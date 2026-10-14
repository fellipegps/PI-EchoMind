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
print("Successful CI revision is still the main branch head.")
