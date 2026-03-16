from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.faq import FAQ
from app.schemas.faq import FAQCreate
from app.services.embedding_service import EmbeddingService
from app.models.faq import faq as FAQ

class FAQService:
    @staticmethod
    async def create_faq(db: AsyncSession, faq_in: FAQCreate):
        # O EmbeddingService deve usar o modelo do Ollama (ex: 768 dimensões)
        embedding = await EmbeddingService.get_embedding(faq_in.question)
        
        new_faq = FAQ(
            question=faq_in.question,
            answer=faq_in.answer,
            embedding=embedding,
            # Garantindo que os novos campos do dashboard iniciem zerados
            total_consults=0 
        )
        db.add(new_faq)
        await db.commit()
        await db.refresh(new_faq)
        return new_faq

    @staticmethod
    async def get_all(db: AsyncSession):
        result = await db.execute(select(FAQ))
        return result.scalars().all()

    @staticmethod
    async def search_similar(db: AsyncSession, query_text: str):
        """
        Realiza a busca RAG: transforma a pergunta em vetor e busca no banco.
        """
        # 1. Gera o embedding da pergunta do usuário
        query_embedding = await EmbeddingService.get_embedding(query_text)

        # 2. Busca o FAQ mais próximo usando a distância de cosseno do pgvector
        # O limite de 0.5 é opcional, serve para evitar respostas nada a ver
        stmt = (
            select(FAQ)
            .order_by(FAQ.embedding.cosine_distance(query_embedding))
            .limit(1)
        )
        
        result = await db.execute(stmt)
        faq = result.scalar_one_or_none()

        if faq:
            # Importante: incrementa o contador para o gráfico de barras do dashboard
            faq.total_consults += 1
            await db.commit()
            await db.refresh(faq)
            
        return faq