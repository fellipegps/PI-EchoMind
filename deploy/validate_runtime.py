"""Validate Compose with synthetic settings and a disposable project only.

Build the backend first. This script never reads production env files or calls AWS.
It removes only the containers/network/volume from its randomly named test project.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import urllib.request
import uuid


COMPOSE_FILE = Path(__file__).resolve().with_name("compose.yaml")
CACHE_CHECK = """
import os
from pathlib import Path
assert os.getuid() == 10001
assert os.environ['HF_HOME'] == '/var/cache/echomind/models'
assert os.environ['DEPLOY_SMOKE_LITERAL'] == 'literal-${DO_NOT_EXPAND}-$-#'
for name in ('RATE_LIMIT_INSTANCE_COUNT', 'UVICORN_WORKERS', 'WEB_CONCURRENCY'):
    assert os.environ[name] == '1', name
marker = Path(os.environ['HF_HOME']) / 'deploy-runtime-check.txt'
marker.write_text('persisted', encoding='utf-8')
temporary = Path('/tmp/deploy-runtime-check.txt')
temporary.write_text('temporary', encoding='utf-8')
temporary.unlink()
"""
CACHE_PERSISTED = """
import os
from pathlib import Path
marker = Path(os.environ['HF_HOME']) / 'deploy-runtime-check.txt'
assert marker.read_text(encoding='utf-8') == 'persisted'
"""
CRASH_UVICORN = r"""
import os
from pathlib import Path
import signal
targets = []
for entry in Path('/proc').iterdir():
    # PID 1 is docker-init; its argv also contains the Uvicorn command.
    if not entry.name.isdigit() or int(entry.name) in {1, os.getpid()}:
        continue
    try:
        arguments = (entry / 'cmdline').read_bytes().split(b'\0')
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        continue
    if b'uvicorn' in arguments:
        targets.append(int(entry.name))
assert len(targets) == 1, targets
os.kill(targets[0], signal.SIGKILL)
"""


def run(
    arguments: list[str],
    *,
    environment: dict[str, str],
    allowed_exit_codes: tuple[int, ...] = (0,),
) -> str:
    result = subprocess.run(
        arguments,
        env=environment,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=180,
    )
    if result.returncode not in allowed_exit_codes:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {arguments[0]}\n"
            f"{result.stdout[-4000:]}\n{result.stderr[-4000:]}"
        )
    return result.stdout.strip()


def inspect(container_id: str, environment: dict[str, str]) -> dict:
    return json.loads(run(["docker", "inspect", container_id], environment=environment))[0]


def wait_healthy(container_id: str, environment: dict[str, str], *, restart_after: int = -1) -> dict:
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        details = inspect(container_id, environment)
        state = details["State"]
        if (
            state["Running"]
            and state.get("Health", {}).get("Status") == "healthy"
            and details["RestartCount"] > restart_after
        ):
            return details
        time.sleep(2)
    raise RuntimeError("The disposable backend did not become healthy within 120 seconds.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="echomind-backend:local")
    arguments = parser.parse_args()
    project = "echomind-runtime-check-" + uuid.uuid4().hex[:12]
    # Avoid inheriting deploy settings or automatically loading a real .env file.
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("BACKEND_", "COMPOSE_"))
    }
    environment["COMPOSE_DISABLE_ENV_FILE"] = "true"
    with tempfile.TemporaryDirectory(prefix=project + "-") as temporary_directory:
        directory = Path(temporary_directory)
        runtime_env = directory / "backend.env"
        runtime_env.write_text(
            "DATABASE_URL=postgresql://smoke:smoke@127.0.0.1:1/smoke\n"
            "SUPABASE_URL=http://127.0.0.1:54321\n"
            "SUPABASE_SECRET_KEY=smoke-placeholder\n"
            "GROQ_API_KEY=smoke-placeholder\n"
            "RAG_WARMUP_ENABLED=false\n"
            "DEPLOY_SMOKE_LITERAL=literal-${DO_NOT_EXPAND}-$-#\n"
            # Verify Compose protects the single-process contract even if mis-set here.
            "UVICORN_WORKERS=4\n"
            "WEB_CONCURRENCY=4\n"
            "RATE_LIMIT_INSTANCE_COUNT=4\n",
            encoding="utf-8",
        )
        environment.update(
            BACKEND_IMAGE=arguments.image,
            BACKEND_ENV_FILE=str(runtime_env),
            BACKEND_PORT="0",
        )
        compose = [
            "docker", "compose", "--project-name", project,
            "--file", str(COMPOSE_FILE),
        ]

        def compose_run(*command: str) -> str:
            return run([*compose, *command], environment=environment)

        def exec_python(code: str) -> str:
            return compose_run("exec", "--no-TTY", "backend", "python", "-c", code)

        try:
            compose_run("config", "--quiet")
            compose_run(
                "up", "--detach", "--no-build", "--pull", "never",
                "--wait", "--wait-timeout", "120",
            )
            container_id = compose_run("ps", "--quiet", "backend")
            details = wait_healthy(container_id, environment)
            config = details["HostConfig"]
            assert config["RestartPolicy"]["Name"] == "unless-stopped"
            assert config["ReadonlyRootfs"] is True
            assert config["Init"] is True
            assert config["Memory"] == 1536 * 1024 * 1024
            assert config["MemorySwap"] == config["Memory"]
            assert config["NanoCpus"] == 2_000_000_000
            assert config["PidsLimit"] == 256
            assert details["Config"]["StopTimeout"] == 310
            assert "ALL" in config["CapDrop"]
            assert "no-new-privileges:true" in config["SecurityOpt"]
            log_config = config["LogConfig"]
            assert log_config["Type"] == "local"
            assert log_config["Config"]["max-size"] == "10m"
            assert log_config["Config"]["max-file"] == "3"
            port = details["NetworkSettings"]["Ports"]["8000/tcp"][0]
            assert port["HostIp"] == "127.0.0.1"
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port['HostPort']}/health", timeout=5
            ) as response:
                assert json.load(response) == {"status": "ok", "service": "EchoMind API"}
            exec_python(CACHE_CHECK)
            print("PASS: healthy startup, runtime limits, logging, isolation and cache permissions", flush=True)

            compose_run(
                "up", "--detach", "--no-build", "--pull", "never", "--force-recreate",
                "--wait", "--wait-timeout", "120",
            )
            recreated_id = compose_run("ps", "--quiet", "backend")
            assert recreated_id != container_id
            details = wait_healthy(recreated_id, environment)
            exec_python(CACHE_PERSISTED)
            print("PASS: model cache preserved when the container is recreated", flush=True)

            # Docker documents a >=10-second successful start before restart monitoring.
            time.sleep(11)
            before_restart = details["RestartCount"]
            run(
                [*compose, "exec", "--no-TTY", "backend", "python", "-c", CRASH_UVICORN],
                environment=environment,
                allowed_exit_codes=(0, 137, 143),
            )
            details = wait_healthy(recreated_id, environment, restart_after=before_restart)
            exec_python(CACHE_PERSISTED)
            print("PASS: automatic restart after process failure, preserving cache", flush=True)

            compose_run("stop")
            stopped = inspect(recreated_id, environment)
            # Uvicorn 0.29 re-raises SIGTERM after completing its lifespan shutdown.
            # Under docker-init this can legitimately be reported as 128 + 15.
            exit_code = stopped["State"]["ExitCode"]
            assert exit_code in (0, 143), exit_code
            assert stopped["State"]["OOMKilled"] is False
            shutdown_logs = compose_run("logs", "--no-color", "--tail", "30", "backend")
            assert "Application shutdown complete." in shutdown_logs
            time.sleep(11)
            assert inspect(recreated_id, environment)["State"]["Running"] is False
            print(f"PASS: clean shutdown (exit {exit_code}); intentional stops are respected", flush=True)
        finally:
            # The project name is generated here, never accepted from the caller.
            compose_run("down", "--volumes")
    print("PASS: disposable test resources removed; no AWS operations performed", flush=True)


if __name__ == "__main__":
    main()
