import os
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.document import Document, DocumentChunk
from app.utils.file_handler import FileHandler
from app.services.embedding_service import EmbeddingService

class DocumentService:
    @staticmethod
    async def process_pdf_upload(db: AsyncSession, file_path: str, filename: str):
        # 1. Save Document record
        doc = Document(filename=filename)
        db.add(doc)
        await db.flush()

        # 2. Extract and Split
        text = FileHandler.extract_text_from_pdf(file_path)
        chunks = FileHandler.split_text(text)

        # 3. Embed and Save Chunks
        for content in chunks:
            embedding = await EmbeddingService.get_embedding(content)
            chunk = DocumentChunk(
                document_id=doc.id,
                content=content,
                embedding=embedding
            )
            db.add(chunk)
        
        await db.commit()
        return doc
    