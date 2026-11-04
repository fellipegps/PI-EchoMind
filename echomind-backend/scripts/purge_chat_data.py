"""Descarte operacional: prévia por padrão; exclusão somente com --apply."""

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def positive_days(value: str) -> int:
    days = int(value)
    if not 1 <= days <= 36500:
        raise argparse.ArgumentTypeError("Use um prazo entre 1 e 36500 dias.")
    return days


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--days", type=positive_days, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not args.tenant_id.strip():
        parser.error("Informe uma instituição.")

    cutoff = datetime.now(timezone.utc) - timedelta(days=args.days)
    try:
        # --help não carrega configuração; falhas de configuração também são sanitizadas.
        from app.database import SessionLocal
        from app.privacy_retention import purge_chat_data

        with SessionLocal() as db:
            counts = purge_chat_data(
                db, tenant_id=args.tenant_id, cutoff=cutoff, apply=args.apply,
            )
            if args.apply:
                db.commit()
            else:
                db.rollback()
    except Exception:
        # Exceções SQL podem incluir conteúdo pessoal e credenciais.
        print("Não foi possível concluir o descarte. Verifique o ambiente e o banco.", file=sys.stderr)
        return 1
    print(json.dumps({"applied": args.apply, "cutoff": cutoff.isoformat(), "counts": counts}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
