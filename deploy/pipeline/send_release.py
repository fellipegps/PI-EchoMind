"""GitHub runner: invoke the fixed SSM document and report status without private logs."""
import json
import os
import re
import subprocess
import time


def aws(*args):
    return subprocess.run(["aws", *args, "--output", "json"], capture_output=True)


def main():
    revision, checksum = os.environ["RELEASE_REVISION"], os.environ["BUNDLE_SHA256"]
    instance, document = os.environ["INSTANCE_ID"], os.environ["DEPLOY_DOCUMENT"]
    if (not re.fullmatch(r"[0-9a-f]{40}", revision) or not re.fullmatch(r"[0-9a-f]{64}", checksum)
            or not re.fullmatch(r"i-[0-9a-f]{8,17}", instance)
            or not re.fullmatch(r"[A-Za-z0-9_.-]{3,128}", document)):
        raise SystemExit("Invalid SSM release parameters.")
    result = aws("ssm", "send-command", "--document-name", document, "--document-version", "$DEFAULT",
                 "--instance-ids", instance, "--timeout-seconds", "120",
                 "--parameters", json.dumps({"Revision": [revision], "BundleSha256": [checksum]}))
    if result.returncode:
        raise SystemExit("SSM rejected the release command; inspect permissions/host status.")
    command_id = json.loads(result.stdout)["Command"]["CommandId"]
    print(f"SSM command: {command_id}", flush=True)
    deadline = time.monotonic() + 3100
    while time.monotonic() < deadline:
        result = aws("ssm", "get-command-invocation", "--command-id", command_id, "--instance-id", instance)
        if result.returncode:
            if b"InvocationDoesNotExist" not in result.stderr:
                raise SystemExit("Could not observe SSM; command may still be running. Inspect host before retrying.")
        else:
            status = json.loads(result.stdout)["Status"]
            if status == "Success":
                print("Application release verified by the host.")
                return
            if status not in {"Pending", "InProgress", "Delayed", "Cancelling"}:
                raise SystemExit(f"Release status: {status}. Inspect SSM privately; automatic recovery may have run.")
        time.sleep(10)
    raise SystemExit("Observation deadline exceeded. Do not assume cancellation; inspect SSM and pending.json.")


if __name__ == "__main__":
    main()
