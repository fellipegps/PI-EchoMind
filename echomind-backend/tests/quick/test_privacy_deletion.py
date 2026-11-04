"""Eliminação de pergunta e seus derivados, sem afetar outros titulares/tenants."""
from app.database import UnansweredQuestion, UnansweredSuppression


def test_delete_question_removes_only_its_tenant_scoped_suppressions(client, db):
    for question_id, tenant in [("privacy-target", "test-admin"), ("privacy-other", "test-admin"), ("privacy-foreign", "other")]:
        db.add(UnansweredQuestion(id=question_id, tenant_id=tenant, canonical_question="Pergunta sintética"))
        db.add(UnansweredSuppression(tenant_id=tenant, question_id=question_id, fingerprint="a" * 64))
    # Even malformed cross-tenant references must not expand a deletion's scope.
    db.add(UnansweredSuppression(tenant_id="other", question_id="privacy-target", fingerprint="b" * 64))
    db.flush()
    assert client.delete("/unanswered/privacy-foreign").status_code == 404
    assert db.query(UnansweredSuppression).count() == 4
    assert client.delete("/unanswered/privacy-target").status_code == 204
    assert db.query(UnansweredQuestion).count() == 2
    assert db.query(UnansweredSuppression).count() == 3
    assert db.query(UnansweredSuppression).filter_by(tenant_id="test-admin", question_id="privacy-target").count() == 0
    assert db.query(UnansweredSuppression).filter_by(tenant_id="other", question_id="privacy-target").count() == 1
    assert client.delete("/unanswered/privacy-target").status_code == 404
