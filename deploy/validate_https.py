"""Exercise the production HTTPS overlay with a local CA and synthetic services.

Never reads real env files, requests public certificates, changes host trust,
or calls AWS. Only this randomly named project's test resources are removed.
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
from pathlib import Path
import secrets
import socket
import ssl
import sys
import tempfile
import time
import uuid

from validate_runtime import inspect, run, wait_healthy


DEPLOY = Path(__file__).resolve().parent
ORIGIN = "https://frontend.example.test"
CLIENT_CHECK = r'''
import http.client, json, socket, ssl
class ProxyConnection(http.client.HTTPSConnection):
    def connect(self):
        sock = socket.create_connection(('proxy', 8443), timeout=10)
        self.sock = self._context.wrap_socket(sock, server_hostname='localhost')
context = ssl.create_default_context(cafile='/tmp/public-ca.crt')
def request(path, forged):
    connection = ProxyConnection('localhost', context=context, timeout=10)
    connection.request('GET', path, headers={'X-Forwarded-For': forged, 'X-Forwarded-Proto': 'http',
                                           'Forwarded': 'for=198.51.100.8', 'X-Real-IP': forged})
    response = connection.getresponse()
    result = (response.status, json.loads(response.read()))
    connection.close()
    return result
status, body = request('/_deploy/ip', '198.51.100.1, 198.51.100.2')
assert status == 200 and body['ip'] == EXPECTED_IP and body['scheme'] == 'https', body
assert body['forwarded'] is None and body['real_ip'] is None
for index in range(2):
    assert request('/_deploy/limited', f'198.51.100.{index}')[0] == 200
assert request('/_deploy/limited', '203.0.113.99')[0] == 429
# This direct peer is not trusted by Uvicorn, even from the shared bridge.
connection = http.client.HTTPConnection('backend', 8000, timeout=10)
connection.request('GET', '/_deploy/ip', headers={'X-Forwarded-For': '198.51.100.99', 'X-Forwarded-Proto': 'https'})
response = connection.getresponse()
body = json.loads(response.read())
assert body['ip'] == EXPECTED_IP and body['scheme'] == 'http', body
connection.close()
print('PASS: distinct client IP, spoofing rejected, independent rate bucket and direct peer untrusted')
'''


class LocalHTTPSConnection(http.client.HTTPSConnection):
    """Use IPv4 loopback while still validating TLS for the localhost name."""
    def connect(self):
        connection = socket.create_connection(("127.0.0.1", self.port), timeout=self.timeout)
        self.sock = self._context.wrap_socket(connection, server_hostname="localhost")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend-image", default="echomind-backend:local")
    parser.add_argument("--proxy-image", default="echomind-proxy:local")
    arguments = parser.parse_args()
    project = "echomind-https-check-" + uuid.uuid4().hex[:12]
    subnet = f"172.29.{secrets.randbelow(240) + 10}"
    proxy_ip = subnet + ".2"
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith(("BACKEND_", "COMPOSE_", "PROXY_"))
                   and key not in {"API_DOMAIN", "ACME_EMAIL"}}
    environment.update(COMPOSE_DISABLE_ENV_FILE="true", BACKEND_IMAGE=arguments.backend_image,
                       PROXY_IMAGE=arguments.proxy_image, API_DOMAIN="localhost", ACME_EMAIL="ops@example.test",
                       PROXY_BIND_IP="127.0.0.1", PROXY_HTTP_PORT="0", PROXY_HTTPS_PORT="0",
                       PROXY_SUBNET=subnet + ".0/29", PROXY_IP=proxy_ip, BACKEND_PRIVATE_IP=subnet + ".3")
    with tempfile.TemporaryDirectory(prefix=project + "-") as temporary:
        directory = Path(temporary)
        runtime = directory / "backend.env"
        runtime.write_text(
            "DATABASE_URL=postgresql://synthetic:synthetic@127.0.0.1:1/synthetic?sslmode=require\n"
            "SUPABASE_URL=https://synthetic.supabase.co\nSUPABASE_SECRET_KEY=sb_secret_synthetic_offline_only\n"
            "GROQ_API_KEY=gsk_synthetic_offline_only\nALLOWED_ORIGINS=" + ORIGIN + "\n"
            "RAG_WARMUP_ENABLED=false\nDOCUMENT_RECOVERY_ENABLED=false\nCHAT_RATE_LIMIT_REQUESTS=2\n",
            encoding="utf-8",
        )
        environment["BACKEND_ENV_FILE"] = str(runtime)
        override = directory / "test.yaml"
        override_settings = {"services": {"backend": {
            "environment": {"PYTHONPATH": "/deploy-check:/app"},
            "healthcheck": {"interval": "1s", "start_period": "5s"},
            "volumes": [{"type": "bind", "source": str(DEPLOY / "fixtures"), "target": "/deploy-check", "read_only": True}],
        }, "proxy": {"healthcheck": {"interval": "1s", "start_period": "2s"}}}}
        override.write_text(json.dumps(override_settings), encoding="utf-8")
        compose = ["docker", "compose", "--project-name", project, "--file", str(DEPLOY / "compose.yaml"),
                   "--file", str(DEPLOY / "compose.https.yaml"), "--file", str(override)]

        def compose_run(*command):
            return run([*compose, *command], environment=environment)

        try:
            # Preserve every actual production server option; swap only the app.
            # This config contains synthetic env values only and is never printed.
            configuration = json.loads(compose_run("config", "--format", "json"))
            command = configuration["services"]["backend"]["command"]
            command[command.index("app.main:app")] = "https_app:app"
            override_settings["services"]["backend"]["command"] = command
            override.write_text(json.dumps(override_settings), encoding="utf-8")
            compose_run("config", "--quiet")
            compose_run("up", "--detach", "--no-build", "--pull", "never", "--wait", "--wait-timeout", "120")
            backend_id = compose_run("ps", "--quiet", "backend")
            proxy_id = compose_run("ps", "--quiet", "proxy")
            backend = inspect(backend_id, environment)
            proxy = inspect(proxy_id, environment)
            assert not backend["HostConfig"]["PortBindings"]
            assert proxy["Config"]["User"] == "10001:10001"
            assert proxy["HostConfig"]["ReadonlyRootfs"] is True
            assert "ALL" in proxy["HostConfig"]["CapDrop"]
            assert proxy["HostConfig"]["Memory"] == 128 * 1024 * 1024
            # Proxy never receives backend keys or the original document volume.
            assert not any(value.startswith(("DATABASE_URL=", "SUPABASE_SECRET_KEY=", "GROQ_API_KEY=")) for value in proxy["Config"]["Env"])
            destinations = {mount["Destination"] for mount in proxy["Mounts"]}
            assert {"/data", "/config"} <= destinations <= {"/data", "/config", "/tmp"}
            http_port = int(proxy["NetworkSettings"]["Ports"]["8080/tcp"][0]["HostPort"])
            https_port = int(proxy["NetworkSettings"]["Ports"]["8443/tcp"][0]["HostPort"])
            ca_path = directory / "public-ca.crt"
            run(["docker", "cp", proxy_id + ":/data/caddy/pki/authorities/local/root.crt", str(ca_path)], environment=environment)
            context = ssl.create_default_context(cafile=str(ca_path))

            def request(path, *, method="GET", body=None, headers=None):
                connection = LocalHTTPSConnection("localhost", https_port, context=context, timeout=20)
                connection.request(method, path, body=body, headers=headers or {})
                response = connection.getresponse()
                result = response.status, dict(response.getheaders()), response.read()
                connection.close()
                return result

            # A valid local certificate is required; no global trust or verify=False.
            try:
                untrusted = LocalHTTPSConnection("localhost", https_port, timeout=10)
                untrusted.request("GET", "/health")
                raise AssertionError("Unexpectedly trusted disposable CA")
            except ssl.SSLCertVerificationError:
                pass
            finally:
                untrusted.close()
            status, headers, body = request("/health")
            assert status == 200 and json.loads(body)["status"] == "ok"
            assert headers["Strict-Transport-Security"] == "max-age=31536000"
            assert headers["X-Content-Type-Options"] == "nosniff"
            assert "Server" not in headers
            key_modes = compose_run("exec", "--no-TTY", "proxy", "sh", "-c",
                                    "find /data -type f -name '*.key' -exec stat -c %a {} +")
            assert key_modes and set(key_modes.splitlines()) == {"600"}
            connection = http.client.HTTPConnection("127.0.0.1", http_port, timeout=10)
            connection.request("GET", "/health?synthetic=1", headers={"Host": "localhost"})
            redirect = connection.getresponse()
            assert redirect.status == 308 and redirect.getheader("Location") == "https://localhost/health?synthetic=1"
            redirect.read()
            connection.close()
            wrong_host_status = request("/health", headers={"Host": "unexpected.example.test"})[0]
            assert wrong_host_status in {404, 421}, wrong_host_status
            print("PASS: verified TLS, HTTP redirect, host restriction, isolation and response headers", flush=True)

            for origin, expected_status in ((ORIGIN, 200), ("https://blocked.example.test", 400)):
                status, headers, _ = request("/chat", method="OPTIONS", headers={
                    "Origin": origin, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "Content-Type"})
                assert status == expected_status
                assert headers.get("Access-Control-Allow-Origin") == (ORIGIN if expected_status == 200 else None)
            print("PASS: exact CORS allowlist through HTTPS", flush=True)

            for message, disconnect in (("stream", False), ("disconnect", True)):
                connection = LocalHTTPSConnection("localhost", https_port, context=context, timeout=10)
                connection.connect()
                started = time.monotonic()
                connection.request("POST", "/chat", body=json.dumps({"message": message, "tenant_id": "synthetic"}),
                                   headers={"Content-Type": "application/json", "Origin": ORIGIN})
                response = connection.getresponse()
                assert response.status == 200 and response.readline() == b"first\n"
                first_chunk_elapsed = time.monotonic() - started
                assert first_chunk_elapsed < 1.5, f"First chunk buffered: {first_chunk_elapsed:.3f}s"
                if not disconnect:
                    assert response.read() == b"last\n"
                    assert time.monotonic() - started >= 1.8
                response.close()
                connection.close()
            deadline = time.monotonic() + 8
            while True:
                state = json.loads(request("/_deploy/stream-state")[2])
                if state["cancelled"] >= 1:
                    break
                assert time.monotonic() < deadline, state
                time.sleep(0.2)
            print("PASS: incremental chat stream and upstream cancellation after disconnect", flush=True)

            prefix = b'--synthetic-boundary\r\nContent-Disposition: form-data; name="file"; filename="test.txt"\r\nContent-Type: text/plain\r\n\r\n'
            suffix = b'\r\n--synthetic-boundary--\r\n'
            for size, expected in ((10 * 1024 * 1024, 200), (10 * 1024 * 1024 + 1, 413)):
                status, headers, body = request("/documents/upload", method="POST", body=prefix + b"x" * size + suffix,
                                              headers={"Content-Type": "multipart/form-data; boundary=synthetic-boundary", "Origin": ORIGIN})
                assert status == expected, (status, body[:200])
                assert headers.get("Access-Control-Allow-Origin") == ORIGIN
                if status == 200:
                    assert json.loads(body)["bytes"] == size
            assert request("/_deploy/body", method="POST", body=b"x" * (1024 * 1024 + 1))[0] == 413
            print("PASS: exact 10 MiB file boundary, multipart allowance and proxy body cap", flush=True)

            for suffix_ip in (4, 5):
                client_ip = subnet + f".{suffix_ip}"
                code = f"EXPECTED_IP = {client_ip!r}\n" + CLIENT_CHECK
                output = run(["docker", "run", "--rm", "--network", project + "_proxy", "--ip", client_ip,
                              "--mount", f"type=bind,source={ca_path},target=/tmp/public-ca.crt,readonly",
                              arguments.backend_image, "python", "-c", code], environment=environment)
                print(output, flush=True)

            def certificate_fingerprint():
                connection = LocalHTTPSConnection("localhost", https_port, context=context, timeout=10)
                connection.connect()
                fingerprint = hashlib.sha256(connection.sock.getpeercert(binary_form=True)).hexdigest()
                connection.close()
                return fingerprint

            before = certificate_fingerprint()
            compose_run("up", "--detach", "--no-build", "--pull", "never", "--force-recreate", "--wait", "--wait-timeout", "120", "proxy")
            proxy_id = compose_run("ps", "--quiet", "proxy")
            proxy = wait_healthy(proxy_id, environment)
            https_port = int(proxy["NetworkSettings"]["Ports"]["8443/tcp"][0]["HostPort"])
            assert certificate_fingerprint() == before
            assert request("/health")[0] == 200
            print("PASS: certificate persisted across proxy recreation; public ACME renewal requires deployment", flush=True)
        except Exception:
            # This project contains synthetic values only; retain useful diagnostics.
            print(compose_run("logs", "--tail", "35", "proxy"), flush=True)
            print(compose_run("logs", "--tail", "20", "backend"), flush=True)
            raise
        finally:
            compose_run("down", "--volumes", "--remove-orphans", "--timeout", "15")
            print("PASS: disposable HTTPS resources removed; no AWS operations performed", flush=True)


if __name__ == "__main__":
    main()
