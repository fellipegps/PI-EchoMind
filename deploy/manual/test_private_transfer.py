"""Offline tests: committed-source filtering, encryption and fail-closed install."""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


package = load("package_source")
prepare = load("prepare_envelope")
installer = load("install_envelope")
OPENSSL = os.environ.get("TEST_OPENSSL", "openssl")


class PrivateTransferTests(unittest.TestCase):
    def test_archive_allowlist_rejects_secrets_and_unrelated_files(self):
        for name in ("echomind-backend/.env", "echomind-backend/app/.env", "deploy/backend.env",
                     "echomind-backend/app/../.env", ".git/config", "uploads/document.pdf"):
            self.assertFalse(package.allowed(name), name)
        self.assertTrue(package.allowed("echomind-backend/app/main.py"))
        self.assertTrue(package.allowed("deploy/.env.example"))

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.cert, self.key = self.root / "recipient.pem", self.root / "recipient.key"
        subprocess.run([OPENSSL, "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                        "-subj", "/CN=synthetic-transfer", "-keyout", str(self.key), "-out", str(self.cert)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    def envelope(self):
        values = {"DATABASE_URL": "postgresql://postgres:synthetic%40password@db.owaapvfiyltapzlhosqh.supabase.co:5432/postgres",
                  "SUPABASE_URL": "https://owaapvfiyltapzlhosqh.supabase.co",
                  "SUPABASE_SECRET_KEY": "sb_secret_synthetic_offline", "GROQ_API_KEY": "gsk_synthetic_offline"}
        destination = self.root / "runtime.cms"
        with patch.object(prepare, "dotenv_values", return_value=values):
            report = prepare.prepare(self.cert, destination, OPENSSL, "aws-0-sa-east-1.pooler.supabase.com")
        return destination, report

    def test_encryption_roundtrip_preserves_password_and_production_defaults(self):
        envelope, report = self.envelope()
        self.assertNotIn(b"sb_secret_synthetic_offline", envelope.read_bytes())
        decrypted = subprocess.check_output([OPENSSL, "cms", "-decrypt", "-binary", "-inform", "DER",
                                            "-recip", str(self.cert), "-inkey", str(self.key), "-in", str(envelope)])
        values = prepare.configuration.parse_raw(decrypted.decode())
        self.assertIn("postgres.owaapvfiyltapzlhosqh", values["DATABASE_URL"])
        self.assertEqual(prepare.make_url(values["DATABASE_URL"]).password, "synthetic@password")
        self.assertEqual(values["ALLOWED_ORIGINS"], "https://echomind-front.vercel.app")
        self.assertFalse(report["plaintext_written"])

    def test_tampered_ciphertext_never_reaches_install_and_removes_transfer_keys(self):
        envelope, report = self.envelope()
        envelope.write_bytes(envelope.read_bytes() + b"tampered")
        with patch.object(installer, "TRANSFER", self.root), patch.object(installer, "private"), \
                patch.object(installer.os, "geteuid", return_value=0, create=True), \
                patch.object(installer.configuration, "install_private_file") as install:
            with self.assertRaises(ValueError):
                installer.install(report["sha256"])
            install.assert_not_called()
        self.assertFalse(self.key.exists())
        self.assertFalse(envelope.exists())

    def test_rejects_pooler_hostname_not_verified_for_project_region(self):
        with self.assertRaises(ValueError):
            prepare.prepare(self.cert, self.root / "runtime.cms", OPENSSL, "attacker.example")


if __name__ == "__main__":
    unittest.main()
