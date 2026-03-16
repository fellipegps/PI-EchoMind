from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from pydantic import BaseModel
from app.core.database import get_db
from app.schemas.faq import FAQCreate, FAQResponse
from app.services.faq_service import FAQService
from app.services.ai_service import AIService

router = APIRouter(prefix="/faqs", tags=["FAQ Management"])

# --- SCHEMAS DE ENTRADA ---

class QuestionRequest(BaseModel):
    """Modelo para receber a pergunta do Totem via JSON Body"""
    question: str

# --- ROTAS ---

# Rota para o Admin criar novos FAQs
@router.post("/", response_model=FAQResponse, status_code=status.HTTP_201_CREATED)
async def create_faq(faq_in: FAQCreate, db: AsyncSession = Depends(get_db)):
    return await FAQService.create_faq(db, faq_in)

# Rota para listar todos (usado na aba Base de Conhecimento)
@router.get("/", response_model=List[FAQResponse])
async def list_faqs(db: AsyncSession = Depends(get_db)):
    return await FAQService.get_all(db)

# A ROTA PRINCIPAL DO TOTEM (O coração da IA)
@router.post("/ask")
async def ask_question(data: QuestionRequest, db: AsyncSession = Depends(get_db)):
    """
    Recebe uma pergunta, busca no banco vetorial e humaniza a resposta com IA.
    """
    question_text = data.question

    # 1. Busca o FAQ mais próximo via busca vetorial (pgvector)
    result = await FAQService.search_similar(db, question_text)
    
    if not result:
        # 2. Se não achar nada parecido, gera o embedding para salvar em "Não Respondidas"
        # Isso permitirá que o Admin veja o que os alunos estão perguntando e não tem no banco
        query_vector = await AIService.get_embedding(question_text)
        
        # Certifique-se de que o método save_unanswered existe no seu FAQService
        try:
            await FAQService.save_unanswered(db, question_text, query_vector)
        except Exception as e:
            print(f"Erro ao salvar pergunta não respondida: {e}")
        
        return {"answer": "Ainda não tenho essa informação, mas meus criadores já foram notificados!"}

    # 3. Se achou um FAQ compatível, envia a resposta para a IA "humanizar"
    # O AIService usa o Ollama para deixar a resposta menos "robótica"
    try:
        final_answer = await AIService.generate_text_response(question_text, result.answer)
    except Exception as e:
        # Fallback caso a IA (Ollama) esteja fora do ar ou lenta
        print(f"Erro no AIService: {e}")
        final_answer = result.answer
    
    # 4. O contador result.total_consults é incrementado dentro do search_similar
    # O commit final garante que as métricas do Dashboard sejam persistidas
    await db.commit()
    
    return {
        "answer": final_answer,
        "source_faq_id": result.id  # Útil para debug e auditoria
    }