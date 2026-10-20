"""Reject an obsolete CI result before obtaining AWS credentials or starting SSM."""
import json
import os
import re
import urllib.request

revision = os.environ["RELEASE_REVISION"]
repository = os.environ["GITHUB_REPOSITORY"]
if not re.fullmatch(r"[0-9a-f]{40}", revision) or not re.fullmatch(r"[\w.-]+/[\w.-]+", repository):
    raise SystemExit("Invalid release context.")
request = urllib.request.Request(
    f"https://api.github.com/repos/{repository}/git/ref/heads/main",
    headers={"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
             "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"},
)
with urllib.request.urlopen(request, timeout=15) as response:
    latest = json.load(response)["object"]["sha"]
if revision != latest:
    raise SystemExit("Main has a newer commit; this release is obsolete. Wait for its CI.")
checks = urllib.request.Request(
    f"https://api.github.com/repos/{repository}/actions/workflows/ci.yml/runs"
    f"?head_sha={revision}&event=push&status=success&per_page=10",
    headers=request.headers,
)
with urllib.request.urlopen(checks, timeout=15) as response:
    runs = json.load(response)["workflow_runs"]
if not any(run.get("head_sha") == revision and run.get("head_branch") == "main"
           and run.get("event") == "push" and run.get("conclusion") == "success"
           and run.get("head_repository", {}).get("full_name") == repository for run in runs):
    raise SystemExit("Require successful push CI for the current main revision before publication.")
print("Current main revision has successful push CI.")
