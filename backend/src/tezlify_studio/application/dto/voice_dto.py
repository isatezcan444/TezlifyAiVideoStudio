from typing import List, Optional
from pydantic import BaseModel, Field

class VoiceDTO(BaseModel):
    voice_id: str
    name: str
    gender: str
    language: str
    category: str
    preview_url: Optional[str] = None
    description: Optional[str] = None

class VoiceListResponseDTO(BaseModel):
    items: List[VoiceDTO]
    total: int
    is_configured: bool

class SynthesizePreviewRequestDTO(BaseModel):
    text: str = Field(..., min_length=1, max_length=500)
    voice_id: str = Field(..., min_length=1)
    model_id: Optional[str] = None

class DialogueAudioDTO(BaseModel):
    dialogue_id: str
    character_id: str
    voice_id: str
    text: str
    audio_file_path: str
    duration_seconds: float
    start_time: float
    end_time: float
    alignment_json: Optional[str] = None

