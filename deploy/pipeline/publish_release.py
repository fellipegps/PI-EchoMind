"""GitHub runner: publish immutable images/bundle using an already assumed OIDC role."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

from package_release import ROOT, REVISION, package


def run(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def image_digest(repository: str, revision: str) -> str | None:
    result = subprocess.run([
        "aws", "ecr", "describe-images", "--repository-name", repository.split("/", 1)[1],
        "--image-ids", f"imageTag={revision}", "--output", "json",
    ], capture_output=True)
    if result.returncode:
        if b"ImageNotFoundException" in result.stderr:
            return None
        raise RuntimeError("ECR lookup failed; publication aborted.")
    digest = json.loads(result.stdout)["imageDetails"][0]["imageDigest"]
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise RuntimeError("Invalid ECR image digest.")
    return digest


def main():
    revision = os.environ["RELEASE_REVISION"]
    if not REVISION.fullmatch(revision):
        raise RuntimeError("Invalid release commit.")
    account = os.environ["AWS_ACCOUNT_ID"]
    registry = f"{account}.dkr.ecr.us-east-1.amazonaws.com"
    repositories = [os.environ["BACKEND_REPOSITORY"], os.environ["PROXY_REPOSITORY"]]
    if (not re.fullmatch(r"[0-9]{12}", account)
            or not all(re.fullmatch(re.escape(registry) + r"/[a-z0-9/_-]+", repo) for repo in repositories)):
        raise RuntimeError("Unexpected ECR registry.")
    os.umask(0o077)
    with tempfile.TemporaryDirectory(prefix="echomind-publish-") as directory:
        os.environ["DOCKER_CONFIG"] = str(Path(directory) / "docker")
        token = run(["aws", "ecr", "get-login-password"], capture_output=True).stdout
        try:
            run(["docker", "login", "--username", "AWS", "--password-stdin", registry],
                input=token, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        finally:
            del token
        images = []
        for repo, context in zip(repositories, (ROOT / "echomind-backend", ROOT / "deploy/proxy")):
            digest = image_digest(repo, revision)
            if digest is None:
                tag = f"{repo}:{revision}"
                run(["docker", "build", "--platform", "linux/amd64", "--label",
                     f"org.opencontainers.image.revision={revision}", "--tag", tag, str(context)])
                run(["docker", "push", tag])
                digest = image_digest(repo, revision)
                if digest is None:
                    raise RuntimeError("Published image is unavailable.")
            images.append(f"{repo}@{digest}")
        bundle = Path(directory) / "release.tar.gz"
        checksum = package(bundle, revision, *images)
        result = subprocess.run([
            "aws", "s3api", "put-object", "--bucket", os.environ["RELEASE_BUCKET"],
            "--key", f"releases/{revision}.tar.gz", "--body", str(bundle),
            "--server-side-encryption", "AES256", "--if-none-match", "*",
        ], capture_output=True)
        if result.returncode:
            # A rerun reuses only an identical bundle; never overwrite a commit.
            old = Path(directory) / "existing.tar.gz"
            run(["aws", "s3api", "get-object", "--bucket", os.environ["RELEASE_BUCKET"],
                 "--key", f"releases/{revision}.tar.gz", str(old)], stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL)
            if hashlib.sha256(old.read_bytes()).hexdigest() != checksum:
                raise RuntimeError("Commit bundle already exists with different content.")
        with open(os.environ["GITHUB_OUTPUT"], "a") as output:
            output.write(f"bundle_sha256={checksum}\n")
        print("Commit images and release bundle published.")


if __name__ == "__main__":
    main()
