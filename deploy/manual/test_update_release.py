"""Offline checks for backend-only manual updates; no AWS, Docker or credentials."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import update_release as release


class ManualUpdateTests(unittest.TestCase):
    def test_replacement_targets_only_backend(self):
        host = release.ManualHost({})
        with patch.object(host, "compose") as compose:
            host.up({"revision": "new"})
        args = compose.call_args.args
        self.assertEqual(args[-1], "backend")
        self.assertIn("--no-deps", args)
        self.assertIn("--pull", args)
        self.assertIn("never", args)

    def test_backup_failure_blocks_replacement_and_resumes_old_version(self):
        host = release.ManualHost({})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            current = root / "current.json"
            current.write_text(json.dumps({"revision": "old"}))
            with (patch.object(release, "ROOT", root),
                  patch.object(host, "preflight"), patch.object(host, "drain"),
                  patch.object(host, "resume") as resume, patch.object(host, "up") as up,
                  patch.object(host, "documents", side_effect=release.ReleaseError("backup failed"))):
                with self.assertRaisesRegex(release.ReleaseError, "previous version resumed"):
                    release.transact(host, {"revision": "new"}, current)
            up.assert_not_called()
            resume.assert_called_once_with({"revision": "old"})
            self.assertFalse((root / "pending.json").exists())
            self.assertEqual(json.loads(current.read_text()), {"revision": "old"})

    def test_backup_stays_in_private_recovery_directory(self):
        host = release.ManualHost({})
        def documents(_state, action, *, output):
            self.assertEqual(action, "backup")
            output.write(b"synthetic archive" * 1024)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(release, "ROOT", root), patch.object(host, "documents", side_effect=documents):
                host.backup({})
            archives = list((root / "manual-backups").glob("*.documents.tar"))
            self.assertEqual(len(archives), 1)
            self.assertGreater(archives[0].stat().st_size, 1024)

    def test_identity_mismatch_fails_health_check_before_commit(self):
        host = release.ManualHost({})
        host.expected_images = {"candidate": "sha256:expected"}
        host.proxy_id = "original-proxy"
        with patch.object(release.Host, "healthy"), patch.object(release, "command", side_effect=[
            json.dumps([{"Image": "sha256:other"}]), json.dumps([{"Id": "original-proxy"}]),
        ]):
            with self.assertRaisesRegex(release.ReleaseError, "identity mismatch"):
                host.healthy({"backend": "candidate"})

    def test_public_settings_are_replaced_atomically(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "deploy.env"
            path.write_text("BACKEND_IMAGE=old\n")
            release.atomic_text(path, "BACKEND_IMAGE=new\n")
            self.assertEqual(path.read_text(), "BACKEND_IMAGE=new\n")
            self.assertEqual(list(path.parent.glob(".manual-*")), [])


if __name__ == "__main__":
    unittest.main()
