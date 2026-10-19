"""Encrypt existing local credentials to a one-use certificate generated on EC2.

Only ciphertext is written. Plaintext stays in process memory and a private pipe.
This does not fetch AWS Secrets Manager values or print provider errors.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess

from dotenv import dotenv_values
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("configure_runtime", ROOT / "deploy/configure_runtime.py")
configuration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(configuration)


def prepare(certificate: Path, output: Path, openssl: str, pooler_host: str) -> dict:
    if not re.fullmatch(r"aws-[0-9]+-sa-east-1\.pooler\.supabase\.com", pooler_host):
        raise ValueError("Use the session pooler hostname verified in the project dashboard.")
    project = "owaapvfiyltapzlhosqh"
    local = dotenv_values(ROOT / "echomind-backend/.env", interpolate=False)
    url = make_url(local["DATABASE_URL"])
    if (url.host != f"db.{project}.supabase.co" or url.username != "postgres"
            or local.get("SUPABASE_URL", "").rstrip("/") != f"https://{project}.supabase.co"):
        raise ValueError("Local credentials do not match the reviewed project.")
    values = {key: local[key] for key in ("SUPABASE_URL", "SUPABASE_SECRET_KEY", "GROQ_API_KEY")}
    values["DATABASE_URL"] = url.set(
        host=pooler_host, port=5432, username=f"postgres.{project}",
        query={"sslmode": "require", "connect_timeout": "10"},
    ).render_as_string(hide_password=False)
    values["ALLOWED_ORIGINS"] = "https://echomind-front.vercel.app"
    values = configuration.validated_config(values)
    plaintext = "".join(f"{name}={value}\n" for name, value in values.items()).encode()
    # Capture all OpenSSL output: errors must never disclose plaintext/configuration.
    encrypted = subprocess.run(
        [openssl, "cms", "-encrypt", "-binary", "-aes-256-cbc", "-outform", "DER",
         "-recip", str(certificate.resolve())], input=plaintext, capture_output=True, check=False,
    )
    if encrypted.returncode or not encrypted.stdout:
        raise ValueError("Could not encrypt the private configuration.")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as target:
        target.write(encrypted.stdout)
    # Digest travels inside the authenticated SSM command, binding ciphertext to this transfer.
    return {"bytes": len(encrypted.stdout), "sha256": hashlib.sha256(encrypted.stdout).hexdigest(),
            "variables": len(values), "plaintext_written": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--certificate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--openssl", required=True)
    parser.add_argument("--pooler-host", required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(prepare(args.certificate, args.output, args.openssl, args.pooler_host)))
    except Exception:
        print("Private configuration encryption failed; no credentials are printed.")
        raise SystemExit(1) from None
