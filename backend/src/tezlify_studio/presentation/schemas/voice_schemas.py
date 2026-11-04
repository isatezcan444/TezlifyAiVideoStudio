from typing import List, Optional
from pydantic import BaseModel, Field

class VoiceResponse(BaseModel):
    voice_id: str
    name: str
    gender: str
    language: str
    category: str
    preview_url: Optional[str] = None
    description: Optional[str] = None

class VoiceListResponse(BaseModel):
    items: List[VoiceResponse]
    total: int
    is_configured: bool

class VoicePreviewRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=500)
    voice_id: str = Field(..., min_length=1)

class VoiceStatusResponse(BaseModel):
    is_configured: bool
    default_model: str
    provider: str = "ElevenLabs"

