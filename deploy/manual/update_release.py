"""Update an existing manual EC2 installation, preserving its proxy and volumes.

Run as root from committed, digest-verified source through SSM. Reuses the tested
pipeline transaction without enabling CI/CD, ECR, S3 or additional permissions.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))
from rollout import Host, PRIVATE, ROOT, ReleaseError, atomic_json, command, settings, transact


def atomic_text(path: Path, value: str):
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".manual-")
    try:
        with os.fdopen(descriptor, "w") as target:
            target.write(value)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


class ManualHost(Host):
    def healthy(self, state):
        super().healthy(state)
        live = json.loads(command(["docker", "inspect", "echomind-backend-1"], env=self.environment))[0]
        proxy = json.loads(command(["docker", "inspect", "echomind-proxy-1"], env=self.environment))[0]
        if live["Image"] != self.expected_images[state["backend"]] or proxy["Id"] != self.proxy_id:
            raise ReleaseError("Live image or proxy identity mismatch.")

    def backup(self, state):
        # Local recovery copy on encrypted data EBS; not an off-host disaster backup.
        directory = ROOT / "manual-backups"
        directory.mkdir(mode=0o700, exist_ok=True)
        archive = directory / (uuid.uuid4().hex + ".documents.tar")
        with archive.open("xb") as output:
            os.chmod(archive, 0o600)
            self.documents(state, "backup", output=output)
            output.flush()
            os.fsync(output.fileno())
        if archive.stat().st_size < 1024:
            raise ReleaseError("Document backup is incomplete.")

    def up(self, state):
        # Proxy image/configuration must match the current release, checked below.
        self.compose(state, "up", "--detach", "--no-deps", "--force-recreate",
                     "--no-build", "--pull", "never", "--wait",
                     "--wait-timeout", "180", "backend", timeout=600)


def update(revision: str, archive_sha256: str):
    if (ROOT / "current.json").exists():
        raise ReleaseError("Installation adopted by the pipeline; use its release/recovery procedure.")
    if os.geteuid() != 0 or not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ReleaseError("Root and a full committed revision are required.")
    if not (ROOT / "bootstrap-ready").is_file() or not all(os.path.ismount(p) for p in (ROOT, PRIVATE)):
        raise ReleaseError("Prepared durable mounts are required.")
    if not re.fullmatch(r"[0-9a-f]{64}", archive_sha256):
        raise ReleaseError("Expected the authenticated source archive digest.")
    if shutil.disk_usage(ROOT).free < 4 * 1024**3:
        raise ReleaseError("Require at least 4 GiB free on the data volume.")
    source = ROOT / "releases" / revision
    if source.resolve() != Path(__file__).resolve().parents[2]:
        raise ReleaseError("Run only from the verified candidate source directory.")
    archive = ROOT / "incoming" / (revision + ".tar.gz")
    if hashlib.sha256(archive.read_bytes()).hexdigest() != archive_sha256:
        raise ReleaseError("Source archive digest mismatch.")
    manifest_path = ROOT / "manual-current.json"
    previous_manifest = json.loads(manifest_path.read_text())
    old_revision = previous_manifest["source_revision"]
    if not re.fullmatch(r"[0-9a-f]{40}", old_revision) or old_revision == revision:
        raise ReleaseError("Expected a distinct existing manual release.")
    old_source = ROOT / "releases" / old_revision
    if previous_manifest["source_directory"] != str(old_source):
        raise ReleaseError("Existing release directory mismatch.")
    for name in ("compose.yaml", "compose.https.yaml", "proxy/Caddyfile", "proxy/Dockerfile"):
        if (source / "deploy" / name).read_bytes() != (old_source / "deploy" / name).read_bytes():
            raise ReleaseError("This backend-only update requires unchanged Compose and proxy inputs.")
    environment = {"PATH": os.environ["PATH"], "HOME": "/root"}
    host = ManualHost(environment)
    containers = [json.loads(command(["docker", "inspect", f"echomind-{name}-1"], env=environment))[0]
                  for name in ("backend", "proxy")]
    for index, item in enumerate(containers):
        if not item["State"]["Running"] or item["State"]["Health"]["Status"] != "healthy":
            raise ReleaseError("Existing application must be healthy before updating.")
        if index == 0 and item["Config"]["Labels"]["com.docker.compose.project.working_dir"] != str(old_source / "deploy"):
            raise ReleaseError("Live containers disagree with the current manual release.")
    old = {"release": str(old_source / "deploy"), "revision": old_revision,
           "backend": containers[0]["Config"]["Image"],
           "proxy": containers[1]["Config"]["Image"], "settings": settings()}
    candidate = old | {"release": str(source / "deploy"), "revision": revision,
                       "backend": "echomind-backend:" + revision}
    expected_image = json.loads(command(["docker", "image", "inspect", candidate["backend"]], env=environment))[0]["Id"]
    host.expected_images = {old["backend"]: containers[0]["Image"], candidate["backend"]: expected_image}
    host.proxy_id = containers[1]["Id"]
    public_path = PRIVATE / "deploy.env"
    lines = public_path.read_text().splitlines()
    if sum(line.startswith("BACKEND_IMAGE=") for line in lines) != 1:
        raise ReleaseError("Public image setting requires reconciliation.")
    directory = ROOT / "manual-rollout"
    directory.mkdir(mode=0o700, exist_ok=True)
    current = directory / "current.json"
    if current.exists() and json.loads(current.read_text()) != old:
        raise ReleaseError("Manual rollout state requires reconciliation before another update.")
    if not current.exists():
        atomic_json(current, old)
    # transact checks pending.json, drains writes, backs up, swaps and verifies;
    # failures restore the previous backend and resume writes automatically.
    transact(host, candidate, current)
    live = json.loads(command(["docker", "inspect", "echomind-backend-1"], env=environment))[0]
    proxy = json.loads(command(["docker", "inspect", "echomind-proxy-1"], env=environment))[0]
    if live["Image"] != expected_image or proxy["Id"] != containers[1]["Id"]:
        raise ReleaseError("Live image verification requires operator reconciliation.")
    atomic_text(public_path, "\n".join(
        "BACKEND_IMAGE=" + candidate["backend"] if line.startswith("BACKEND_IMAGE=") else line
        for line in lines) + "\n")
    atomic_json(directory / "previous-installation.json", previous_manifest)
    manifest = previous_manifest | {
        "source_revision": revision, "source_archive_sha256": archive_sha256,
        "source_directory": str(source), "updated_at": datetime.now(timezone.utc).isoformat(),
        "previous_source_revision": old_revision,
        "images": {"backend": {"reference": candidate["backend"], "id": live["Image"]},
                   "proxy": {"reference": candidate["proxy"], "id": proxy["Image"]}},
    }
    atomic_json(manifest_path, manifest)
    print(json.dumps({"revision": revision, "backend_image": live["Image"],
                      "proxy_preserved": True, "recovery_state_saved": True}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--sha256", required=True)
    args = parser.parse_args()
    try:
        import fcntl
        os.umask(0o077)
        with (ROOT / "deploy.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            update(args.revision, args.sha256)
    except Exception:
        print("Manual update failed; inspect private rollout state before retrying.")
        raise SystemExit(1) from None
