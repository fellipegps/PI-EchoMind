"""Production checks use synthetic credentials and never contact external APIs."""

from contextlib import nullcontext
import importlib.util
import os
from pathlib import Path
import runpy
import subprocess
import sys

import pytest

from app.runtime_config import ProductionConfigurationError, load_runtime_environment, validate_production


ROOT = Path(__file__).resolve().parents[3]
DEPLOY = ROOT / "deploy"


@pytest.fixture
def production_config():
    return {
        "ECHOMIND_ENV": "production",
        "DATABASE_URL": "postgresql://synthetic:p%40ss%2F%25word@db.example.test:5432/postgres?sslmode=require",
        "SUPABASE_URL": "https://synthetic.supabase.co",
        "SUPABASE_SECRET_KEY": "sb_secret_synthetic-$-#-only",
        "GROQ_API_KEY": "gsk_synthetic_offline_only",
        "ALLOWED_ORIGINS": "https://app.example.test,https://second.example.test",
    }


def test_valid_config_preserves_literal_credentials(production_config):
    original = production_config.copy()
    validate_production(production_config)
    assert production_config == original


@pytest.mark.parametrize("name,value", [
    ("DATABASE_URL", "sqlite:///:memory:"),
    ("DATABASE_URL", "postgresql://u:secret@db.example.test/db?sslmode=disable"),
    ("DATABASE_URL", "postgresql://u:secret@db.example.test/db?sslmode=require&sslmode=disable"),
    ("DATABASE_URL", "postgresql://u:secret@db.example.test:invalid/db?sslmode=require"),
    ("DATABASE_URL", "postgresql://u:secret@db.example.test/db"),
    ("SUPABASE_URL", "http://synthetic.supabase.co"),
    ("SUPABASE_URL", "https://user:private@synthetic.supabase.co"),
    ("SUPABASE_URL", "https://synthetic.supabase.co/path"),
    ("SUPABASE_URL", "https://synthetic.supabase.co:invalid"),
    ("ALLOWED_ORIGINS", "*"),
    ("ALLOWED_ORIGINS", "https://*.vercel.app"),
    ("ALLOWED_ORIGINS", "http://localhost:3000"),
    ("ALLOWED_ORIGINS", "https://app.example.test,"),
    ("SUPABASE_SECRET_KEY", "sb_publishable_synthetic"),
    ("SUPABASE_SECRET_KEY", "{{resolve:secretsmanager:example:SecretString:key}}"),
    ("GROQ_API_KEY", "CHANGE_ME"),
    ("GROQ_API_KEY", "gsk_private\nsecond-line"),
    ("UVICORN_WORKERS", "2"),
    ("WEB_CONCURRENCY", "0"),
    ("RATE_LIMIT_INSTANCE_COUNT", "2"),
    ("EMBEDDING_DIM", "768"),
    ("RERANKER_ENABLED", "typo"),
    ("RERANKER_ENABLED", "on"),
    ("RAG_WARMUP_ENABLED", "off"),
    ("CHAT_RATE_LIMIT_REQUESTS", "private-invalid-number"),
    ("MAX_DOCUMENT_SIZE_MB", "0"),
    ("RERANKER_TIMEOUT_SECONDS", "nan"),
    ("SIMILARITY_THRESHOLD", "secret-not-number"),
])
def test_bad_config_names_only(production_config, name, value):
    production_config[name] = value
    with pytest.raises(ProductionConfigurationError) as caught:
        validate_production(production_config)
    diagnostic = str(caught.value)
    assert name in diagnostic
    # Short scalar values can also be substrings of ordinary diagnostic words.
    if len(value) > 3:
        assert value not in diagnostic
    assert production_config["GROQ_API_KEY"] not in diagnostic


def test_missing_config_lists_all_required_variables():
    with pytest.raises(ProductionConfigurationError) as caught:
        validate_production({})
    for name in ("DATABASE_URL", "SUPABASE_URL", "SUPABASE_SECRET_KEY", "GROQ_API_KEY", "ALLOWED_ORIGINS"):
        assert name in str(caught.value)


def test_production_does_not_load_dotenv(monkeypatch, production_config):
    import dotenv
    monkeypatch.setattr(dotenv, "load_dotenv", lambda: pytest.fail("Production must not read .env"))
    for name, value in production_config.items():
        monkeypatch.setenv(name, value)
    load_runtime_environment()


def test_development_still_loads_dotenv(monkeypatch):
    import dotenv
    calls = []
    monkeypatch.setenv("ECHOMIND_ENV", "development")
    monkeypatch.setattr(dotenv, "load_dotenv", lambda: calls.append(True))
    load_runtime_environment()
    assert calls == [True]


def test_invalid_mode_does_not_echo_value(monkeypatch):
    monkeypatch.setenv("ECHOMIND_ENV", "private-bad-mode")
    with pytest.raises(ProductionConfigurationError, match="^ECHOMIND_ENV inválido.$"):
        load_runtime_environment()


def test_api_rejects_bad_production_config_before_connecting(production_config):
    environment = os.environ | production_config | {"DATABASE_URL": "private-invalid-database-url"}
    result = subprocess.run([sys.executable, "-c", "import app.main"], env=environment,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode != 0
    assert "Configuração de produção inválida" in result.stderr
    assert "private-invalid-database-url" not in result.stderr
    assert production_config["GROQ_API_KEY"] not in result.stderr


def test_alembic_preserves_percent_encoded_password(monkeypatch, production_config):
    from alembic import context
    from alembic.config import Config
    from sqlalchemy.engine import make_url

    captured = {}
    monkeypatch.setenv("DATABASE_URL", production_config["DATABASE_URL"])
    monkeypatch.setattr(context, "config", Config(), raising=False)
    monkeypatch.setattr(context, "is_offline_mode", lambda: True)
    monkeypatch.setattr(context, "configure", lambda **kwargs: captured.update(kwargs))
    monkeypatch.setattr(context, "begin_transaction", nullcontext)
    monkeypatch.setattr(context, "run_migrations", lambda: None)
    runpy.run_path(str(Path(__file__).resolve().parents[2] / "alembic/env.py"))
    assert captured["url"] == production_config["DATABASE_URL"]
    assert make_url(captured["url"]).password == "p@ss/%word"


@pytest.fixture
def installer():
    spec = importlib.util.spec_from_file_location("configure_runtime", DEPLOY / "operations/configure_runtime.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_raw_file_and_installation_round_trip(installer, production_config, tmp_path):
    if os.name != "posix":
        pytest.skip("Host Linux permissions")
    source = tmp_path / "source.env"
    source.write_text("\n".join(f"{k}={v}" for k, v in production_config.items()), encoding="utf-8")
    source.chmod(0o600)
    destination = tmp_path / "private/backend.env"
    values = installer.read_private_file(source)
    installer.install_private_file(destination, values)
    assert destination.stat().st_mode & 0o777 == 0o600
    assert destination.parent.stat().st_mode & 0o777 == 0o700
    installed = installer.read_private_file(destination)
    for name, value in production_config.items():
        assert installed[name] == value


def test_installer_refuses_checkout_and_symlinks(installer, tmp_path):
    with pytest.raises(installer.PrivateConfigurationError, match="fora do repositório"):
        installer.outside_checkout(DEPLOY / "backend.env")
    if os.name == "posix":
        target = tmp_path / "target"
        target.mkdir()
        link = tmp_path / "linked"
        link.symlink_to(target, target_is_directory=True)
        with pytest.raises(installer.PrivateConfigurationError, match="links simbólicos"):
            installer.outside_checkout(link / "backend.env")


def test_installer_rejects_exposed_files_and_directories(installer, production_config, tmp_path):
    if os.name != "posix":
        pytest.skip("Host Linux permissions")
    source = tmp_path / "source.env"
    source.write_text("", encoding="utf-8")
    source.chmod(0o644)
    with pytest.raises(installer.PrivateConfigurationError, match="permissões"):
        installer.read_private_file(source)
    directory = tmp_path / "exposed"
    directory.mkdir(mode=0o755)
    with pytest.raises(installer.PrivateConfigurationError, match="permissões"):
        installer.install_private_file(directory / "backend.env", production_config)


def test_rotation_preserves_old_file_if_invalid(installer, production_config, tmp_path):
    if os.name != "posix":
        pytest.skip("Host Linux permissions")
    destination = tmp_path / "private/backend.env"
    installer.install_private_file(destination, production_config)
    before = destination.read_bytes()
    with pytest.raises(installer.PrivateConfigurationError, match="já existe"):
        installer.install_private_file(destination, production_config)
    with pytest.raises(installer.runtime_config.ProductionConfigurationError):
        installer.install_private_file(destination, production_config | {"GROQ_API_KEY": "CHANGE_ME"}, replace=True)
    assert destination.read_bytes() == before
    rotated = production_config | {"GROQ_API_KEY": "gsk_synthetic_rotated"}
    installer.install_private_file(destination, rotated, replace=True)
    assert installer.read_private_file(destination)["GROQ_API_KEY"] == rotated["GROQ_API_KEY"]


@pytest.mark.parametrize("contents", ['KEY="quoted"', "KEY=x\nKEY=y", "bad key=x", "export KEY=x", "KEY=x\0"])
def test_raw_parser_rejects_ambiguous_format(installer, contents):
    with pytest.raises(installer.PrivateConfigurationError):
        installer.parse_raw(contents)


def test_installer_rejects_unknown_vars_and_environment_injection(installer, production_config):
    with pytest.raises(installer.PrivateConfigurationError):
        installer.validated_config(production_config | {"LD_PRELOAD": "private-value"})
    with pytest.raises(installer.PrivateConfigurationError):
        installer.validated_config(production_config | {"GROQ_LLM_MODEL": "model\nLD_PRELOAD=bad"})


def test_cli_diagnostics_never_print_secret(installer, production_config, monkeypatch, capsys):
    for name, value in production_config.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("DATABASE_URL", "private-invalid-url")
    monkeypatch.setattr(sys, "argv", ["configure_runtime.py", "--from-environment"])
    assert installer.main() == 1
    output = capsys.readouterr().out
    assert "DATABASE_URL" in output
    assert "private-invalid-url" not in output
    assert production_config["SUPABASE_SECRET_KEY"] not in output


def test_cli_success_has_no_values(installer, production_config, monkeypatch, capsys):
    for name, value in production_config.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(sys, "argv", ["configure_runtime.py", "--from-environment"])
    assert installer.main() == 0
    output = capsys.readouterr().out
    assert "validada" in output
    for value in production_config.values():
        assert value not in output
