"""
voice_service.py — Serviço de Text-to-Speech via Google TTS (gTTS)

Substitui o edge-tts, que dependia de um TrustedClientToken da Microsoft
revogado periodicamente, causando erro 403.

O gTTS usa a mesma API interna do Google Translate para gerar áudio MP3,
sem chave de API, sem token, sem conta. Requer apenas acesso à internet.

Vozes: o gTTS não diferencia gênero nativamente — ambas as opções usam
a voz neural pt-BR do Google (mesma usada no Google Assistente), que é
feminina por padrão. A distinção de gênero é mantida na interface para
compatibilidade com o campo da configuração, mas soa igual nas duas opções.
Se diferenciação real de gênero for necessária no futuro, use a Google
Cloud Text-to-Speech API (requer chave).
"""

from __future__ import annotations

import asyncio
import io
import logging

from gtts import gTTS

logger = logging.getLogger("echomind.tts")


async def synthesize(text: str, gender: str = "feminina") -> bytes:
    """
    Gera áudio MP3 a partir de texto usando Google TTS (gTTS).

    Args:
        text:   Texto a ser sintetizado.
        gender: "feminina" ou "masculina" (aceito por compatibilidade;
                o gTTS usa a voz pt-BR padrão do Google em ambos os casos).

    Returns:
        Bytes do arquivo MP3 gerado em memória.

    Raises:
        RuntimeError: se o gTTS falhar (sem internet, texto vazio, etc).
    """
    text = text.strip()
    if not text:
        raise RuntimeError("Texto vazio — nada a sintetizar.")

    if gender not in {"feminina", "masculina"}:
        logger.warning("[TTS] Gênero inválido '%s'. Usando voz feminina como fallback.", gender)
        gender = "feminina"

    logger.info("[TTS] Sintetizando %d chars (gTTS pt-BR, voz=%s)", len(text), gender)

    loop = asyncio.get_running_loop()

    def _generate() -> bytes:
        """Executa gTTS de forma síncrona — rodado em thread para não bloquear."""
        tts = gTTS(text=text, lang="pt", tld="com.br", slow=False)
        buf = io.BytesIO()
        tts.write_to_fp(buf)
        return buf.getvalue()

    try:
        # gTTS é síncrono e faz I/O de rede — executa em thread separada
        audio_bytes = await loop.run_in_executor(None, _generate)
    except Exception as exc:
        logger.error("[TTS] Falha no gTTS: %s", exc, exc_info=True)
        raise RuntimeError(f"Falha ao sintetizar áudio: {exc}") from exc

    if not audio_bytes:
        raise RuntimeError("gTTS retornou áudio vazio.")

    logger.info("[TTS] Áudio gerado: %d bytes", len(audio_bytes))
    return audio_bytes
