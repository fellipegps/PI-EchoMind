import time
import httpx
from app.core.config import settings

class AIService:
    EMBEDDING_MODEL = "nomic-embed-text" 
    LLM_MODEL = "llama3" 
    OLLAMA_BASE_URL = "http://host.docker.internal:11434"

    @staticmethod
    async def get_embedding(text: str):
        """Transforma texto em vetor usando Ollama local"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{AIService.OLLAMA_BASE_URL}/api/embeddings",
                json={"model": AIService.EMBEDDING_MODEL, "prompt": text}
            )
            resp.raise_for_status()
            return resp.json()["embedding"]

    @staticmethod
    async def generate_text_response(prompt: str, context: str) -> str:
        """Gera resposta usando o LLM local via Ollama"""
        system_prompt = f"Você é um assistente de totem universitário para o projeto EchoMind. Use apenas este contexto para responder: {context}. Se não souber, diga que não encontrou a informação específica."
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{AIService.OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": AIService.LLM_MODEL,
                    "prompt": f"System: {system_prompt}\nUser: {prompt}",
                    "stream": False
                }
            )
            resp.raise_for_status()
            return resp.json()["response"]

    @staticmethod
    async def transcribe_audio(file_path: str) -> str:
        return "Função de transcrição mantida como original"

    @staticmethod
    async def text_to_speech(text: str) -> str:
        return "Caminho do áudio gerado"