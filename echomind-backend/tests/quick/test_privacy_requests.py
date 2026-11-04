from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

from app.database import Interaction
from app.privacy_requests import delete_chat_records, export_chat_records


@pytest.fixture
def selected_interactions(db):
    now = datetime(2026, 10, 27, 12, tzinfo=timezone.utc)
    db.add_all([
        Interaction(id="selected-a", tenant_id="institution-a", question="Texto sintético reservado", answer="Resposta sintética", asked_at=now, feedback_helpful=True),
        Interaction(id="keep-a", tenant_id="institution-a", question="Texto sintético reservado", asked_at=now),
        Interaction(id="foreign-b", tenant_id="institution-b", question="Texto sintético reservado", asked_at=now),
    ])
    db.flush()
    return ["selected-a"]


def test_preview_and_deletion_are_exact_and_tenant_scoped(db, selected_interactions):
    assert delete_chat_records(db, tenant_id="institution-a", interaction_ids=selected_interactions) == 1
    assert db.query(Interaction).count() == 3
    assert delete_chat_records(db, tenant_id="institution-a", interaction_ids=selected_interactions, apply=True) == 1
    assert {row.id for row in db.query(Interaction).all()} == {"keep-a", "foreign-b"}


@pytest.mark.parametrize("ids", [["foreign-b"], ["selected-a", "foreign-b"], ["selected-a", "missing"]])
def test_missing_or_foreign_selection_cannot_cause_partial_deletion(db, selected_interactions, ids):
    with pytest.raises(ValueError, match="indisponíveis"):
        delete_chat_records(db, tenant_id="institution-a", interaction_ids=ids, apply=True)
    assert db.query(Interaction).count() == 3


def test_export_contains_only_selected_fields_and_requires_human_review(db, selected_interactions):
    payload = export_chat_records(db, tenant_id="institution-a", interaction_ids=selected_interactions)
    assert payload["requires_review"] is True
    assert payload["scope"] == "selected_interactions_only"
    assert len(payload["interactions"]) == 1
    assert payload["interactions"][0] == {
        "id": "selected-a", "question": "Texto sintético reservado", "answer": "Resposta sintética",
        "asked_at": "2026-10-27T12:00:00", "feedback_helpful": True, "was_answered": True,
    }
    assert "institution-b" not in json.dumps(payload)
    assert "tenant_id" not in payload["interactions"][0]
    assert db.query(Interaction).count() == 3


@pytest.mark.parametrize("tenant,ids", [
    ("", ["id"]), ("   ", ["id"]), ("institution-a", []), ("institution-a", "id"),
    ("institution-a", [True]), ("institution-a", [" "]), ("institution-a", ["x" * 129]),
    ("institution-a", ["same", "same"]), ("institution-a", [str(value) for value in range(101)]),
])
def test_invalid_selection_is_rejected(db, tenant, ids):
    with pytest.raises(ValueError):
        export_chat_records(db, tenant_id=tenant, interaction_ids=ids)


@pytest.fixture
def tool(tmp_path, monkeypatch):
    source = Path(__file__).resolve().parents[2] / "scripts/manage_chat_data.py"
    spec = importlib.util.spec_from_file_location("manage_chat_data", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path / "checkout")
    return module


def test_cli_preview_export_and_apply_never_print_contents(tool, db, selected_interactions, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("app.database.SessionLocal", sessionmaker(bind=db.connection(), join_transaction_mode="create_savepoint"))
    selection = tmp_path / "selection.json"
    selection.write_text(json.dumps({"interaction_ids": selected_interactions}), encoding="utf-8")
    args = ["--tenant-id", "institution-a", "--selection-file", str(selection)]
    assert tool.main(args) == 0
    assert json.loads(capsys.readouterr().out) == {"selected_interactions": 1, "applied": False, "exported": False}
    output = tmp_path / "checkout/.privacy-requests/request.json"
    assert tool.main([*args, "--export-to", str(output)]) == 0
    logs = capsys.readouterr()
    assert "reservado" not in logs.out + logs.err and "selected-a" not in logs.out + logs.err
    assert json.loads(output.read_text(encoding="utf-8"))["interactions"][0]["id"] == "selected-a"
    if os.name == "posix":
        assert output.stat().st_mode & 0o777 == 0o600
        assert output.parent.stat().st_mode & 0o777 == 0o700
    assert tool.main([*args, "--apply"]) == 0
    assert json.loads(capsys.readouterr().out)["applied"] is True
    assert db.query(Interaction).count() == 2


def test_export_never_overwrites_or_writes_into_versioned_folders(tool, db, selected_interactions, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("app.database.SessionLocal", sessionmaker(bind=db.connection(), join_transaction_mode="create_savepoint"))
    selection = tmp_path / "selection.json"
    selection.write_text(json.dumps({"interaction_ids": selected_interactions}), encoding="utf-8")
    output = tmp_path / "existing.json"
    output.write_text("Preserve existing file", encoding="utf-8")
    args = ["--tenant-id", "institution-a", "--selection-file", str(selection), "--export-to"]
    assert tool.main([*args, str(output)]) == 1
    assert output.read_text(encoding="utf-8") == "Preserve existing file"
    forbidden = tmp_path / "checkout/docs/request.json"
    assert tool.main([*args, str(forbidden)]) == 1
    assert not forbidden.exists()
    logs = capsys.readouterr()
    assert "reservado" not in logs.out + logs.err
    assert db.query(Interaction).count() == 3


def test_invalid_input_and_backend_errors_do_not_leak_private_details(tool, tmp_path, monkeypatch, capsys):
    selection = tmp_path / "selection.json"
    selection.write_text('{"question":"private text"}', encoding="utf-8")
    args = ["--tenant-id", "institution-a", "--selection-file", str(selection)]
    assert tool.main(args) == 1
    selection.write_text('{"interaction_ids":["id"]}', encoding="utf-8")
    def failing_session():
        raise RuntimeError("private DSN and personal text")
    monkeypatch.setattr("app.database.SessionLocal", failing_session)
    assert tool.main(args) == 1
    output = capsys.readouterr()
    assert "private" not in output.err and "personal" not in output.err


def test_export_and_delete_cannot_be_requested_together(tool, tmp_path):
    with pytest.raises(SystemExit) as error:
        tool.main(["--tenant-id", "a", "--selection-file", "selection.json", "--apply", "--export-to", str(tmp_path / "request.json")])
    assert error.value.code == 2


def test_failed_export_removes_only_its_new_partial_file(tool, tmp_path):
    output = tmp_path / "private/request.json"
    with pytest.raises(TypeError):
        tool.write_private_export(output, {"invalid": object()})
    assert not output.exists()


def test_private_folder_cannot_redirect_exports_into_versioned_source(tool, tmp_path):
    if os.name != "posix":
        pytest.skip("Symlink permissions are tested in the Linux container")
    root = tool.PROJECT_ROOT
    (root / "docs").mkdir(parents=True)
    (root / ".privacy-requests").symlink_to(root / "docs", target_is_directory=True)
    with pytest.raises(ValueError):
        tool.private_export_path(root / ".privacy-requests/request.json")
