from typing import List
from tezlify_studio.application.ports.voice_synthesizer_port import VoiceSynthesizerPort
from tezlify_studio.application.dto.voice_dto import VoiceDTO, VoiceListResponseDTO

class ListVoicesUseCase:
    def __init__(self, voice_synthesizer: VoiceSynthesizerPort):
        self.voice_synthesizer = voice_synthesizer

    def execute(self) -> VoiceListResponseDTO:
        profiles = self.voice_synthesizer.list_voices()
        dtos = [
            VoiceDTO(
                voice_id=p.voice_id,
                name=p.name,
                gender=p.gender,
                language=p.language,
                category=p.category,
                preview_url=p.preview_url,
                description=p.description,
            )
            for p in profiles
        ]
        return VoiceListResponseDTO(
            items=dtos,
            total=len(dtos),
            is_configured=self.voice_synthesizer.is_configured(),
        )

