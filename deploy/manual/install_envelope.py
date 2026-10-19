"""Decrypt a one-use CMS envelope on EC2 and atomically install validated runtime.

Run as root. The SHA256 must come from the authenticated SSM control channel.
Never prints plaintext or provider diagnostics. Transfer keys are removed on exit.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import stat
import subprocess

DEPLOY = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("configure_runtime", DEPLOY / "configure_runtime.py")
configuration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(configuration)
TRANSFER = Path("/etc/echomind/transfer")


def private(path: Path, *, directory=False) -> None:
    if path.is_symlink():
        raise ValueError("Reject symbolic links.")
    metadata = path.stat()
    if (metadata.st_uid != 0 or stat.S_IMODE(metadata.st_mode) != (0o700 if directory else 0o600)
            or not (stat.S_ISDIR(metadata.st_mode) if directory else stat.S_ISREG(metadata.st_mode))):
        raise ValueError("Require root-only transfer files.")


def install(checksum: str) -> None:
    if os.geteuid() != 0 or not re.fullmatch(r"[a-f0-9]{64}", checksum):
        raise ValueError("Require root and a validated transfer digest.")
    private(TRANSFER.parent, directory=True)
    private(TRANSFER, directory=True)
    certificate, key, envelope = (TRANSFER / name for name in ("recipient.pem", "recipient.key", "runtime.cms"))
    try:
        for path in (certificate, key, envelope):
            private(path)
        ciphertext = envelope.read_bytes()
        if len(ciphertext) > 65536 or hashlib.sha256(ciphertext).hexdigest() != checksum:
            raise ValueError("Encrypted transfer digest mismatch.")
        decrypted = subprocess.run(
            ["openssl", "cms", "-decrypt", "-binary", "-inform", "DER", "-recip", str(certificate),
             "-inkey", str(key)], input=ciphertext, capture_output=True, check=False,
        )
        if decrypted.returncode or len(decrypted.stdout) > 65536:
            raise ValueError("Could not decrypt the private configuration.")
        values = configuration.parse_raw(decrypted.stdout.decode("utf-8"))
        configuration.install_private_file(Path("/etc/echomind/backend.env"), values)
    finally:
        for path in (certificate, key, envelope):
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sha256", required=True)
    args = parser.parse_args()
    try:
        install(args.sha256)
        print("Private production configuration installed; one-use transfer files removed.")
    except Exception:
        print("Private installation aborted; previous runtime preserved, diagnostics suppressed.")
        raise SystemExit(1) from None
