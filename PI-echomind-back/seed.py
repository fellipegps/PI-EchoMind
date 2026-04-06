import asyncio
from sqlalchemy import text, select
from app.core.database import AsyncSessionLocal, init_db
from app.services.faq_service import FAQService
from app.schemas.faq import FAQCreate
from app.models.event import Event
from app.models.admin import Admin
from app.core.security import get_password_hash
from datetime import datetime, timedelta

# Importa todos os modelos para o create_all funcionar
import app.models  # noqa: F401


async def seed():
    # Garante que as tabelas existam antes de inserir dados
    await init_db()

    async with AsyncSessionLocal() as db:
        # ── Admin padrão ───────────────────────────────────────────────────────
        print("👤 Verificando admin padrão...")
        result = await db.execute(select(Admin).where(Admin.username == "admin"))
        existing_admin = result.scalar_one_or_none()

        if existing_admin:
            print("✅ Admin já existe, pulando criação.")
        else:
            admin = Admin(
                username="admin",
                hashed_password=get_password_hash("admin123"),
            )
            db.add(admin)
            await db.commit()
            print("✅ Admin criado — usuário: admin | senha: admin123")

        # ── FAQs ──────────────────────────────────────────────────────────────
        print("\n🧹 Limpando FAQs antigas...")
        await db.execute(text("TRUNCATE TABLE faqs CASCADE;"))
        await db.commit()

        print("🌱 Inserindo FAQs...")
        faqs = [
            FAQCreate(question="Onde fica a secretaria?", answer="A secretaria central fica no Bloco A, térreo. Atendimento das 08h às 22h."),
            FAQCreate(question="Onde fica o Restaurante Universitário (RU)?", answer="O RU está localizado atrás do Bloco B. Almoço: 11h às 13h30. Jantar: 17h30 às 19h."),
            FAQCreate(question="Onde é o Laboratório de Informática 3?", answer="O Lab 3 fica no Bloco D, segundo andar, sala 204."),
            FAQCreate(question="Onde encontro o Diretório Acadêmico (DA)?", answer="O DA fica no Centro de Convivência, ao lado da lanchonete principal."),
            FAQCreate(question="Como emitir o histórico escolar?", answer="Acesse o Portal do Aluno, vá em 'Documentos' e selecione 'Histórico'. Também pode ser solicitado na secretaria."),
            FAQCreate(question="Como trancar o semestre?", answer="O trancamento é feito via protocolo no Portal do Aluno. Verifique o prazo no calendário acadêmico."),
            FAQCreate(question="Como solicitar aproveitamento de disciplinas?", answer="Anexe ementa e histórico da faculdade anterior no menu 'Protocolos > Aproveitamento' no portal."),
            FAQCreate(question="Qual o prazo das atividades complementares?", answer="As horas (ACC) devem ser enviadas até o penúltimo semestre do seu curso via portal."),
            FAQCreate(question="Quais são as regras da biblioteca?", answer="Empréstimo de até 5 livros por 7 dias. A multa por atraso é de R$ 2,00 por dia útil."),
            FAQCreate(question="Como renovar um livro?", answer="A renovação é feita online pelo sistema Pergamum até 3 vezes, caso não haja reserva para o livro."),
            FAQCreate(question="Tem salas de estudo em grupo?", answer="Sim, a biblioteca possui salas de estudo que podem ser reservadas no balcão de atendimento."),
            FAQCreate(question="Como conectar no Wi-Fi da faculdade?", answer="Conecte na rede 'ALUNOS_WIFI'. Use seu RA como login e a mesma senha do portal acadêmico."),
            FAQCreate(question="Esqueci minha senha do portal, o que eu faço?", answer="Use a opção 'Esqueci minha senha' no site ou vá ao setor de TI no Bloco C para resetar."),
            FAQCreate(question="Como pegar o boleto da mensalidade?", answer="Os boletos ficam no Portal do Aluno, seção 'Financeiro', disponíveis 10 dias antes do vencimento."),
            FAQCreate(question="Como solicitar uma bolsa de estudos?", answer="Procure o setor de Responsabilidade Social no Bloco A para informações sobre Prouni, FIES ou bolsas internas."),
        ]

        for faq_in in faqs:
            try:
                await FAQService.create_faq(db, faq_in)
                print(f"  ✅ {faq_in.question}")
            except Exception as e:
                print(f"  ❌ Erro em '{faq_in.question}': {e}")

        # ── Eventos ───────────────────────────────────────────────────────────
        print("\n📅 Inserindo eventos...")
        eventos = [
            Event(
                title="Semana Acadêmica de Tecnologia",
                description="Palestras e workshops sobre IA, Cloud e Desenvolvimento de Software no auditório principal.",
                event_date=datetime.now() + timedelta(days=15),
                event_type="palestra",
            ),
            Event(
                title="Feira de Carreiras e Estágios",
                description="Empresas da região apresentando oportunidades de estágio e trainee para alunos.",
                event_date=datetime.now() + timedelta(days=22),
                event_type="evento_social",
            ),
        ]

        for ev in eventos:
            db.add(ev)

        await db.commit()

        print("\n🚀 Seed finalizado!")
        print("   Admin: admin / admin123")
        print("   Acesse: http://localhost:8000/docs")


if __name__ == "__main__":
    asyncio.run(seed())
