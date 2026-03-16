import time
import os
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.services.ai_service import AIService
from app.services.faq_service import FAQService
from app.models.interaction import Interaction

router = APIRouter(prefix="/voice-query", tags=["AI Agent - Voice"])


@router.post("/")
async def voice_query(
    audio: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Fluxo completo do totem de voz:
    1. Recebe arquivo de áudio (wav, mp3, ogg, webm)
    2. Transcreve com Whisper local
    3. Busca contexto via RAG (FAQs + Documentos)
    4. Gera resposta com Ollama (llama3.2)
    5. Converte resposta em áudio com Edge TTS
    6. Salva log da interação no banco
    7. Retorna texto + URL do áudio
    """
    start_ts = time.time()

    # Valida tipo de arquivo
    allowed_types = {"audio/wav", "audio/mpeg", "audio/ogg", "audio/webm", "audio/mp4", "video/webm"}
    if audio.content_type and audio.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Formato não suportado: {audio.content_type}. Use wav, mp3, ogg ou webm."
        )

    # Salva áudio temporariamente
    ext = audio.filename.split(".")[-1] if audio.filename and "." in audio.filename else "wav"
    temp_path = f"temp_audio_{int(time.time())}.{ext}"

    try:
        with open(temp_path, "wb") as f:
            f.write(await audio.read())

        # 1. Transcrição (Whisper local)
        user_text = await AIService.transcribe_audio(temp_path)

        if not user_text:
            raise HTTPException(status_code=422, detail="Não foi possível transcrever o áudio. Tente falar mais claramente.")

        # 2. RAG + resposta da IA (reutiliza o fluxo do faq_service)
        result = await FAQService.ask_question(db, user_text)
        ai_text = result["answer"]

        # 3. TTS (Edge TTS)
        audio_path = await AIService.text_to_speech(ai_text)

        duration = round(time.time() - start_ts, 2)

        # 4. Log da interação
        interaction = Interaction(
            question=user_text,
            answer=ai_text,
            response_time=duration
        )
        db.add(interaction)
        await db.commit()

        return {
            "transcribed_text": user_text,
            "text_response": ai_text,
            "audio_url": f"/{audio_path}",  # ex: /static/audio_1234.mp3
            "response_time": duration
        }

    finally:
        # Sempre remove o arquivo temporário
        if os.path.exists(temp_path):
            os.remove(temp_path)


@router.get("/audio/{filename}")
async def get_audio(filename: str):
    """Serve o arquivo de áudio gerado pelo TTS."""
    path = f"static/{filename}"
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Arquivo de áudio não encontrado")
    return FileResponse(path, media_type="audio/mpeg")
