from openai import AsyncOpenAI
from app.core.config import settings

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

class EmbeddingService:
    @staticmethod
    async def get_embedding(text: str):
        '''
        response = await client.embeddings.create(
            input=text,
            model="text-embedding-3-small"
        )

        return response.data[0].embedding
    '''
        return [0.0] * 768
        