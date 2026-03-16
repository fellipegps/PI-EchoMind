from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.faq import FAQ
from app.models.document import DocumentChunk

class VectorSearch:
    @staticmethod
    async def find_similar_context(db: AsyncSession, embedding: list, limit: int = 3):
        faq_stmt = select(FAQ).order_by(FAQ.embedding.cosine_distance(embedding)).limit(limit)
        doc_stmt = select(DocumentChunk).order_by(DocumentChunk.embedding.cosine_distance(embedding)).limit(limit)
        
        faqs = (await db.execute(faq_stmt)).scalars().all()
        chunks = (await db.execute(doc_stmt)).scalars().all()
        
        context = "FAQs:\n" + "\n".join([f"P: {f.question} R: {f.answer}" for f in faqs])
        context += "\nDocumentos:\n" + "\n".join([c.content for c in chunks])
        
        return context
    