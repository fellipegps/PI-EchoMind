"""Local safety/regression checks; never executes host bootstrap or AWS commands."""

from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

from estimate_cost import estimate


DIRECTORY = Path(__file__).resolve().parent


class CfnLoader(yaml.SafeLoader):
    pass


def intrinsic(loader, tag, node):
    if isinstance(node, yaml.ScalarNode):
        value = loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        value = loader.construct_sequence(node)
    else:
        value = loader.construct_mapping(node)
    if tag == "GetAtt" and isinstance(value, str):
        value = value.split(".")
    return {tag if tag in {"Ref", "Condition"} else "Fn::" + tag: value}


CfnLoader.add_multi_constructor("!", intrinsic)


def load_template():
    return yaml.load((DIRECTORY / "stack.yaml").read_text(encoding="utf-8"), Loader=CfnLoader)


class InfrastructureChecks(unittest.TestCase):
    def setUp(self):
        self.template = load_template()
        self.resources = self.template["Resources"]

    def test_template_size_and_region_independent_references(self):
        self.assertLess((DIRECTORY / "stack.yaml").stat().st_size, 51200)
        self.assertNotRegex(str(self.template), r"\b\d{12}\b")
        self.assertNotIn("arn:aws:iam::", (DIRECTORY / "stack.yaml").read_text())

    def test_public_access_has_no_admin_or_backend_port(self):
        ingress = self.resources["WebSecurityGroup"]["Properties"]["SecurityGroupIngress"]
        self.assertEqual({(rule["FromPort"], rule["ToPort"]) for rule in ingress}, {(80, 80), (443, 443)})
        node = self.resources["Node"]["Properties"]
        self.assertNotIn("KeyName", node)
        self.assertFalse(node["NetworkInterfaces"][0]["AssociatePublicIpAddress"])

    def test_container_credentials_and_burst_charges_are_blocked(self):
        node = self.resources["Node"]["Properties"]
        self.assertEqual(node["MetadataOptions"]["HttpTokens"], "required")
        self.assertEqual(node["MetadataOptions"]["HttpPutResponseHopLimit"], 1)
        self.assertEqual(node["CreditSpecification"]["CPUCredits"], "standard")
        self.assertTrue(node["DisableApiTermination"])

    def test_retention_and_backup_cover_the_durable_disk(self):
        disk = self.resources["DataVolume"]
        self.assertEqual(disk["DeletionPolicy"], "Retain")
        self.assertEqual(disk["UpdateReplacePolicy"], "Retain")
        self.assertTrue(disk["Properties"]["Encrypted"])
        schedule = self.resources["SnapshotPolicy"]["Properties"]["PolicyDetails"]["Schedules"][0]
        self.assertEqual(schedule["RetainRule"]["Count"], 7)
        self.assertEqual(schedule["CreateRule"]["Interval"], 24)
        self.assertTrue(schedule["CopyTags"])

    def test_budget_observes_spend_before_credits(self):
        budget = self.resources["Budget"]["Properties"]
        self.assertFalse(budget["Budget"]["CostTypes"]["IncludeCredit"])
        thresholds = [item["Notification"]["Threshold"] for item in budget["NotificationsWithSubscribers"]]
        self.assertEqual(thresholds, [50, 80, 100, 100])

    def test_backup_failure_alarm_uses_actual_dlm_metric(self):
        alarm = self.resources["BackupAlarm"]["Properties"]
        self.assertEqual((alarm["Namespace"], alarm["MetricName"]), ("AWS/EBS", "SnapshotsCreateFailed"))
        self.assertEqual(alarm["Dimensions"][0]["Name"], "DLMPolicyId")

    def test_host_uses_both_durable_stores_and_mount_guards(self):
        script = self.resources["Node"]["Properties"]["UserData"]["Fn::Base64"]["Fn::Sub"][0]
        for value in ("/srv/echomind/docker", "/srv/echomind/containerd", "mountpoint -q /srv/echomind", "mountpoint -q /etc/echomind"):
            self.assertIn(value, script)
        self.assertNotIn("ln -s", script)
        self.assertNotIn("set -x", script)
        self.assertNotIn("get-secret-value", script)

    def test_never_formats_reused_unknown_or_signed_disks(self):
        script = self.resources["Node"]["Properties"]["UserData"]["Fn::Base64"]["Fn::Sub"][0]
        fragment = script[script.index("FS_TYPE="):script.index("DISK_UUID=")]
        for filesystem, signature, fresh, expected in (("", "", True, True), ("ext4", "", False, False),
                                                       ("", "", False, False), ("xfs", "", False, False), ("", "gpt", True, False)):
            with self.subTest(filesystem=filesystem, signature=signature, fresh=fresh):
                # Only mocked disk commands execute. No real block device is accessed.
                mocks = f'''set -e
blkid() {{ printf '%s' '{filesystem}'; }}
wipefs() {{ printf '%s' '{signature}'; }}
mkfs.ext4() {{ printf 'FORMATTED'; }}
DEVICE=/dev/synthetic-test-only
'''
                result = subprocess.run(["bash", "-c", mocks + fragment.replace("${FreshDisk}", str(fresh).lower())],
                                        capture_output=True, text=True, timeout=5)
                self.assertEqual("FORMATTED" in result.stdout, expected)

    def test_shell_syntax_without_executing_bootstrap(self):
        script = self.resources["Node"]["Properties"]["UserData"]["Fn::Base64"]["Fn::Sub"][0]
        # EC2 limits decoded user data to 16 KiB, independently of template size.
        self.assertLess(len(script.encode("utf-8")), 16384)
        subprocess.run(["bash", "-n"], input=script, text=True, check=True, timeout=5)

    def test_unverified_cli_is_never_extracted(self):
        script = self.resources["Node"]["Properties"]["UserData"]["Fn::Base64"]["Fn::Sub"][0]
        fragment = script[script.index("CLI_FINGERPRINT="):script.index('"$CLI_WORK/aws/install"')]
        fingerprint = "FB5DB77FD5C118B80511ADA8A6310ACC4672475C"
        for valid, signer, extracted in ((True, fingerprint, True), (False, fingerprint, False),
                                         (True, "0" * 40, False)):
            with self.subTest(valid=valid, signer=signer), tempfile.TemporaryDirectory() as work:
                mocks = f'''set -euo pipefail
CLI_WORK={work!r}
gpg() {{
  if test "$2" = --show-keys; then printf 'fpr:::::::::{fingerprint}:\\n';
  elif test "$2" = --status-fd; then
    printf '[GNUPG:] VALIDSIG {signer} other-public-fields\\n'
    return {0 if valid else 1}
  fi
}}
curl() {{ :; }}
unzip() {{ printf 'EXTRACTED'; }}
'''
                result = subprocess.run(["bash", "-c", mocks + fragment], capture_output=True,
                                        text=True, timeout=5)
                self.assertEqual("EXTRACTED" in result.stdout, extracted)

    def test_old_ssm_blocks_readiness_if_stable_refresh_is_insufficient(self):
        script = self.resources["Node"]["Properties"]["UserData"]["Fn::Base64"]["Fn::Sub"][0]
        fragment = script[script.index('SSM_VERSION=$("$SSM_AGENT"'):script.index("printf '%s\\n' 'Host ready")]
        for initial, refreshed, expected in (("3.3.1000.0", "3.3.1000.0", False),
                                            ("3.3.1000.0", "3.3.2746.0", True),
                                            ("3.3.2746.0", "3.3.2746.0", True)):
            with self.subTest(initial=initial, refreshed=refreshed):
                mocks = f'''set -euo pipefail
VERSION={initial}
SSM_AGENT=mock_agent
mock_agent() {{ printf 'SSM Agent version: %s\\n' "$VERSION"; }}
snap() {{ VERSION={refreshed}; }}
systemctl() {{ :; }}
'''
                result = subprocess.run(["bash", "-c", mocks + fragment + "printf READY"],
                                        capture_output=True, text=True, timeout=5)
                self.assertEqual("READY" in result.stdout, expected)

    def test_cost_calculator(self):
        result = estimate()
        self.assertEqual(result["gross_monthly_total"], "24.11")
        self.assertEqual(result["illustrative_credit_months"], "4.15")


if __name__ == "__main__":
    unittest.main()
