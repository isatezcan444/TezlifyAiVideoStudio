from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class VoiceProfile(BaseModel):
    voice_id: str = Field(..., min_length=1, description="ElevenLabs voice ID")
    name: str = Field(..., min_length=1, description="Display name of the voice")
    gender: str = Field(default="neutral", description="Gender of the voice (male, female, neutral)")
    language: str = Field(default="tr", description="Primary or supported language code")
    category: str = Field(default="premade", description="Voice category (premade, cloned, generated)")
    preview_url: Optional[str] = Field(default=None, description="URL to a sample audio snippet")
    description: Optional[str] = Field(default=None, description="Descriptive label or style notes")

class DialogueAudioResult(BaseModel):
    dialogue_id: str
    character_id: str
    voice_id: str
    text: str
    audio_file_path: str
    duration_seconds: float = Field(ge=0.0)
    start_time: float = Field(ge=0.0)
    end_time: float = Field(gt=0.0)
    alignment_json: Optional[str] = None

