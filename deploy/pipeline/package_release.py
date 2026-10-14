"""Build a small, deterministic, public release bundle. Never includes env files."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile

ROOT = Path(__file__).resolve().parents[2]
REVISION = re.compile(r"[0-9a-f]{40}")
IMAGE = re.compile(r"[0-9]{12}\.dkr\.ecr\.us-east-1\.amazonaws\.com/[a-z0-9/_-]+@sha256:[0-9a-f]{64}")
FILES = {
    "compose.yaml": ROOT / "deploy/compose.yaml",
    "compose.https.yaml": ROOT / "deploy/compose.https.yaml",
    "rollout.py": ROOT / "deploy/pipeline/rollout.py",
}


def package(output: Path, revision: str, backend: str, proxy: str) -> str:
    if not REVISION.fullmatch(revision) or not all(IMAGE.fullmatch(value) for value in (backend, proxy)):
        raise ValueError("Expected a full commit and us-east-1 ECR image digests.")
    members = {name: path.read_bytes() for name, path in FILES.items()}
    members["manifest.json"] = json.dumps({
        "version": 1, "revision": revision, "backend": backend, "proxy": proxy,
    }, sort_keys=True).encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as target, gzip.GzipFile(fileobj=target, mode="wb", mtime=0, filename="") as compressed:
        with tarfile.open(fileobj=compressed, mode="w|") as archive:
            for name, data in sorted(members.items()):
                member = tarfile.TarInfo(name)
                member.size, member.mtime, member.mode = len(data), 0, 0o600
                archive.addfile(member, io.BytesIO(data))
    return hashlib.sha256(output.read_bytes()).hexdigest()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--backend", required=True)
    parser.add_argument("--proxy", required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    print(package(arguments.output, arguments.revision, arguments.backend, arguments.proxy))
