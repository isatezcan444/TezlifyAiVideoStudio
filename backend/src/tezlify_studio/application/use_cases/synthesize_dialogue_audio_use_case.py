import os
from typing import List, Tuple
from tezlify_studio.application.ports.voice_synthesizer_port import VoiceSynthesizerPort
from tezlify_studio.application.dto.voice_dto import DialogueAudioDTO
from tezlify_studio.domain.value_objects.scene_graph import SceneGraph
from tezlify_studio.infrastructure.ai.elevenlabs_client_impl import ElevenLabsClientImpl

class SynthesizeDialogueAudioUseCase:
    def __init__(self, voice_synthesizer: VoiceSynthesizerPort):
        self.voice_synthesizer = voice_synthesizer

    def execute(
        self,
        scene_graph: SceneGraph,
        project_id: str,
        audio_base_dir: str,
    ) -> Tuple[SceneGraph, List[DialogueAudioDTO]]:
        """Synthesizes speech audio for every dialogue line in the SceneGraph,

        measures actual spoken duration, and adjusts dialogue timings and scene durations
        so that animations and audio are perfectly synchronized.
        """
        proj_audio_dir = os.path.join(audio_base_dir, project_id, "audio")
        os.makedirs(proj_audio_dir, exist_ok=True)

        char_lookup = {c.id: c for c in scene_graph.characters}
        generated_audios: List[DialogueAudioDTO] = []

        for s_idx, scene in enumerate(scene_graph.scenes):
            # Start speech after a 0.5s scene establishing beat
            speech_cursor = 0.5

            for d_idx, dlg in enumerate(scene.dialogues):
                char_info = char_lookup.get(dlg.character_id)
                char_gender = "neutral"
                assigned_voice = ""
                if char_info:
                    assigned_voice = getattr(char_info, "voice_id", "") or ""
                    # Style/character hints
                    if "ali" in dlg.character_id.lower():
                        char_gender = "male"
                    elif "ayse" in dlg.character_id.lower():
                        char_gender = "female"

                if isinstance(self.voice_synthesizer, ElevenLabsClientImpl):
                    real_voice_id = self.voice_synthesizer.resolve_voice_id_for_character(
                        dlg.character_id, char_gender, assigned_voice
                    )
                else:
                    real_voice_id = assigned_voice or "IKne3meq5aSn9XLyUdCD"

                dlg_filename = f"dlg_{s_idx + 1}_{d_idx + 1}_{dlg.character_id}.mp3"
                dlg_path = os.path.join(proj_audio_dir, dlg_filename)

                audio_res = self.voice_synthesizer.synthesize_speech(
                    text=dlg.text,
                    voice_id=real_voice_id,
                    output_path=dlg_path,
                    dialogue_id=f"dlg_{s_idx}_{d_idx}",
                    character_id=dlg.character_id,
                    start_time=speech_cursor,
                )

                # Update dialogue object with exact times and audio file path
                dlg.start_time = speech_cursor
                dlg.end_time = round(speech_cursor + audio_res.duration_seconds, 2)
                dlg.audio_file = audio_res.audio_file_path

                # Advance cursor with a natural pause between speaking turns
                speech_cursor = round(dlg.end_time + 0.65, 2)

                generated_audios.append(
                    DialogueAudioDTO(
                        dialogue_id=audio_res.dialogue_id,
                        character_id=audio_res.character_id,
                        voice_id=audio_res.voice_id,
                        text=audio_res.text,
                        audio_file_path=audio_res.audio_file_path,
                        duration_seconds=audio_res.duration_seconds,
                        start_time=dlg.start_time,
                        end_time=dlg.end_time,
                        alignment_json=audio_res.alignment_json,
                    )
                )

            # Ensure scene duration fits all dialogue lines with a trailing rest
            min_required_scene_dur = max(scene.duration_seconds, speech_cursor + 0.8)
            scene.duration_seconds = round(min_required_scene_dur, 2)

        return scene_graph, generated_audios

