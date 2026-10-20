"""Read-only integrity inventory inside the backend; never prints user content."""
import argparse
import json
import uuid


def check(absent_id=None):
    from sqlalchemy import text
    from app.database import engine
    from app.document_storage import DocumentStorage

    if absent_id is not None and str(uuid.UUID(absent_id)) != absent_id:
        raise ValueError("Invalid fixture identity.")
    storage = DocumentStorage()
    valid = missing = invalid = 0
    with engine.connect() as connection, connection.begin():
        connection.execute(text("SET TRANSACTION READ ONLY"))
        connection.execute(text("SET LOCAL statement_timeout = '10s'"))
        rows = connection.execute(text(
            "SELECT id,tenant_id,sha256,size_bytes FROM public.documents WHERE status='ready'"
        )).mappings().all()
        for row in rows:
            path = storage.directory(row["tenant_id"], row["id"]) / "original.bin"
            if not path.exists():
                missing += 1
                continue
            try:
                storage.read_original(tenant_id=row["tenant_id"], document_id=row["id"],
                                      digest=row["sha256"], size=row["size_bytes"])
                valid += 1
            except Exception:
                invalid += 1
        fixture_absent = (connection.execute(text(
            "SELECT count(*) FROM public.documents WHERE id=:id"
        ), {"id": absent_id}).scalar_one() == 0) if absent_id else None
    return {"ready_documents": len(rows), "valid_originals": valid,
            "missing_originals": missing, "invalid_originals": invalid,
            "original_files": len(list(storage.root.glob("*/*/original.bin"))),
            "queued_jobs": len(list(storage.jobs())), "draining": storage.draining,
            "fixture_absent": fixture_absent}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--absent-id")
    args = parser.parse_args()
    try:
        report = check(args.absent_id)
        print(json.dumps(report))
        raise SystemExit(int(bool(report["missing_originals"] or report["invalid_originals"]
                                  or report["draining"] or report["queued_jobs"]
                                  or report["fixture_absent"] is False)))
    except Exception:
        print("Original integrity inventory unavailable; private diagnostics suppressed.")
        raise SystemExit(1) from None
