#!/usr/bin/env python3
"""
seed.py – Popula o banco com dados iniciais e indexa no pgvector.

Uso (dentro do container ou com banco local):
    python seed.py

O script é idempotente: se os dados já existirem, pula a inserção.
"""

import os
import sys
import json
import uuid
import logging
from datetime import datetime

# Garante que o pacote app seja encontrado
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.database import SessionLocal, engine, Base, Faq, CompanyEvent, Config

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger("seed")


# ─── Dados de seed ────────────────────────────────────────────────────────────

SEED_CONFIG = {
    "company_name": "UniEVANGÉLICA",
    "description": (
        "A UniEVANGÉLICA é uma instituição de ensino superior localizada em Anápolis, Goiás. "
        "Oferece cursos de graduação, pós-graduação, extensão e pesquisa nas áreas de saúde, "
        "exatas, humanas e tecnologia."
    ),
    "tone_of_voice": "profissional e cordial",
    "totem_voice_gender": "feminina",
    "website": "https://www.unievangelica.edu.br",
    "phone": "(62) 3310-6600",
    "address": "Av. Universitária Km 3,5 - Cidade Universitária, Anápolis - GO, 75083-515",
    "business_hours": "Segunda a Sexta: 7h30 às 22h | Sábados: 7h30 às 12h",
}

SEED_FAQS = [
    {
        "question": "Como faço minha matrícula?",
        "answer": (
            "A matrícula pode ser realizada de forma presencial na Secretaria Acadêmica "
            "(Bloco A, térreo) ou pelo Portal do Aluno em unievangelica.edu.br/portal. "
            "Você precisará apresentar RG, CPF, comprovante de residência, histórico do "
            "ensino médio e foto 3x4 recente. O prazo de matrícula segue o calendário "
            "acadêmico vigente."
        ),
        "show_on_totem": True,
    },
    {
        "question": "Quais são os horários da secretaria?",
        "answer": (
            "A Secretaria Acadêmica funciona de segunda a sexta-feira das 7h30 às 21h30, "
            "e aos sábados das 7h30 às 11h30. Nos feriados e recessos acadêmicos o "
            "atendimento pode ser reduzido — consulte o mural do bloco A."
        ),
        "show_on_totem": True,
    },
    {
        "question": "Como solicitar meu histórico escolar?",
        "answer": (
            "O histórico escolar pode ser solicitado pelo Portal do Aluno (unievangelica.edu.br/portal) "
            "na seção 'Documentos'. O prazo de emissão é de até 5 dias úteis. "
            "Para retirada presencial, compareça à Secretaria Acadêmica com seu RG ou carteirinha. "
            "Documentos urgentes têm taxa adicional conforme tabela disponível na secretaria."
        ),
        "show_on_totem": True,
    },
    {
        "question": "Como acessar o portal do aluno?",
        "answer": (
            "Acesse unievangelica.edu.br/portal e faça login com sua matrícula (RA) e senha. "
            "Na primeira vez, sua senha padrão é sua data de nascimento no formato DDMMAAAA. "
            "Caso tenha dificuldades, clique em 'Esqueci minha senha' ou dirija-se ao "
            "setor de TI no Bloco D, sala 104."
        ),
        "show_on_totem": True,
    },
    {
        "question": "Onde fica a biblioteca?",
        "answer": (
            "A Biblioteca Central fica no Bloco B, 1º andar. Funciona de segunda a "
            "sexta das 7h às 22h e sábados das 7h às 12h. Para empréstimo de livros, "
            "apresente sua carteirinha de estudante. O acervo digital está disponível "
            "24h pelo Portal Pergamum no site da instituição."
        ),
        "show_on_totem": False,
    },
    {
        "question": "Como solicitar bolsa de estudo ou desconto?",
        "answer": (
            "A UniEVANGÉLICA oferece bolsas pelo ProUni, FIES e pelo programa interno "
            "de bolsas socioeconômicas. Para bolsas internas, inscreva-se na Comissão "
            "de Assistência Estudantil (CAE), localizada no Bloco A, sala 12. "
            "O processo seletivo ocorre no início de cada semestre. Traga RG, CPF e "
            "comprovante de renda familiar."
        ),
        "show_on_totem": False,
    },
    {
        "question": "Quais são os documentos necessários para o FIES?",
        "answer": (
            "Para o FIES você precisará de: RG e CPF do estudante e do fiador, "
            "comprovante de renda familiar dos últimos 3 meses, comprovante de residência, "
            "histórico escolar do ensino médio, comprovante de matrícula emitido pela secretaria "
            "e número do ENEM dos últimos 5 anos com nota acima de 450 pontos. "
            "A solicitação é feita pelo site do MEC (fies.mec.gov.br)."
        ),
        "show_on_totem": False,
    },
    {
        "question": "Como chego à universidade de ônibus?",
        "answer": (
            "As linhas de ônibus que atendem a UniEVANGÉLICA são: 101 (Centro → Cidade Universitária), "
            "204 (Jundiaí → Universitária) e 315 (JK → Universitária). "
            "Consulte horários atualizados no aplicativo da RMTC ou no site rmtcgoiania.com.br. "
            "O ponto final fica na entrada principal da universidade, na Av. Universitária."
        ),
        "show_on_totem": False,
    },
]

SEED_EVENTS = [
    {
        "title": "Semana Acadêmica de Medicina",
        "event_date": "2025-08-20",
        "event_type": "palestra",
        "description": "Palestras, workshops e apresentações de casos clínicos para alunos do curso de Medicina. Auditório Central, Bloco E.",
    },
    {
        "title": "Processo Seletivo 2025/2 — Vestibular",
        "event_date": "2025-07-13",
        "event_type": "outro",
        "description": "Aplicação das provas do vestibular para o 2º semestre de 2025. Inscrições até 30/06/2025 pelo site.",
    },
    {
        "title": "Recesso de Julho",
        "event_date": "2025-07-07",
        "event_type": "feriado",
        "description": "Recesso acadêmico e administrativo. A secretaria funcionará em horário reduzido (9h às 14h).",
    },
    {
        "title": "Workshop de Inovação e Startups",
        "event_date": "2025-09-05",
        "event_type": "workshop",
        "description": "Workshop sobre empreendedorismo e criação de startups, promovido pelo Núcleo de Inovação. Vagas limitadas — inscrições no portal.",
    },
]


# ─── Funções de seed ─────────────────────────────────────────────────────────

def seed_config(db) -> Config:
    existing = db.query(Config).first()
    if existing:
        log.info("⏭️  Config já existe — pulando.")
        return existing

    cfg = Config(id=str(uuid.uuid4()), **SEED_CONFIG)
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    log.info(f"✅ Config criada: {cfg.company_name}")
    return cfg


def seed_faqs(db) -> list[Faq]:
    existing_count = db.query(Faq).count()
    if existing_count > 0:
        log.info(f"⏭️  FAQs já existem ({existing_count} registros) — pulando.")
        return db.query(Faq).all()

    faqs = []
    for data in SEED_FAQS:
        faq = Faq(id=str(uuid.uuid4()), **data)
        db.add(faq)
        faqs.append(faq)

    db.commit()
    log.info(f"✅ {len(faqs)} FAQs criadas.")
    return faqs


def seed_events(db) -> list[CompanyEvent]:
    existing_count = db.query(CompanyEvent).count()
    if existing_count > 0:
        log.info(f"⏭️  Eventos já existem ({existing_count} registros) — pulando.")
        return db.query(CompanyEvent).all()

    events = []
    for data in SEED_EVENTS:
        event = CompanyEvent(id=str(uuid.uuid4()), **data)
        db.add(event)
        events.append(event)

    db.commit()
    log.info(f"✅ {len(events)} eventos criados.")
    return events


def seed_rag(db, faqs: list[Faq], events: list[CompanyEvent], config: Config):
    """Indexa todos os registros no pgvector via RAGEngine."""
    log.info("🔄 Iniciando indexação RAG no pgvector...")

    try:
        from app.rag_engine import RAGEngine
        engine_rag = RAGEngine(db)

        for faq in faqs:
            try:
                engine_rag.index_faq(faq)
                log.info(f"  📌 FAQ indexada: {faq.question[:60]}...")
            except Exception as e:
                log.warning(f"  ⚠️  Falha ao indexar FAQ {faq.id}: {e}")

        for event in events:
            try:
                engine_rag.index_event(event)
                log.info(f"  📌 Evento indexado: {event.title}")
            except Exception as e:
                log.warning(f"  ⚠️  Falha ao indexar evento {event.id}: {e}")

        log.info("✅ Indexação RAG concluída.")

    except Exception as e:
        log.error(
            f"❌ Erro ao gerar embeddings: {e}\n"
            "   → O modelo FastEmbed será baixado automaticamente na primeira execução.\n"
            "   → Os dados foram salvos no banco. Rode o seed novamente se o erro persistir."
        )


# ─── Entrypoint ──────────────────────────────────────────────────────────────

def main():
    log.info("🌱 Iniciando seed do EchoMind...")

    # Garante que as tabelas existam (caso não use Alembic)
    Base.metadata.create_all(bind=engine)

    # Verifica se pgvector está habilitado
    with engine.connect() as conn:
        try:
            conn.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))
            log.info("✅ Extensão pgvector detectada.")
        except Exception:
            log.warning("⚠️  pgvector não encontrado. Execute: CREATE EXTENSION vector;")

    db = SessionLocal()
    try:
        config = seed_config(db)
        faqs   = seed_faqs(db)
        events = seed_events(db)
        seed_rag(db, faqs, events, config)
    finally:
        db.close()

    log.info("🎉 Seed concluído com sucesso!")
    log.info("")
    log.info("   Próximos passos:")
    log.info("   1. Acesse http://localhost:8000/docs para explorar a API")
    log.info("   2. Teste o chat: POST /chat { 'message': 'Como faço minha matrícula?' }")
    log.info("   3. Veja as FAQs: GET /faqs")


if __name__ == "__main__":
    main()
