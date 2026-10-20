"""Behavioral release failures + trust boundary checks. No Docker, AWS or secrets."""
import copy
import importlib.util
import io
import json
import runpy
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import yaml

from package_release import ROOT, package
from rollout import Host, ReleaseError, command, manifest, recover_previous, rehearse_rollback, transact

SPEC = importlib.util.spec_from_file_location("infra_checks", ROOT / "deploy/aws/check_infra.py")
sys.path.insert(0, str(ROOT / "deploy/aws"))
infra = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(infra)


class FakeHost:
    def __init__(self, failures=()):
        self.events = []
        self.failures = set(failures)

    def __getattr__(self, action):
        def call(state=None):
            event = (action, (state or {}).get("revision"))
            self.events.append(event)
            if event in self.failures:
                self.failures.remove(event)
                raise ReleaseError("Synthetic failure.")
        return call


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.current = Path(self.directory.name) / "current.json"
        self.old = {"revision": "old"}
        self.new = {"revision": "new"}
        self.current.write_text(json.dumps(self.old))

    def test_success_orders_drain_backup_replace_verify_and_resume(self):
        host = FakeHost()
        transact(host, self.new, self.current)
        self.assertEqual(host.events, [("preflight", "new"), ("drain", "old"), ("backup", "old"),
                                       ("up", "new"), ("healthy", "new"), ("resume", "new")])
        self.assertEqual(json.loads(self.current.read_text()), self.new)
        self.assertEqual(json.loads(self.current.with_name("previous.json").read_text()), self.old)
        self.assertFalse(self.current.with_name("pending.json").exists())

    def test_pending_migration_stops_before_any_maintenance(self):
        host = FakeHost({("preflight", "new")})
        with self.assertRaises(ReleaseError):
            transact(host, self.new, self.current)
        self.assertEqual(host.events, [("preflight", "new")])
        self.assertFalse(self.current.with_name("pending.json").exists())

    def test_drain_timeout_or_failed_backup_never_replace_containers(self):
        for action in ("drain", "backup"):
            with self.subTest(action=action):
                host = FakeHost({(action, "old")})
                with self.assertRaisesRegex(ReleaseError, "previous version resumed"):
                    transact(host, self.new, self.current)
                self.assertNotIn(("up", "new"), host.events)
                self.assertEqual(host.events[-1], ("resume", "old"))
                self.assertEqual(json.loads(self.current.read_text()), self.old)

    def test_failed_start_or_tls_restores_previous_release(self):
        for action in ("up", "healthy", "resume"):
            with self.subTest(action=action):
                host = FakeHost({(action, "new")})
                with self.assertRaisesRegex(ReleaseError, "previous version resumed"):
                    transact(host, self.new, self.current)
                self.assertEqual(host.events[-4:], [("drain", "old"), ("up", "old"),
                                                   ("healthy", "old"), ("resume", "old")])
                self.assertEqual(json.loads(self.current.read_text()), self.old)

    def test_failed_recovery_preserves_pending_state_and_never_resumes(self):
        host = FakeHost({("healthy", "new"), ("healthy", "old")})
        with self.assertRaisesRegex(ReleaseError, "Recovery failed"):
            transact(host, self.new, self.current)
        self.assertTrue(self.current.with_name("pending.json").exists())
        self.assertNotIn(("resume", "old"), host.events)
        self.assertNotIn(("resume", "new"), host.events)

    def test_first_deploy_failure_stops_candidate_without_fabricating_rollback(self):
        self.current.unlink()
        host = FakeHost({("healthy", "new")})
        with self.assertRaisesRegex(ReleaseError, "No previous version"):
            transact(host, self.new, self.current)
        self.assertEqual(host.events[:4], [("preflight", "new"), ("initialize_documents", None),
                                          ("drain", "new"), ("backup", "new")])
        self.assertEqual(host.events[-1], ("stop", "new"))
        self.assertFalse(self.current.exists())

    def test_interrupted_release_blocks_new_transactions(self):
        self.current.with_name("pending.json").write_text("{}")
        host = FakeHost()
        with self.assertRaisesRegex(ReleaseError, "Interrupted"):
            transact(host, self.new, self.current)
        self.assertEqual(host.events, [])

    def test_operator_recovery_checks_previous_version_before_resuming(self):
        self.current.with_name("pending.json").write_text(json.dumps({"previous": self.old, "candidate": self.new}))
        host = FakeHost()
        recover_previous(host, self.current)
        self.assertEqual(host.events, [("drain", "old"), ("up", "old"), ("healthy", "old"), ("resume", "old")])
        self.assertFalse(self.current.with_name("pending.json").exists())
        self.assertEqual(json.loads(self.current.read_text()), self.old)

    def test_operator_recovery_failure_keeps_pending_and_maintenance(self):
        pending = self.current.with_name("pending.json")
        pending.write_text(json.dumps({"previous": self.old, "candidate": self.new}))
        host = FakeHost({("healthy", "old")})
        with self.assertRaises(ReleaseError):
            recover_previous(host, self.current)
        self.assertTrue(pending.exists())
        self.assertNotIn(("resume", "old"), host.events)

    def test_rehearsal_proves_candidate_then_recovers_verified_previous(self):
        host = FakeHost()
        rehearse_rollback(host, self.new, self.current)
        self.assertEqual(json.loads(self.current.read_text()), self.old)
        self.assertIn(('healthy', 'new'), host.events)
        self.assertEqual(host.events[-2:], [('healthy', 'old'), ('resume', 'old')])
        self.assertFalse(self.current.with_name('pending.json').exists())

    def test_rehearsal_does_not_claim_success_when_candidate_or_recovery_fails(self):
        for action, revision in (('up', 'new'), ('healthy', 'new'), ('healthy', 'old'), ('resume', 'old')):
            self.current.write_text(json.dumps(self.old))
            self.current.with_name('pending.json').unlink(missing_ok=True)
            with self.assertRaises(ReleaseError):
                rehearse_rollback(FakeHost({(action, revision)}), self.new, self.current)

    def test_local_adoption_is_recovery_only_and_pins_exact_images(self):
        path = Path(self.directory.name)
        value = {'version': 1, 'revision': 'a' * 40, 'origin': 'manual-adoption',
                 'backend': 'sha256:' + 'b' * 64, 'proxy': 'sha256:' + 'c' * 64}
        (path / 'manifest.json').write_text(json.dumps(value))
        self.assertEqual(manifest(path, allow_local_recovery=True), value)
        with patch.dict('os.environ', {'BACKEND_REPOSITORY':'approved','PROXY_REPOSITORY':'approved'}):
            with self.assertRaises(ReleaseError):manifest(path)
        value['backend'] = 'untrusted:latest'
        (path / 'manifest.json').write_text(json.dumps(value))
        with self.assertRaises(ReleaseError):manifest(path, allow_local_recovery=True)

    def test_durable_state_write_failure_restores_previous_pointer(self):
        import rollout
        original = rollout.atomic_json

        def failing_write(path, value):
            if path == self.current and value == self.new:
                raise OSError("Synthetic disk failure")
            original(path, value)

        with patch("rollout.atomic_json", side_effect=failing_write):
            with self.assertRaisesRegex(ReleaseError, "previous version resumed"):
                transact(FakeHost(), self.new, self.current)
        self.assertEqual(json.loads(self.current.read_text()), self.old)

    def test_private_provider_error_is_never_emitted(self):
        failure = subprocess.CalledProcessError(1, ["synthetic"], stderr=b"private-test-value")
        with patch("rollout.subprocess.run", side_effect=failure):
            with self.assertRaises(ReleaseError) as context:
                command(["synthetic", "private-test-value"])
        self.assertNotIn("private-test-value", str(context.exception))

    def test_maintenance_uses_offline_utility_independent_of_running_app(self):
        with patch("rollout.command", return_value=b"") as call:
            Host({}).drain({"backend": "synthetic"})
        args = call.call_args_list[-1].args[0]
        self.assertEqual(args[1], "run")
        self.assertEqual(args[args.index("--network") + 1], "none")
        self.assertNotIn("--env-file", args)
        self.assertIn("type=volume,source=echomind_documents,target=/var/lib/echomind/documents", args)

    def test_bundle_contains_only_public_allowlist_and_is_reproducible(self):
        image = "111122223333.dkr.ecr.us-east-1.amazonaws.com/example@sha256:" + "a" * 64
        first, second = [Path(self.directory.name) / name for name in ("one.tar.gz", "two.tar.gz")]
        self.assertEqual(package(first, "a" * 40, image, image), package(second, "a" * 40, image, image))
        with tarfile.open(first) as archive:
            self.assertEqual(set(archive.getnames()), {"compose.yaml", "compose.https.yaml", "rollout.py", "manifest.json"})
            self.assertTrue(all(member.isfile() for member in archive))
        with self.assertRaises(ValueError):
            package(second, "main; unsafe", image, image)
        with self.assertRaises(ValueError):
            package(second, "a" * 40, "example:latest", image)

    def test_outside_repository_digest_is_rejected(self):
        path = Path(self.directory.name)
        (path / "manifest.json").write_text(json.dumps({"version": 1, "revision": "a" * 40,
                                                        "backend": "outside@sha256:" + "a" * 64, "proxy": "unused"}))
        with patch.dict("os.environ", {"BACKEND_REPOSITORY": "approved", "PROXY_REPOSITORY": "approved"}):
            with self.assertRaisesRegex(ReleaseError, "outside"):
                manifest(path)


class PipelineSecurityTests(unittest.TestCase):
    def setUp(self):
        self.template = yaml.load((ROOT / "deploy/aws/pipeline.yaml").read_text(), Loader=infra.CfnLoader)
        self.resources = self.template["Resources"]

    def test_trust_requires_exact_environment_subject_and_audience(self):
        for name, environment in (("BuildRole", "aws-build"), ("DeployRole", "aws-production")):
            trust = self.resources[name]["Properties"]["AssumeRolePolicyDocument"]["Statement"][0]
            conditions = trust["Condition"]["StringEquals"]
            self.assertEqual(conditions["token.actions.githubusercontent.com:aud"], "sts.amazonaws.com")
            self.assertEqual(conditions["token.actions.githubusercontent.com:sub"],
                             {"Fn::Sub": "${GitHubSubjectPrefix}:environment:" + environment})
            self.assertNotIn("*", str(trust))

    def test_deployer_cannot_run_arbitrary_shell_or_change_infrastructure(self):
        policies = self.resources["DeployRole"]["Properties"]["Policies"][0]["PolicyDocument"]["Statement"]
        self.assertEqual({item["Action"] for item in policies}, {"ssm:SendCommand", "ssm:GetCommandInvocation"})
        targets = str(policies[0]["Resource"])
        self.assertIn("document/${DeployDocument}", targets)
        self.assertIn("instance/${InstanceId}", targets)
        self.assertNotIn("AWS-RunShellScript", targets)
        self.assertNotIn("*", targets)

    def test_publisher_cannot_read_backups_or_send_commands(self):
        policy = str(self.resources["BuildRole"]["Properties"]["Policies"])
        self.assertNotIn("backups/", policy)
        self.assertNotIn("ssm:", policy)
        self.assertIn("/releases/*", policy)

    def test_ssm_parameters_and_extractor_reject_injection_links_and_secrets(self):
        document = self.resources["DeployDocument"]["Properties"]["Content"]
        for key, length in (("Revision", 40), ("BundleSha256", 64)):
            parameter = document["parameters"][key]
            self.assertEqual(parameter["interpolationType"], "ENV_VAR")
            import re
            self.assertIsNone(re.fullmatch(parameter["allowedPattern"], "a" * length + "; id"))
        script = document["mainSteps"][0]["inputs"]["runCommand"][0]["Fn::Sub"]
        self.assertNotIn("{{", script)
        self.assertNotIn("set -x", script)
        self.assertNotIn("extractall", script)
        self.assertIn("m.isfile()", script)
        self.assertIn("hashlib.sha256", script)
        subprocess.run(["bash", "-n"], input=script, text=True, check=True)
        # Execute only the isolated extractor against synthetic archives, never AWS/shell.
        code = script.split("python3 - <<'PY'\n", 1)[1].split("\nPY\n", 1)[0]
        import hashlib
        for malicious in (False, True):
            with tempfile.TemporaryDirectory() as temporary:
                bundle = Path(temporary) / "bundle.tar.gz"
                with tarfile.open(bundle, "w:gz") as archive:
                    for name in ("compose.yaml", "compose.https.yaml", "rollout.py", "manifest.json"):
                        member = tarfile.TarInfo(name)
                        payload = json.dumps({"revision": "a" * 40}).encode() if name == "manifest.json" else b"synthetic"
                        member.size = len(payload)
                        if malicious and name == "rollout.py":
                            member.type, member.linkname, member.size = tarfile.SYMTYPE, "/private", 0
                        archive.addfile(member, io.BytesIO(payload) if member.isfile() else None)
                import os
                environment = os.environ | {"WORK": temporary, "SSM_Revision": "a" * 40,
                                            "SSM_BundleSha256": hashlib.sha256(bundle.read_bytes()).hexdigest()}
                result = subprocess.run([os.sys.executable, "-c", code], env=environment, capture_output=True)
                self.assertEqual(result.returncode == 0, not malicious)

    def test_images_are_immutable_and_bucket_private_retained_encrypted(self):
        for name in ("BackendRepository", "ProxyRepository"):
            self.assertEqual(self.resources[name]["Properties"]["ImageTagMutability"], "IMMUTABLE")
        bucket = self.resources["ReleaseBucket"]
        self.assertEqual(bucket["DeletionPolicy"], "Retain")
        self.assertTrue(all(bucket["Properties"]["PublicAccessBlockConfiguration"].values()))
        self.assertEqual(bucket["Properties"]["VersioningConfiguration"]["Status"], "Enabled")
        self.assertTrue(bucket["Properties"]["BucketEncryption"])

    def test_workflow_uses_only_successful_same_repo_main_push_and_never_cancels(self):
        workflow = yaml.safe_load((ROOT / ".github/workflows/deploy-aws.yml").read_text())
        publish = workflow["jobs"]["publish"]
        for condition in ("conclusion == 'success'", "event == 'push'", "head_branch == 'main'",
                          "head_repository.full_name == github.repository", "AWS_DEPLOY_ENABLED == 'true'"):
            self.assertIn(condition, publish["if"])
        self.assertFalse(workflow["concurrency"]["cancel-in-progress"])
        self.assertEqual(workflow["jobs"]["deploy"]["needs"], "publish")
        for job in workflow["jobs"].values():
            checkout = job["steps"][0]
            self.assertEqual(checkout["with"]["ref"], "${{ github.event.workflow_run.head_sha || github.sha }}")
            self.assertFalse(checkout["with"]["persist-credentials"])
        self.assertIn("github.event_name == 'workflow_run'", workflow['jobs']['deploy']['if'])
        self.assertIn("github.ref == 'refs/heads/main'", publish['if'])
        self.assertEqual(workflow['jobs']['publish']['permissions']['actions'], 'read')

    def test_manual_publication_requires_successful_push_ci_for_current_main(self):
        revision = 'a' * 40
        repo = 'owner/repository'
        run = {'head_sha': revision, 'head_branch':'main', 'event':'push', 'conclusion':'success',
               'head_repository':{'full_name':repo}}
        for runs, allowed in (([run], True), ([], False), ([run | {'event':'pull_request'}], False),
                              ([run | {'head_repository':{'full_name':'untrusted/fork'}}], False)):
            responses = [io.BytesIO(json.dumps({'object':{'sha':revision}}).encode()),
                         io.BytesIO(json.dumps({'workflow_runs':runs}).encode())]
            with patch.dict('os.environ', {'RELEASE_REVISION':revision,'GITHUB_REPOSITORY':repo,
                                          'GITHUB_TOKEN':'synthetic-test-token'}), \
                    patch('urllib.request.urlopen', side_effect=responses):
                if allowed:
                    runpy.run_path(str(ROOT / 'deploy/pipeline/ensure_main.py'))
                else:
                    with self.assertRaises(SystemExit):
                        runpy.run_path(str(ROOT / 'deploy/pipeline/ensure_main.py'))


if __name__ == "__main__":
    unittest.main()
