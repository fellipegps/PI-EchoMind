from pydantic import BaseModel

class VoiceQueryResponse(BaseModel):
    text_response: str
    audio_url: str
    response_time: float
    