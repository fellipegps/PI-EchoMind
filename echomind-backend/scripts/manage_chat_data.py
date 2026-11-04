"""Atende seleção revisada de conversas: prévia, exportação privada ou exclusão."""
import argparse
import json
import os
from pathlib import Path
import sys

BACKEND = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND.parent if BACKEND.name == "echomind-backend" else BACKEND
sys.path.insert(0, str(BACKEND))


def read_selection(path: Path) -> list[str]:
    if path.stat().st_size > 65536:
        raise ValueError("Seleção grande demais.")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or set(value) != {"interaction_ids"}:
        raise ValueError("Use somente interaction_ids na seleção.")
    return value["interaction_ids"]


def private_export_path(path: Path) -> Path:
    target = path.resolve()
    root = PROJECT_ROOT.resolve()
    private = root / ".privacy-requests"
    if target == root or (root in target.parents and private not in target.parents):
        raise ValueError("Exporte fora do projeto ou na pasta privada .privacy-requests.")
    return target


def write_private_export(path: Path, payload: dict) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(payload, output, ensure_ascii=False, indent=2)
            output.write("\n")
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--selection-file", required=True, type=Path, help="JSON privado com interaction_ids já conferidos.")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--export-to", type=Path, help="Cria arquivo privado para revisão, sem sobrescrever.")
    action.add_argument("--apply", action="store_true", help="Exclui definitivamente apenas as interações selecionadas.")
    args = parser.parse_args(argv)
    try:
        ids = read_selection(args.selection_file)
        destination = private_export_path(args.export_to) if args.export_to else None
        # --help não importa a aplicação nem carrega configuração ou credenciais.
        from app.database import SessionLocal
        from app.privacy_requests import delete_chat_records, export_chat_records
        from sqlalchemy import text

        with SessionLocal() as db:
            if db.bind.dialect.name == "postgresql":
                db.execute(text("SET LOCAL statement_timeout = '20s'"))
                db.execute(text("SET LOCAL lock_timeout = '3s'"))
            if destination:
                payload = export_chat_records(db, tenant_id=args.tenant_id, interaction_ids=ids)
                write_private_export(destination, payload)
                count = len(payload["interactions"])
                db.rollback()
            else:
                count = delete_chat_records(db, tenant_id=args.tenant_id, interaction_ids=ids, apply=args.apply)
                if args.apply:
                    db.commit()
                else:
                    db.rollback()
    except Exception:
        # Nem conteúdo pessoal, DSN, identificadores ou caminhos privados entram no diagnóstico.
        print("Não foi possível concluir. Confira a instituição, a seleção e o destino privado; nenhum arquivo existente é sobrescrito.", file=sys.stderr)
        return 1
    print(json.dumps({"selected_interactions": count, "applied": args.apply, "exported": destination is not None}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
