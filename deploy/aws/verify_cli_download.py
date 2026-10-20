"""Verify the pinned public installer without installing it or accessing AWS.

Requires PyYAML and GnuPG. Downloads only the official public ZIP/signature;
temporary files and the isolated public keyring are removed afterwards.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import urllib.request

from check_infra import load_template


def download(url, destination, limit):
    with urllib.request.urlopen(url, timeout=120) as response, destination.open("wb") as target:
        total = 0
        while chunk := response.read(1024 * 1024):
            total += len(chunk)
            if total > limit:
                raise RuntimeError("Public download exceeded the expected size limit.")
            target.write(chunk)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gpg", default="gpg", help="Existing GnuPG executable; nothing is installed.")
    parser.add_argument("--msys-paths", action="store_true", help="Use /c/... paths for Git for Windows GnuPG.")
    args = parser.parse_args()
    script = load_template()["Resources"]["Node"]["Properties"]["UserData"]["Fn::Base64"]["Fn::Sub"][0]
    version = re.search(r"^CLI_VERSION=(2\.\d+\.\d+)$", script, re.M)[1]
    fingerprint = re.search(r"^CLI_FINGERPRINT=([A-F0-9]{40})$", script, re.M)[1]
    key = re.search(r"-----BEGIN PGP PUBLIC KEY BLOCK-----.*?-----END PGP PUBLIC KEY BLOCK-----", script, re.S)[0]
    with tempfile.TemporaryDirectory(prefix="echomind-cli-verify-") as temp:
        work = Path(temp).resolve()
        # Bound the recursively cleaned temporary directory on Windows as well.
        assert work.parent == Path(tempfile.gettempdir()).resolve()
        assert work.name.startswith("echomind-cli-verify-")
        key_file = work / "awscli.asc"
        key_file.write_text(key + "\n", encoding="ascii")
        def gpg_path(value):
            if isinstance(value, Path):
                value = value.as_posix()
                if args.msys_paths and re.match(r"^[A-Za-z]:/", value):
                    value = "/" + value[0].lower() + value[2:]
            return str(value)
        gpg = [args.gpg, "--homedir", gpg_path(work), "--batch", "--no-tty", "--no-autostart"]
        def invoke(*options):
            return subprocess.run([*gpg, *map(gpg_path, options)], capture_output=True, timeout=60)
        info = invoke("--with-colons", "--show-keys", key_file)
        if info.returncode or fingerprint not in info.stdout.decode("ascii"):
            raise RuntimeError("The embedded public key could not be verified: " + info.stderr.decode(errors="replace"))
        if invoke("--import", key_file).returncode:
            raise RuntimeError("Unable to import the public AWS signing key.")
        archive, signature = work / "awscliv2.zip", work / "awscliv2.zip.sig"
        url = f"https://awscli.amazonaws.com/awscli-exe-linux-x86_64-{version}.zip"
        download(url, archive, 128 * 1024 * 1024)
        download(url + ".sig", signature, 64 * 1024)
        result = invoke("--status-fd", "1", "--verify", signature, archive)
        if result.returncode or f"[GNUPG:] VALIDSIG {fingerprint} " not in result.stdout.decode("ascii"):
            raise RuntimeError("The official installer signature was not accepted. Nothing installed.")
        tampered = work / "tampered.zip"
        shutil.copyfile(archive, tampered)
        with tampered.open("r+b") as altered:
            first = altered.read(1)
            altered.seek(0)
            altered.write(bytes([first[0] ^ 1]))
        if invoke("--verify", signature, tampered).returncode == 0:
            raise RuntimeError("Signature verification failed to reject a changed archive.")
        print(json.dumps({"version": version, "fingerprint": fingerprint,
                          "official_signature_verified": True, "tampered_archive_rejected": True,
                          "installed": False}, indent=2))


if __name__ == "__main__":
    main()
