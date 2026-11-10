"""Simula chat sintético em Docker local, através do Caddy e com TLS validado.

Não mede geração Groq/E5 nem capacidade da EC2. Não lê configuração privada,
não faz chamadas AWS e não baixa imagens. Usa os limites do Compose versionado,
uma rede interna e portas publicadas apenas em loopback. Remove somente os
recursos do projeto aleatório que criou. Requer Docker Compose >= 2.30.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json
import math
import os
from pathlib import Path
import secrets
import ssl
import sys
import tempfile
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "deploy/tests"))
from validate_https import LocalHTTPSConnection, ORIGIN  # noqa: E402
from validate_runtime import inspect, run  # noqa: E402


def percentile(values, fraction):
    return sorted(values)[max(0, math.ceil(len(values) * fraction) - 1)] if values else None


def memory_bytes(value):
    number, unit = value.strip().split()[0], ""
    for index, char in enumerate(number):
        if not (char.isdigit() or char == "."):
            number, unit = number[:index], number[index:]
            break
    return float(number) * {"B": 1, "kB": 1000, "MB": 1000**2, "GB": 1000**3,
                           "KiB": 1024, "MiB": 1024**2, "GiB": 1024**3}[unit]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--duration", type=int, default=60)
    parser.add_argument("--vus", nargs="+", type=int, default=[10, 50])
    parser.add_argument("--backend-image", default="echomind-backend:docs-f13-f05f1f8")
    parser.add_argument("--proxy-image", default="echomind-proxy:docs-f12-f05f1f8")
    args = parser.parse_args()
    if args.duration < 10 or args.duration > 120 or args.vus != sorted(set(args.vus)) or any(v < 1 or v > 50 for v in args.vus):
        parser.error("Use 10–120 segundos e patamares crescentes entre 1 e 50 clientes.")
    project = "echomind-capacidade-local-" + uuid.uuid4().hex[:12]
    subnet = f"172.28.{secrets.randbelow(240) + 10}"
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith(("BACKEND_", "COMPOSE_", "PROXY_"))
                   and key not in {"API_DOMAIN", "ACME_EMAIL"}}
    environment.update(COMPOSE_DISABLE_ENV_FILE="true", BACKEND_IMAGE=args.backend_image,
                       PROXY_IMAGE=args.proxy_image, API_DOMAIN="localhost", ACME_EMAIL="ops@example.test",
                       PROXY_BIND_IP="127.0.0.1", PROXY_HTTP_PORT="0", PROXY_HTTPS_PORT="0",
                       PROXY_SUBNET=subnet + ".0/29", PROXY_IP=subnet + ".2", BACKEND_PRIVATE_IP=subnet + ".3")
    endpoint = None if environment.get("DOCKER_CONTEXT") else environment.get("DOCKER_HOST")
    endpoint = endpoint or run(["docker", "context", "inspect", "--format", "{{.Endpoints.docker.Host}}"],
                               environment=environment)
    if not endpoint.startswith(("npipe:////./pipe/", "unix:///")):
        parser.error("A simulação aceita apenas o daemon Docker local.")
    report = {"scope": "Docker local; chat e provedores sintéticos; não representa EC2/Groq/E5",
              "target": {"clients": 50, "max_first_byte_seconds": 5, "availability_sla": None},
              "stages": []}
    with tempfile.TemporaryDirectory(prefix=project + "-") as temporary:
        directory = Path(temporary)
        runtime = directory / "backend.env"
        def configure_quota(quota):
            runtime.write_text(
                "DATABASE_URL=postgresql://synthetic:synthetic@127.0.0.1:1/synthetic?sslmode=require\n"
                "SUPABASE_URL=https://synthetic.supabase.co\nSUPABASE_SECRET_KEY=sb_secret_synthetic_offline_only\n"
                "GROQ_API_KEY=gsk_synthetic_offline_only\nALLOWED_ORIGINS=" + ORIGIN + "\n"
                "RAG_WARMUP_ENABLED=false\nDOCUMENT_RECOVERY_ENABLED=false\nCHAT_RATE_LIMIT_REQUESTS=" + str(quota) + "\n",
                encoding="utf-8")
        configure_quota(20)
        environment["BACKEND_ENV_FILE"] = str(runtime)
        override = directory / "test.json"
        configuration = {"services": {"backend": {
            "environment": {"PYTHONPATH": "/deploy-check:/app"},
            "healthcheck": {"interval": "1s", "start_period": "5s"},
            "volumes": [
                {"type": "bind", "source": str(ROOT / "deploy/tests/fixtures"), "target": "/deploy-check", "read_only": True},
                {"type": "bind", "source": str(ROOT / "echomind-backend/app"), "target": "/app/app", "read_only": True},
            ]}, "proxy": {"healthcheck": {"interval": "1s", "start_period": "2s"},
                          "networks": {"edge": {}}}},
            "networks": {"proxy": {"internal": True}, "edge": {}}}
        override.write_text(json.dumps(configuration), encoding="utf-8")
        compose = ["docker", "compose", "--project-name", project,
                   "--file", str(ROOT / "deploy/compose.yaml"),
                   "--file", str(ROOT / "deploy/compose.https.yaml"), "--file", str(override)]
        def compose_run(*command):
            return run([*compose, *command], environment=environment)
        def save():
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            resolved = json.loads(compose_run("config", "--format", "json"))
            command = resolved["services"]["backend"]["command"]
            command[command.index("app.main:app")] = "https_app:app"
            configuration["services"]["backend"]["command"] = command
            override.write_text(json.dumps(configuration), encoding="utf-8")
            compose_run("up", "--detach", "--no-build", "--pull", "never", "--wait", "--wait-timeout", "120")
            proxy_id = compose_run("ps", "--quiet", "proxy")
            proxy = inspect(proxy_id, environment)
            port = int(proxy["NetworkSettings"]["Ports"]["8443/tcp"][0]["HostPort"])
            ca_path = directory / "public-ca.crt"
            run(["docker", "cp", proxy_id + ":/data/caddy/pki/authorities/local/root.crt", str(ca_path)], environment=environment)
            context = ssl.create_default_context(cafile=str(ca_path))
            def request_chat():
                started = time.perf_counter()
                connection = LocalHTTPSConnection("localhost", port, context=context, timeout=12)
                result = {"status": None, "first_byte_seconds": None, "marker": False}
                try:
                    connection.request("POST", "/public/synthetic/chat", body=json.dumps({"message": "stream"}),
                                       headers={"Content-Type": "application/json", "Origin": ORIGIN})
                    response = connection.getresponse()
                    result["status"] = response.status
                    first = response.read(1)
                    if response.status == 200 and first:
                        result["first_byte_seconds"] = time.perf_counter() - started
                    body = first + response.read()
                    result["marker"] = response.status == 200 and body == b"first\nlast\n"
                except (OSError, TimeoutError, ssl.SSLError):
                    result["error"] = "transport-or-timeout"
                finally:
                    connection.close()
                result["duration_seconds"] = time.perf_counter() - started
                return result
            # The default per-IP quota must remain effective, including behind Caddy.
            barrier = threading.Barrier(50)
            def burst(_):
                barrier.wait(timeout=15)
                return request_chat()
            with ThreadPoolExecutor(max_workers=50) as pool:
                baseline = list(pool.map(burst, range(50)))
            statuses = Counter(str(r["status"]) for r in baseline)
            report["default_quota_burst"] = {"requests": 50, "per_ip_quota": 20, "statuses": dict(statuses)}
            save()
            if statuses != Counter({"200": 20, "429": 30}):
                raise RuntimeError("A rajada não reproduziu a quota padrão esperada; consulte o relatório.")
            print("Quota padrão: 20 respostas aceitas e 30 recusas 429 na mesma origem.", flush=True)
            # A second, explicitly synthetic configuration isolates proxy/server capacity.
            configure_quota(6000)
            compose_run("up", "--detach", "--no-build", "--pull", "never", "--force-recreate", "--wait", "--wait-timeout", "120", "backend")
            backend_id = compose_run("ps", "--quiet", "backend")
            report["simulation_quota_per_minute"] = 6000
            for clients in args.vus:
                started = time.monotonic()
                deadline = started + args.duration
                stop = threading.Event()
                samples = []
                def observe():
                    while not stop.is_set():
                        raw = run(["docker", "stats", "--no-stream", "--format", "{{json .}}", backend_id, proxy_id], environment=environment)
                        for row in raw.splitlines():
                            item = json.loads(row)
                            role = next(role for role, cid in (("backend", backend_id), ("proxy", proxy_id))
                                        if cid.startswith(item["ID"]))
                            usage, limit = item["MemUsage"].split("/")
                            samples.append({"role": role, "cpu_pct": float(item["CPUPerc"].rstrip("%")),
                                            "memory_bytes": memory_bytes(usage), "memory_limit_bytes": memory_bytes(limit)})
                        stop.wait(1)
                observer = threading.Thread(target=observe)
                observer.start()
                barrier = threading.Barrier(clients)
                def client(_):
                    barrier.wait(timeout=15)
                    responses = []
                    while time.monotonic() < deadline:
                        responses.append(request_chat())
                    return responses
                try:
                    with ThreadPoolExecutor(max_workers=clients) as pool:
                        results = [r for group in pool.map(client, range(clients)) for r in group]
                finally:
                    stop.set()
                    observer.join(timeout=20)
                elapsed = time.monotonic() - started
                times = [r["first_byte_seconds"] for r in results if r["first_byte_seconds"] is not None]
                states = {role: inspect(cid, environment) for role, cid in (("backend", backend_id), ("proxy", proxy_id))}
                stage = {"clients": clients, "elapsed_seconds": elapsed, "requests": len(results),
                         "statuses": dict(Counter(str(r["status"]) for r in results)),
                         "first_byte_p50_seconds": percentile(times, .50), "first_byte_p95_seconds": percentile(times, .95),
                         "first_byte_max_seconds": max(times) if times else None,
                         "requests_per_second": len(results) / elapsed, "correct_markers": sum(r["marker"] for r in results),
                         "resources": {role: {"samples": sum(s["role"] == role for s in samples),
                           "cpu_max_pct": max((s["cpu_pct"] for s in samples if s["role"] == role), default=None),
                           "memory_max_mib": max((s["memory_bytes"] / 1024**2 for s in samples if s["role"] == role), default=None),
                           "oom": states[role]["State"]["OOMKilled"], "restarts": states[role]["RestartCount"],
                           "healthy": states[role]["State"].get("Health", {}).get("Status") == "healthy"} for role in states}}
                stage["synthetic_target_met"] = (len(times) == len(results) and all(r["marker"] for r in results)
                                                 and bool(times) and max(times) <= 5
                                                 and all(v["healthy"] and not v["oom"] and v["restarts"] == 0 for v in stage["resources"].values()))
                report["stages"].append(stage)
                save()
                print(f"Patamar {clients}: {len(results)} requisições; aceite sintético = {stage['synthetic_target_met']}", flush=True)
                if not stage["synthetic_target_met"]:
                    break
        finally:
            compose_run("down", "--volumes", "--remove-orphans", "--timeout", "15")
            report["owned_resources_removed"] = True
            save()
            print("Recursos do ensaio removidos.", flush=True)
    if len(report["stages"]) != len(args.vus) or not all(s["synthetic_target_met"] for s in report["stages"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
