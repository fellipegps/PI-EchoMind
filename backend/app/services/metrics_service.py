from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.interaction import Interaction
from app.models.faq import FAQ
from app.models.unanswered import UnansweredQuestion

class MetricsService:
    @staticmethod
    async def get_overview(db: AsyncSession):
        # 1. Total de Perguntas (Baseado nas interações totais do Totem)
        total_stmt = select(func.count(Interaction.id))
        total_res = await db.execute(total_stmt)
        total_count = total_res.scalar() or 0
        
        # 2. Sem Resposta (Olhando para o seu modelo UnansweredQuestion)
        unanswered_stmt = select(func.count(UnansweredQuestion.id)).where(UnansweredQuestion.resolved == False)
        unanswered_res = await db.execute(unanswered_stmt)
        unanswered_count = unanswered_res.scalar() or 0
        
        # 3. Tempo Médio de Resposta (Média da tabela Interaction)
        avg_time_stmt = select(func.avg(Interaction.response_time))
        avg_time_res = await db.execute(avg_time_stmt)
        avg_time_value = avg_time_res.scalar() or 1.2

        # 4. FAQs Mais Consultadas (Gráfico de barras)
        top_faqs_stmt = select(FAQ).order_by(FAQ.total_consults.desc()).limit(5)
        top_faqs_res = await db.execute(top_faqs_stmt)
        top_faqs = top_faqs_res.scalars().all()

        # Retorno formatado para os componentes do seu Dashboard
        return {
            "total_questions": total_count,
            "unanswered_count": unanswered_count,
            "avg_response_time": f"{round(float(avg_time_value), 1)}s",
            "top_faqs": [
                {
                    # Ajustado para pegar a coluna question do modelo FAQ
                    "label": f.question[:25] + "..." if len(f.question) > 25 else f.question, 
                    "value": f.total_consults
                } for f in top_faqs
            ],
            "interactions_per_day": [
                {"date": "10/03", "total": total_count}
            ]
        }

    @staticmethod
    async def get_top_faqs(db: AsyncSession, limit: int = 5):
        stmt = select(FAQ).order_by(FAQ.total_consults.desc()).limit(limit)
        result = await db.execute(stmt)
        return result.scalars().all()