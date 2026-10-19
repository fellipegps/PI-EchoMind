"""Run offline deployment checks using the already built local validation image."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
FILES = [
    "deploy/aws/stack.yaml", "deploy/aws/pipeline.yaml", "deploy/aws/access.yaml", "deploy/aws/provisioning.yaml", "deploy/aws/security.guard",
    "deploy/aws/check_infra.py", "deploy/aws/estimate_cost.py",
    "deploy/aws/render_provisioning_policies.py", "deploy/aws/preflight_local.py", "deploy/aws/preflight.mcp.py",
    "deploy/aws/verify_host.sh",
    "deploy/compose.yaml", "deploy/compose.https.yaml", ".github/workflows/deploy-aws.yml", ".github/workflows/ci.yml",
    *["deploy/pipeline/" + name for name in (
        "package_release.py", "publish_release.py", "ensure_main.py", "send_release.py",
        "rollout.py", "test_release.py",
    )],
]
container = ["docker", "run", "--rm", "--pull", "never", "--platform", "linux/amd64",
             "--network", "none", "--read-only", "--tmpfs", "/tmp", "--workdir", "/work",
             "--env", "PYTHONDONTWRITEBYTECODE=1"]
for relative in FILES:
    container.extend(["--mount", f"type=bind,source={ROOT / relative},target=/work/{relative},readonly"])
container.append("echomind-infra-validation:local")
for check in (
    ["actionlint", "-shellcheck=", "-pyflakes=", ".github/workflows/ci.yml", ".github/workflows/deploy-aws.yml"],
    ["cfn-lint", "-t", "deploy/aws/stack.yaml", "deploy/aws/pipeline.yaml", "deploy/aws/access.yaml", "deploy/aws/provisioning.yaml", "-r", "us-east-1", "--format", "json"],
    ["cfn-guard", "validate", "--data", "deploy/aws/stack.yaml", "--rules", "deploy/aws/security.guard", "--show-summary", "fail"],
    ["cfn-guard", "validate", "--data", "deploy/aws/pipeline.yaml", "--rules", "deploy/aws/security.guard", "--show-summary", "fail"],
    ["cfn-guard", "validate", "--data", "deploy/aws/access.yaml", "--rules", "deploy/aws/security.guard", "--show-summary", "fail"],
    ["cfn-guard", "validate", "--data", "deploy/aws/provisioning.yaml", "--rules", "deploy/aws/security.guard", "--show-summary", "fail"],
    ["python", "deploy/aws/check_infra.py"],
    ["python", "deploy/aws/render_provisioning_policies.py", "--check"],
    ["bash", "-n", "deploy/aws/verify_host.sh"],
    ["python", "-m", "unittest", "discover", "-s", "deploy/pipeline", "-p", "test_release.py", "-v"],
):
    subprocess.run([*container, *check], check=True)
print("Offline deployment checks passed; no AWS resources or credentials used.")
