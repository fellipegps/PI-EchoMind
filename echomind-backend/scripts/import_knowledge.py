#!/usr/bin/env python3
"""Importa um template JSON de conhecimento para um tenant do EchoMind."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.database import CompanyEvent, Config, Faq, SessionLocal, utc_now  # noqa: E402
from app.rag_engine import get_rag_engine  # noqa: E402
from app import crud  # noqa: E402


log = logging.getLogger("import_knowledge")

CONFIG_FIELDS = {
    "company_name",
    "description",
    "tone_of_voice",
    "totem_voice_gender",
    "website",
    "phone",
    "address",
    "business_hours",
}
EVENT_FIELDS = {"title", "event_date", "event_type", "description"}


def normalize(text: str) -> str:
    return " ".join(text.strip().lower().split())


def load_template(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"Arquivo nao encontrado: {path}")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"JSON invalido em {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise SystemExit("O arquivo precisa conter um objeto JSON na raiz.")

    faqs = data.get("faqs", [])
    if not isinstance(faqs, list) or not faqs:
        raise SystemExit("O template precisa conter uma lista nao vazia em 'faqs'.")

    totem_count = sum(1 for item in faqs if bool(item.get("show_on_totem")))
    if totem_count > 4:
        raise SystemExit("O template nao pode marcar mais de 4 FAQs com show_on_totem=true.")

    seen_questions: set[str] = set()
    for index, item in enumerate(faqs, start=1):
        if not isinstance(item, dict):
            raise SystemExit(f"FAQ #{index} precisa ser um objeto.")
        question = str(item.get("question", "")).strip()
        answer = str(item.get("answer", "")).strip()
        if len(question) < 5 or len(answer) < 5:
            raise SystemExit(f"FAQ #{index} precisa ter question e answer com pelo menos 5 caracteres.")

        key = normalize(question)
        if key in seen_questions:
            raise SystemExit(f"Pergunta duplicada no template: {question}")
        seen_questions.add(key)

    return data


def upsert_config(db, tenant_id: str, payload: dict[str, Any] | None) -> Config | None:
    if not payload:
        return None

    if not isinstance(payload, dict):
        raise SystemExit("'config' precisa ser um objeto.")

    cfg = db.query(Config).filter(Config.tenant_id == tenant_id).first()
    if not cfg:
        cfg = Config(tenant_id=tenant_id)
        db.add(cfg)

    for field in CONFIG_FIELDS:
        if field in payload:
            setattr(cfg, field, payload[field])

    cfg.updated_at = utc_now()
    db.commit()
    db.refresh(cfg)
    return cfg


def upsert_faqs(db, tenant_id: str, rows: list[dict[str, Any]]) -> tuple[list[Faq], int, int]:
    existing = db.query(Faq).filter(Faq.tenant_id == tenant_id).all()
    by_question = {normalize(row.question): row for row in existing}

    imported: list[Faq] = []
    created = 0
    updated = 0

    for item in rows:
        question = item["question"].strip()
        key = normalize(question)
        faq = by_question.get(key)

        if faq:
            faq.answer = item["answer"].strip()
            faq.show_on_totem = bool(item.get("show_on_totem", False))
            faq.updated_at = utc_now()
            updated += 1
        else:
            faq = Faq(
                tenant_id=tenant_id,
                question=question,
                answer=item["answer"].strip(),
                show_on_totem=bool(item.get("show_on_totem", False)),
            )
            db.add(faq)
            created += 1

        imported.append(faq)

    db.commit()
    for faq in imported:
        db.refresh(faq)

    enforce_totem_limit(db, tenant_id, imported)
    crud.get_cached_faq_answers.cache_clear()
    return imported, created, updated


def enforce_totem_limit(db, tenant_id: str, imported: list[Faq]) -> None:
    active_imported_ids = {faq.id for faq in imported if faq.show_on_totem}
    active = (
        db.query(Faq)
        .filter(Faq.tenant_id == tenant_id, Faq.show_on_totem == True)
        .order_by(Faq.created_at.asc())
        .all()
    )

    if len(active) <= 4:
        return

    for faq in active:
        if len(active) <= 4:
            break
        if faq.id in active_imported_ids:
            continue
        faq.show_on_totem = False
        faq.updated_at = utc_now()
        active.remove(faq)

    if len(active) > 4:
        raise SystemExit("Nao foi possivel respeitar o limite de 4 FAQs no totem.")

    db.commit()


def upsert_events(db, tenant_id: str, rows: list[dict[str, Any]] | None) -> tuple[list[CompanyEvent], int, int]:
    if not rows:
        return [], 0, 0
    if not isinstance(rows, list):
        raise SystemExit("'events' precisa ser uma lista.")

    existing = db.query(CompanyEvent).filter(CompanyEvent.tenant_id == tenant_id).all()
    by_title_date = {(normalize(row.title), row.event_date): row for row in existing}

    imported: list[CompanyEvent] = []
    created = 0
    updated = 0

    for index, item in enumerate(rows, start=1):
        title = str(item.get("title", "")).strip()
        event_date = str(item.get("event_date", "")).strip()
        event_type = str(item.get("event_type", "")).strip()
        if not title or not event_date or not event_type:
            raise SystemExit(f"Evento #{index} precisa conter title, event_date e event_type.")

        key = (normalize(title), event_date)
        event = by_title_date.get(key)

        if event:
            for field in EVENT_FIELDS:
                if field in item:
                    setattr(event, field, item[field])
            event.updated_at = utc_now()
            updated += 1
        else:
            event = CompanyEvent(
                tenant_id=tenant_id,
                title=title,
                event_date=event_date,
                event_type=event_type,
                description=item.get("description"),
            )
            db.add(event)
            created += 1

        imported.append(event)

    db.commit()
    for event in imported:
        db.refresh(event)

    return imported, created, updated


def reindex_imported(db, tenant_id: str, faqs: list[Faq], events: list[CompanyEvent]) -> None:
    rag = get_rag_engine(db, tenant_id=tenant_id)

    for faq in faqs:
        rag.reindex_faq(faq)

    for event in events:
        rag.reindex_event(event)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Importa configuracao, FAQs e eventos de um JSON para um tenant."
    )
    parser.add_argument("--tenant-id", required=True, help="ID do usuario/tenant no Supabase Auth.")
    parser.add_argument("--file", required=True, type=Path, help="Caminho do template JSON.")
    parser.add_argument(
        "--skip-rag",
        action="store_true",
        help="Importa os dados sem reindexar o RAG. Use apenas para diagnostico.",
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    args = parse_args()
    tenant_id = args.tenant_id.strip()
    if not tenant_id:
        raise SystemExit("--tenant-id nao pode ser vazio.")

    data = load_template(args.file)
    db = SessionLocal()
    try:
        config = upsert_config(db, tenant_id, data.get("config"))
        faqs, created_faqs, updated_faqs = upsert_faqs(db, tenant_id, data["faqs"])
        events, created_events, updated_events = upsert_events(db, tenant_id, data.get("events"))

        if not args.skip_rag:
            reindex_imported(db, tenant_id, faqs, events)

        log.info("Tenant: %s", tenant_id)
        log.info("Config: %s", "atualizada" if config else "nao informada")
        log.info("FAQs: %d criadas, %d atualizadas, %d reindexadas", created_faqs, updated_faqs, len(faqs))
        log.info("Eventos: %d criados, %d atualizados, %d reindexados", created_events, updated_events, len(events))
        log.info("Importacao concluida.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
