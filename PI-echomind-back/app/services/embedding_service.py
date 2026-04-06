# O EmbeddingService usa o Ollama para gerar vetores semânticos (768 dimensões).
# O código da OpenAI foi removido pois o projeto usa Ollama local como padrão.
# Para reativar a OpenAI, instale o pacote "openai", descomente o bloco abaixo
# e comente o return do stub.

# from openai import AsyncOpenAI
# from app.core.config import settings
# client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


class EmbeddingService:
    @staticmethod
    async def get_embedding(text: str) -> list[float]:
        """
        Gera o embedding de um texto usando Ollama (mxbai-embed-large, 768 dims).

        TODO: integrar com langchain_ollama.OllamaEmbeddings quando o modelo
        estiver disponível localmente. Por ora retorna vetor zerado como stub
        para que o backend suba sem dependência do Ollama durante desenvolvimento.
        """

        # ── Stub para desenvolvimento sem Ollama ──────────────────────────────
        # Remove ou comenta estas duas linhas quando o Ollama estiver rodando.
        return [0.0] * 768

        # ── Integração real com Ollama (descomente quando disponível) ─────────
        # from langchain_ollama import OllamaEmbeddings
        # embedder = OllamaEmbeddings(model="mxbai-embed-large")
        # return await embedder.aembed_query(text)
