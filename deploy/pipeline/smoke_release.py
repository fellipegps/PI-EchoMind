"""Disposable local Docker rollback drill. Synthetic HTTP/backup adapters; no AWS/DB/LLM.

Exercises real Compose replacement, offline maintenance locks, durable originals
and the transaction's rollback. HTTPS/SQL readiness use their separate validators.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tarfile
import tempfile
import urllib.request
import uuid

from rollout import Host, ReleaseError, command, transact

SERVER = '''
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        payload = json.dumps({"revision": "synthetic-good"}).encode()
        self.send_response(200)
        self.end_headers()
        self.wfile.write(payload)
    def log_message(self, *args): pass
HTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
'''
SEED = '''
from app.document_storage import DocumentStorage
from hashlib import sha256
content = b"Synthetic original must survive failed deployment"
DocumentStorage().save(tenant_id="synthetic", document_id="document", content=content, digest=sha256(content).hexdigest())
'''


class SmokeHost(Host):
    def __init__(self, environment, project, backup_directory):
        empty_env_file = backup_directory / "empty.env"
        empty_env_file.write_text("")
        super().__init__(environment, project=project, empty_env_file=str(empty_env_file))
        self.backup_directory = backup_directory

    def preflight(self, state):
        self.compose(state, "config", "--quiet")

    def up(self, state):
        self.compose(state, "up", "--detach", "--no-build", "--pull", "never", "--wait",
                     "--wait-timeout", "20", timeout=60)

    def healthy(self, state):
        port = self.compose(state, "port", "backend", "8000").decode().strip().rsplit(":", 1)[1]
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5) as response:
            assert json.load(response) == {"revision": "synthetic-good"}

    def backup(self, state):
        target = self.backup_directory / (uuid.uuid4().hex + ".documents.tar")
        with target.open("wb") as output:
            self.documents(state, "backup", output=output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="echomind-backend:deploy-step7")
    args = parser.parse_args()
    project = "echomind-release-check-" + uuid.uuid4().hex[:12]
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith(("COMPOSE_", "BACKEND_", "PROXY_", "AWS_"))
                   and key not in {"API_DOMAIN", "ACME_EMAIL"}}
    environment["COMPOSE_DISABLE_ENV_FILE"] = "true"
    command(["docker", "image", "inspect", args.image], env=environment)
    with tempfile.TemporaryDirectory(prefix=project) as temporary:
        directory = Path(temporary)
        host = SmokeHost(environment, project, directory)
        states = []
        for revision, server in (("good", SERVER), ("broken", "raise SystemExit(17)")):
            release = directory / revision
            release.mkdir()
            config = {"services": {"backend": {
                "image": args.image, "platform": "linux/amd64", "command": ["python", "-c", server],
                # A shipped release has no source checkout; --no-build must work without this path.
                "build": {"context": str(release / "intentionally-absent-build-context")},
                "ports": ["127.0.0.1::8000"], "read_only": True, "cap_drop": ["ALL"],
                "security_opt": ["no-new-privileges:true"], "mem_limit": "256m", "memswap_limit": "256m",
                "volumes": ["documents:/var/lib/echomind/documents"],
                "tmpfs": ["/tmp:rw,noexec,nosuid,size=16m"],
                "healthcheck": {"interval": "1s", "timeout": "3s", "start_period": "1s", "retries": 2},
            }}, "volumes": {"documents": {}}}
            (release / "compose.yaml").write_text(json.dumps(config))
            (release / "compose.https.yaml").write_text('{"services": {}}')
            states.append({"revision": revision, "release": str(release), "backend": args.image,
                           "proxy": "synthetic-unused", "settings": {}})
        good, broken = states
        current = directory / "current.json"
        try:
            transact(host, good, current)
            host.compose(good, "exec", "-T", "backend", "python", "-c", SEED)
            before = host.compose(good, "ps", "--quiet", "backend")
            try:
                transact(host, broken, current)
                raise AssertionError("Broken candidate unexpectedly passed")
            except ReleaseError as error:
                assert "previous version resumed" in str(error), error
            after = host.compose(good, "ps", "--quiet", "backend")
            assert before != after, "Rollback must recreate the previous container"
            assert json.loads(current.read_text())["revision"] == "good"
            assert not (directory / "pending.json").exists()
            status = json.loads(host.documents(good, "status"))
            assert not status["draining"] and not status["active"]
            host.healthy(good)
            host.drain(good)
            restored = directory / "check.documents.tar"
            with restored.open("wb") as output:
                host.documents(good, "backup", output=output)
            with tarfile.open(restored) as archive:
                originals = [m for m in archive if m.name.endswith("original.bin")]
                assert len(originals) == 1
                assert archive.extractfile(originals[0]).read() == b"Synthetic original must survive failed deployment"
            # Require a nonempty pre-replacement backup too, not just a surviving local file.
            snapshots = [path for path in directory.glob("*.documents.tar") if path != restored]
            backed_up = False
            for snapshot in snapshots:
                with tarfile.open(snapshot) as archive:
                    backed_up |= any(member.name.endswith("original.bin") for member in archive)
            assert backed_up
            host.resume(good)
            print("PASS: real failed container replaced; previous version healthy; originals and backup intact; admission resumed.")
        finally:
            host.compose(good, "down", "--volumes", "--remove-orphans", "--timeout", "5")
            print("Disposable project removed. No AWS, credentials or provider calls.")


if __name__ == "__main__":
    main()
