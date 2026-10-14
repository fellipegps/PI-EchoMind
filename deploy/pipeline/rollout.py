"""Single-node release transaction. Run as root on the prepared EC2 through SSM.

No migrations, reindex, private config changes, volume deletion or image pruning.
Subprocess output is suppressed to keep provider errors/configuration out of SSM.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
import time
import urllib.request
import uuid

ROOT = Path("/srv/echomind")
PRIVATE = Path("/etc/echomind")
PUBLIC_KEYS = {
    "BACKEND_IMAGE", "PROXY_IMAGE", "BACKEND_ENV_FILE", "API_DOMAIN", "ACME_EMAIL",
    "PROXY_BIND_IP", "PROXY_HTTP_PORT", "PROXY_HTTPS_PORT", "PROXY_SUBNET", "PROXY_IP",
    "BACKEND_PRIVATE_IP", "BACKEND_CPUS", "BACKEND_MEMORY_LIMIT",
}


class ReleaseError(RuntimeError):
    pass


def command(args, *, env=None, timeout=600, output=None):
    try:
        result = subprocess.run(args, env=env, stdin=subprocess.DEVNULL,
                                stdout=output or subprocess.PIPE, stderr=subprocess.DEVNULL,
                                timeout=timeout, check=True)
        return result.stdout or b""
    except (subprocess.SubprocessError, OSError):
        # Deliberately never include args, captured stderr or a provider exception.
        raise ReleaseError("External operation failed; inspect privately on the host.") from None


def private_file(path: Path):
    metadata = path.lstat()
    if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != 0
            or metadata.st_mode & 0o077 or metadata.st_size > 65536):
        raise ReleaseError("Expected a root-owned private regular configuration file (600).")


def settings() -> dict[str, str]:
    # Only this PUBLIC file is parsed. backend.env is handed directly to Docker.
    path = PRIVATE / "deploy.env"
    private_file(path)
    private_file(PRIVATE / "backend.env")
    values = {}
    for line in path.read_text().splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if (not separator or key not in PUBLIC_KEYS or key in values or not value
                or any(char in value for char in "\0\r\n$'\"")):
            raise ReleaseError("Invalid public deployment settings.")
        values[key] = value
    # The release manifest supplies image digests; example tags are not runtime settings.
    values.pop("BACKEND_IMAGE", None)
    values.pop("PROXY_IMAGE", None)
    if (values.get("BACKEND_ENV_FILE") != str(PRIVATE / "backend.env")
            or values.get("PROXY_BIND_IP", "0.0.0.0") != "0.0.0.0"
            or values.get("PROXY_HTTP_PORT", "80") != "80"
            or values.get("PROXY_HTTPS_PORT", "443") != "443"
            or not re.fullmatch(r"[a-z0-9]+(?:[.-][a-z0-9]+)+", values.get("API_DOMAIN", ""))
            or "CHANGE_ME" in str(values)):
        raise ReleaseError("Complete the public domain and standard HTTPS configuration first.")
    return values


def manifest(release: Path) -> dict:
    value = json.loads((release / "manifest.json").read_text())
    if value.get("version") != 1 or not re.fullmatch(r"[0-9a-f]{40}", value.get("revision", "")):
        raise ReleaseError("Invalid release manifest.")
    for name, repository in (("backend", "BACKEND_REPOSITORY"), ("proxy", "PROXY_REPOSITORY")):
        expected = os.environ[repository]
        if not re.fullmatch(re.escape(expected) + r"@sha256:[0-9a-f]{64}", value.get(name, "")):
            raise ReleaseError("Image digest is outside the approved ECR repositories.")
    return value


def atomic_json(path: Path, value: dict):
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".release-")
    try:
        with os.fdopen(descriptor, "w") as target:
            json.dump(value, target, sort_keys=True)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, path)
        if os.name == "posix":
            directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    finally:
        Path(temporary).unlink(missing_ok=True)


class Host:
    def __init__(self, environment: dict[str, str], *, project="echomind", empty_env_file="/dev/null"):
        self.environment = environment
        self.project = project
        self.empty_env_file = empty_env_file

    def compose(self, state, *args, timeout=600, output=None):
        # Snapshot the public settings with each release, including the old ones for rollback.
        env = self.environment | state["settings"] | {
            "BACKEND_IMAGE": state["backend"], "PROXY_IMAGE": state["proxy"],
        }
        return command([
            "docker", "compose", "--project-name", self.project, "--env-file", self.empty_env_file,
            "--file", str(Path(state["release"]) / "compose.yaml"),
            "--file", str(Path(state["release"]) / "compose.https.yaml"), *args,
        ], env=env, timeout=timeout, output=output)

    def preflight(self, state):
        self.compose(state, "config", "--quiet")
        # No app startup/model loading and no automatic migrations.
        command([
            "docker", "run", "--rm", "--network", "host", "--read-only", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges:true", "--memory", "384m", "--memory-swap", "384m",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=32m", "--env-file", str(PRIVATE / "backend.env"),
            state["backend"], "python", "scripts/check_database.py",
        ], env=self.environment, timeout=120)

    def drain(self, state):
        self.documents(state, "drain", "--timeout", "300", timeout=620)

    def resume(self, state):
        self.documents(state, "resume")

    def documents(self, state, *args, timeout=600, output=None):
        # The maintenance utility must work even if the application fails to start.
        # No network or provider credentials; same UID and file locks as the API.
        volume = self.project + "_documents"
        command(["docker", "volume", "inspect", volume], env=self.environment)
        return command([
            "docker", "run", "--rm", "--network", "none", "--read-only", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges:true", "--memory", "128m", "--memory-swap", "128m",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=16m", "--mount",
            f"type=volume,source={volume},target=/var/lib/echomind/documents",
            state["backend"], "python", "-m", "app.document_runtime", *args,
        ], env=self.environment, timeout=timeout, output=output)

    def initialize_documents(self):
        command(["docker", "volume", "create", "--label", f"com.docker.compose.project={self.project}",
                 "--label", "com.docker.compose.volume=documents", self.project + "_documents"], env=self.environment)

    def backup(self, state):
        # The backend holds admission + processing locks while producing the archive.
        # Encrypted S3 + lifecycle; bucket write failure blocks the replacement.
        with tempfile.TemporaryDirectory(prefix="backup-", dir=ROOT) as directory:
            archive = Path(directory) / "documents.tar"
            with archive.open("wb") as output:
                self.documents(state, "backup", output=output)
            command(["aws", "s3", "cp", str(archive),
                     f"s3://{os.environ['RELEASE_BUCKET']}/backups/{uuid.uuid4().hex}.documents.tar",
                     "--sse", "AES256", "--only-show-errors"], env=self.environment, timeout=900)

    def up(self, state):
        self.compose(state, "up", "--detach", "--no-build", "--pull", "never", "--wait",
                     "--wait-timeout", "180", timeout=900)

    def healthy(self, state):
        # Compose health is liveness; also require real DB readiness and public trusted TLS.
        self.compose(state, "exec", "-T", "backend", "python", "scripts/check_database.py", timeout=120)
        url = f"https://{state['settings']['API_DOMAIN']}/health"
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        for attempt in range(12):
            try:
                with opener.open(url, timeout=10) as response:
                    if (response.status == 200 and response.url == url
                            and json.loads(response.read(4096)) == {"status": "ok", "service": "EchoMind API"}):
                        return
            except (OSError, ValueError):
                pass
            time.sleep(5)
        raise ReleaseError("Public HTTPS health check failed.")

    def stop(self, state):
        self.compose(state, "stop", timeout=900)


def transact(host, new: dict, current: Path):
    """Rollback only application/Compose versions; never downgrade a database or restore uploads."""
    previous = json.loads(current.read_text()) if current.exists() else None
    pending = current.with_name("pending.json")
    if pending.exists():
        raise ReleaseError("Interrupted release detected; reconcile pending.json privately before retrying.")
    host.preflight(new)
    atomic_json(pending, {"previous": previous, "candidate": new})
    attempted = False
    try:
        if previous:
            host.drain(previous)
            host.backup(previous)
        else:
            host.initialize_documents()
            host.drain(new)
            host.backup(new)
        attempted = True
        host.up(new)
        host.healthy(new)
        host.resume(new)
        # Retain the previous release for an explicit manual rollback after a healthy deploy.
        if previous:
            atomic_json(current.with_name("previous.json"), previous)
        atomic_json(current, new)
        pending.unlink()
        print("Release verified and committed.")
    except Exception:
        try:
            if previous:
                if attempted:
                    # Use the known previous utility even if candidate Python code is broken.
                    host.drain(previous)
                    host.up(previous)
                    host.healthy(previous)
                host.resume(previous)
            elif attempted:
                host.stop(new)
            if previous:
                atomic_json(current, previous)
            else:
                current.unlink(missing_ok=True)
            pending.unlink()
        except Exception:
            raise ReleaseError("Recovery failed; maintenance/pending state preserved for the operator.") from None
        raise ReleaseError("Release failed; previous version resumed." if previous else
                           "Initial release failed; candidate stopped. No previous version exists.") from None


def recover_previous(host, current: Path):
    """Explicit operator recovery after a kill/reboot; preserve the marker if any check fails."""
    pending = current.with_name("pending.json")
    previous = json.loads(pending.read_text()).get("previous")
    if previous is None:
        raise ReleaseError("Interrupted initial release has no previous version; inspect/stop its candidate manually.")
    host.drain(previous)
    host.up(previous)
    host.healthy(previous)
    host.resume(previous)
    atomic_json(current, previous)
    pending.unlink()
    print("Interrupted release recovered to its verified previous version.")


def main():
    import fcntl
    parser = argparse.ArgumentParser(description=__doc__)
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument("--release", type=Path)
    operation.add_argument("--recover-previous", action="store_true", help="Explicit operator recovery from pending.json")
    arguments = parser.parse_args()
    os.umask(0o077)
    if os.geteuid() != 0 or not (ROOT / "bootstrap-ready").is_file():
        raise ReleaseError("Use root on the prepared EC2 host.")
    if not all(os.path.ismount(path) for path in (ROOT, PRIVATE)):
        raise ReleaseError("Durable storage/private configuration mount is unavailable.")
    with (ROOT / "deploy.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ReleaseError("Another deployment is running.") from None
        recovery = None
        if arguments.recover_previous:
            recovery = json.loads((ROOT / "pending.json").read_text()).get("previous")
            if recovery is None:
                raise ReleaseError("No previous version in interrupted initial release; inspect/stop candidate manually.")
        release = Path(recovery["release"] if recovery else arguments.release).resolve()
        if release.parent != ROOT / "releases" or release.is_symlink():
            raise ReleaseError("Release directory outside the durable release store.")
        if shutil.disk_usage(ROOT).free < 4 * 1024**3:
            raise ReleaseError("Require at least 4 GiB free before pulling images/backing up documents.")
        values = manifest(release)
        state = values | {"release": str(release), "settings": settings()}
        if recovery and any(recovery.get(key) != values[key] for key in ("revision", "backend", "proxy")):
            raise ReleaseError("Recovery state disagrees with its saved manifest.")
        # A minimal environment prevents ambient Compose overrides and credential leakage.
        env = {"PATH": os.defpath + ":/usr/local/bin:/snap/bin", "HOME": "/root",
               "AWS_DEFAULT_REGION": "us-east-1", "AWS_REGION": "us-east-1", "AWS_PAGER": ""}
        with tempfile.TemporaryDirectory(prefix="ecr-", dir=ROOT) as directory:
            env["DOCKER_CONFIG"] = directory
            token = command(["aws", "ecr", "get-login-password"], env=env, timeout=30)
            try:
                subprocess.run(["docker", "login", "--username", "AWS", "--password-stdin",
                                os.environ["BACKEND_REPOSITORY"].split("/")[0]],
                               input=token, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               timeout=30, check=True)
            except subprocess.SubprocessError:
                raise ReleaseError("ECR authentication failed.") from None
            finally:
                del token
            for name in ("backend", "proxy"):
                command(["docker", "pull", "--platform", "linux/amd64", values[name]], env=env, timeout=900)
            current = ROOT / "current.json"
            if not current.exists() and command(["docker", "ps", "-aq", "--filter", "label=com.docker.compose.project=echomind"], env=env).strip():
                raise ReleaseError("Unmanaged existing containers detected; register the initial release first.")
            if recovery:
                recover_previous(Host(env), current)
            else:
                transact(Host(env), state, current)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(str(error) if isinstance(error, ReleaseError) else "Release aborted; inspect privately on the host.")
        raise SystemExit(1) from None
