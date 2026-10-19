"""Package only committed build inputs for the first manual installation.

No working-tree files, local configuration, documents or Git metadata are sent.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[2]
EXACT = {
    "echomind-backend/Dockerfile", "echomind-backend/.dockerignore",
    "echomind-backend/requirements-deploy.lock", "echomind-backend/alembic.ini",
    "echomind-backend/scripts/check_database.py", "echomind-backend/scripts/reindex_all.py",
    "deploy/compose.yaml", "deploy/compose.https.yaml", "deploy/.env.example",
    "deploy/configure_runtime.py", "deploy/manual/install_envelope.py",
    "deploy/manual/build_first_release.sh",
    "deploy/proxy/Dockerfile", "deploy/proxy/Caddyfile",
}
PREFIXES = ("echomind-backend/app/", "echomind-backend/alembic/")


def allowed(name: str) -> bool:
    path = Path(name)
    return (not path.is_absolute() and ".." not in path.parts
            and (name in EXACT or (name.startswith(PREFIXES)
                 and all(not part.startswith(".") for part in path.parts))))


def package(output: Path) -> dict:
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if not re.fullmatch(r"[a-f0-9]{40}", revision):
        raise ValueError("Require a committed revision.")
    # git archive reads HEAD, never the checkout or an ignored .env file.
    source = subprocess.check_output(["git", "archive", "--format=tar", revision], cwd=ROOT)
    output.parent.mkdir(parents=True, exist_ok=True)
    names = []
    with tarfile.open(fileobj=io.BytesIO(source)) as incoming, output.open("wb") as target:
        with gzip.GzipFile(fileobj=target, mode="wb", mtime=0, filename="") as compressed:
            with tarfile.open(fileobj=compressed, mode="w|") as outgoing:
                for entry in incoming:
                    if not entry.isfile() or not allowed(entry.name):
                        continue
                    data = incoming.extractfile(entry).read()
                    if entry.name.endswith(".sh") and b"\r" in data:
                        raise ValueError("Shell build inputs must use LF; check committed .gitattributes.")
                    member = tarfile.TarInfo(entry.name)
                    member.size, member.mode, member.mtime = len(data), 0o600, 0
                    outgoing.addfile(member, io.BytesIO(data))
                    names.append(entry.name)
    if not EXACT.issubset(names):
        output.unlink()
        raise ValueError("Commit all required installation tools before packaging.")
    return {"revision": revision, "files": len(names), "bytes": output.stat().st_size,
            "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    print(json.dumps(package(parser.parse_args().output)))
