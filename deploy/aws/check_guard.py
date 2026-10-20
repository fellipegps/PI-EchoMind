"""Prove that the project guard rules accept the template and reject regressions."""

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import tempfile

from check_infra import DIRECTORY, load_template


def guard(template):
    with tempfile.TemporaryDirectory(prefix="echomind-guard-") as temporary:
        path = Path(temporary) / "template.json"
        path.write_text(json.dumps(template), encoding="utf-8")
        return subprocess.run(["cfn-guard", "validate", "--rules", str(DIRECTORY / "security.guard"),
                               "--data", str(path), "--output-format", "json"],
                              capture_output=True, text=True, timeout=30)


def main():
    template = load_template()
    baseline = guard(template)
    if baseline.returncode:
        raise RuntimeError(baseline.stdout + baseline.stderr)
    print("PASS: template accepted by project security rules")
    changes = [
        ("SSH ingress", lambda resources: resources["WebSecurityGroup"]["Properties"]["SecurityGroupIngress"].append(
            {"IpProtocol": "tcp", "FromPort": 22, "ToPort": 22, "CidrIp": "0.0.0.0/0"})),
        ("broad port range", lambda resources: resources["WebSecurityGroup"]["Properties"]["SecurityGroupIngress"][0].update(ToPort=443)),
        ("unencrypted disk", lambda resources: resources["DataVolume"]["Properties"].update(Encrypted=False)),
        ("unlimited CPU billing", lambda resources: resources["Node"]["Properties"]["CreditSpecification"].update(CPUCredits="unlimited")),
        ("IMDSv1", lambda resources: resources["Node"]["Properties"]["MetadataOptions"].update(HttpTokens="optional")),
        ("public audit bucket", lambda resources: resources["AuditBucket"]["Properties"]["PublicAccessBlockConfiguration"].update(BlockPublicPolicy=False)),
    ]
    for name, mutate in changes:
        invalid = deepcopy(template)
        mutate(invalid["Resources"])
        response = guard(invalid)
        if response.returncode == 0:
            raise AssertionError("Security regression was accepted: " + name)
        # A parser/runtime error is not evidence that a security rule rejected it.
        if "FAIL" not in response.stdout:
            raise RuntimeError(response.stdout + response.stderr)
        print("PASS: rejected " + name)


if __name__ == "__main__":
    main()
