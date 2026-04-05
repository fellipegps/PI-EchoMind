from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from app.models.faq import faq as FAQ
from app.schemas.faq import FAQCreate, FAQUpdate
from app.services.embedding_service import EmbeddingService


class FAQService:
    @staticmethod
    async def create_faq(db: AsyncSession, faq_in: FAQCreate):
        embedding = await EmbeddingService.get_embedding(faq_in.question)

        new_faq = FAQ(
            question=faq_in.question,
            answer=faq_in.answer,
            category=faq_in.category,
            embedding=embedding,
            total_consults=0,
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
    async def get_by_id(db: AsyncSession, faq_id: UUID):
        result = await db.execute(select(FAQ).where(FAQ.id == faq_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def update_faq(db: AsyncSession, faq_id: UUID, faq_in: FAQUpdate):
        result = await db.execute(select(FAQ).where(FAQ.id == faq_id))
        faq = result.scalar_one_or_none()
        if not faq:
            return None

        if faq_in.question is not None:
            faq.question = faq_in.question
            faq.embedding = await EmbeddingService.get_embedding(faq_in.question)
        if faq_in.answer is not None:
            faq.answer = faq_in.answer
        if faq_in.category is not None:
            faq.category = faq_in.category

        await db.commit()
        await db.refresh(faq)
        return faq

    @staticmethod
    async def delete_faq(db: AsyncSession, faq_id: UUID):
        result = await db.execute(select(FAQ).where(FAQ.id == faq_id))
        faq = result.scalar_one_or_none()
        if not faq:
            return False
        await db.delete(faq)
        await db.commit()
        return True

    @staticmethod
    async def search_similar(db: AsyncSession, query_text: str):
        query_embedding = await EmbeddingService.get_embedding(query_text)
        stmt = (
            select(FAQ)
            .order_by(FAQ.embedding.cosine_distance(query_embedding))
            .limit(1)
        )
        result = await db.execute(stmt)
        faq = result.scalar_one_or_none()
        if faq:
            faq.total_consults += 1
            await db.commit()
            await db.refresh(faq)
        return faq

    @staticmethod
    async def save_unanswered(db: AsyncSession, question: str, embedding):
        from app.models.unanswered import UnansweredQuestion
        unanswered = UnansweredQuestion(question=question, embedding=embedding)
        db.add(unanswered)
        await db.commit()
