from abc import ABC, abstractmethod
from typing import List, Optional
from tezlify_studio.domain.value_objects.voice_models import VoiceProfile, DialogueAudioResult

class VoiceSynthesizerPort(ABC):
    @abstractmethod
    def list_voices(self) -> List[VoiceProfile]:
        """Lists available voice profiles from ElevenLabs or the local catalog."""
        pass

    @abstractmethod
    def synthesize_speech(
        self,
        text: str,
        voice_id: str,
        output_path: str,
        model_id: Optional[str] = None,
        dialogue_id: Optional[str] = None,
        character_id: Optional[str] = None,
        start_time: float = 0.0,
    ) -> DialogueAudioResult:
        """Synthesizes dialogue text into an audio file (.mp3) using ElevenLabs TTS

        and returns the audio result with exact measured duration.
        """
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """Returns True if ElevenLabs API key is configured and available."""
        pass

