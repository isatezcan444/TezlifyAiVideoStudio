import os
import json
import base64
import hashlib
import logging
import subprocess
from typing import List, Optional, Dict, Any
import httpx

from tezlify_studio.application.ports.voice_synthesizer_port import VoiceSynthesizerPort
from tezlify_studio.domain.value_objects.voice_models import VoiceProfile, DialogueAudioResult
from tezlify_studio.domain.exceptions.studio_exceptions import (
    ElevenLabsNotConfiguredException,
    ElevenLabsApiException,
    AudioSynthesisException,
)

logger = logging.getLogger(__name__)

# Curated real ElevenLabs voices with verified multilingual support (Turkish)
DEFAULT_ELEVENLABS_VOICES = [
    {
        "voice_id": "IKne3meq5aSn9XLyUdCD",
        "name": "Charlie (Genç / Enerjik Erkek)",
        "gender": "male",
        "language": "tr",
        "category": "premade",
        "description": "Ali için önerilen doğal, dinamik Türkçe erkek sesi.",
    },
    {
        "voice_id": "pNInz6obpgDQGcFmaJgB",
        "name": "Adam (Derin / Anlatıcı Erkek)",
        "gender": "male",
        "language": "tr",
        "category": "premade",
        "description": "Klasik anlatıcı, derin ve güven verici erkek sesi.",
    },
    {
        "voice_id": "bIHbv24MWmeRgasZH58o",
        "name": "Will (Samimi / Sakin Erkek)",
        "gender": "male",
        "language": "tr",
        "category": "premade",
        "description": "Sıcak ve rahat konuşma tonuna sahip erkek sesi.",
    },
    {
        "voice_id": "cgSgspJ2msm6clMCkdW9",
        "name": "Jessica (Neşeli / Samimi Kadın)",
        "gender": "female",
        "language": "tr",
        "category": "premade",
        "description": "Ayşe için önerilen neşeli, parlak ve doğal Türkçe kadın sesi.",
    },
    {
        "voice_id": "EXAVITQu4vr4xnSDxMaL",
        "name": "Sarah (Kendinden Emin / Profesyonel Kadın)",
        "gender": "female",
        "language": "tr",
        "category": "premade",
        "description": "Olgun, profesyonel ve berrak kadın sesi.",
    },
    {
        "voice_id": "Xb7hH8MSUJpSbSDYk0k2",
        "name": "Alice (Açık / Anlatıcı Kadın)",
        "gender": "female",
        "language": "tr",
        "category": "premade",
        "description": "Eğitici, net ve tane tane konuşan kadın sesi.",
    },
]

class ElevenLabsClientImpl(VoiceSynthesizerPort):
    def __init__(
        self,
        api_key: Optional[str] = None,
        default_model: str = "eleven_multilingual_v2",
        api_base: str = "https://api.elevenlabs.io/v1",
        cache_dir: Optional[str] = None,
    ):
        self.api_key = api_key or os.environ.get("ELEVENLABS_API_KEY", "").strip() or None
        self.default_model = default_model
        self.api_base = api_base.rstrip("/")
        self.cache_dir = cache_dir or os.path.abspath("data/audio_cache")
        os.makedirs(self.cache_dir, exist_ok=True)

    def is_configured(self) -> bool:
        return bool(self.api_key and len(self.api_key) > 5)

    def list_voices(self) -> List[VoiceProfile]:
        """Fetches voices from ElevenLabs API if reachable; falls back to curated catalog."""
        headers = {}
        if self.api_key:
            headers["xi-api-key"] = self.api_key

        try:
            with httpx.Client(timeout=8.0) as client:
                res = client.get(f"{self.api_base}/voices", headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    voices_raw = data.get("voices", [])
                    profiles = []
                    for v in voices_raw:
                        labels = v.get("labels") or {}
                        gender = labels.get("gender", "neutral")
                        profiles.append(
                            VoiceProfile(
                                voice_id=v["voice_id"],
                                name=v.get("name", v["voice_id"]),
                                gender=gender,
                                language="tr" if labels.get("language") == "tr" else "multilingual",
                                category=v.get("category", "premade"),
                                preview_url=v.get("preview_url"),
                                description=f"{labels.get('descriptive', '')} {labels.get('accent', '')}".strip() or None,
                            )
                        )
                    if profiles:
                        return profiles
        except Exception as e:
            logger.warning(f"Could not reach ElevenLabs voices endpoint ({e}), using curated voice catalog.")

        # Return curated voices if offline or API request failed
        return [VoiceProfile(**item) for item in DEFAULT_ELEVENLABS_VOICES]

    def resolve_voice_id_for_character(self, character_id: str, gender: str, assigned_voice_id: str) -> str:
        """Maps logical voice aliases (e.g. 'tr_male_ali', 'tr_yelda') or unassigned IDs

        to optimal real ElevenLabs voice IDs.
        """
        clean_voice = (assigned_voice_id or "").strip()
        # If an explicit voice ID is provided that is not a legacy alias, use it directly
        if clean_voice and not clean_voice.startswith("tr_") and not clean_voice.startswith("alias_"):
            return clean_voice

        # Check Ali mapping
        if "ali" in clean_voice.lower() or "ali" in character_id.lower() or (gender == "male" and not clean_voice):
            return "IKne3meq5aSn9XLyUdCD"  # Charlie (Energetic male)

        # Check Ayşe mapping
        if "ayse" in clean_voice.lower() or "ayşe" in clean_voice.lower() or "ayse" in character_id.lower() or (gender == "female" and not clean_voice):
            return "cgSgspJ2msm6clMCkdW9"  # Jessica (Warm, playful female)

        # Generic gender fallback
        if gender == "male":
            return "pNInz6obpgDQGcFmaJgB"  # Adam
        elif gender == "female":
            return "EXAVITQu4vr4xnSDxMaL"  # Sarah

        return "IKne3meq5aSn9XLyUdCD"

    def _get_audio_duration_seconds(self, file_path: str) -> float:
        """Measures exact duration in seconds of an audio file using ffprobe."""
        if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
            return 0.0

        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_path,
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            val = float(res.stdout.strip())
            return max(0.1, round(val, 3))
        except Exception as e:
            logger.warning(f"Failed to measure duration with ffprobe for {file_path}: {e}")
            return 1.5

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
        clean_text = (text or "").strip()
        if not clean_text:
            raise ValueError("Diyalog metni boş olamaz.")

        if not self.is_configured():
            raise ElevenLabsNotConfiguredException(
                "ElevenLabs API anahtarı yapılandırılmamış. Ses üretimi için lütfen .env dosyasına "
                "ELEVENLABS_API_KEY ekleyin."
            )

        model = model_id or self.default_model
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        # 1. Check local audio cache by hash
        cache_key = hashlib.sha256(f"{voice_id}_{model}_{clean_text}".encode("utf-8")).hexdigest()
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.mp3")

        alignment_json = None

        if os.path.exists(cache_file) and os.path.getsize(cache_file) > 1000:
            logger.info(f"Using cached audio for voice {voice_id}: {cache_key[:8]}...")
            with open(cache_file, "rb") as sf, open(output_path, "wb") as df:
                df.write(sf.read())
        else:
            # 2. Call ElevenLabs API
            headers = {
                "xi-api-key": self.api_key,
                "Content-Type": "application/json",
            }
            body = {
                "text": clean_text,
                "model_id": model,
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75,
                },
            }

            # First attempt with-timestamps endpoint for character alignment
            with_timestamps_url = f"{self.api_base}/text-to-speech/{voice_id}/with-timestamps"
            got_audio = False

            try:
                with httpx.Client(timeout=35.0) as client:
                    resp = client.post(with_timestamps_url, headers=headers, json=body)
                    if resp.status_code == 200:
                        data = resp.json()
                        audio_b64 = data.get("audio_base64", "")
                        if audio_b64:
                            audio_bytes = base64.b64decode(audio_b64)
                            with open(output_path, "wb") as f:
                                f.write(audio_bytes)
                            with open(cache_file, "wb") as f:
                                f.write(audio_bytes)
                            alignment_json = json.dumps(data.get("alignment", {}))
                            got_audio = True
                    elif resp.status_code == 401:
                        raise ElevenLabsApiException("Yetkilendirme hatası: Geçersiz veya süresi dolmuş API anahtarı.", status_code=401)
                    elif resp.status_code == 429:
                        raise ElevenLabsApiException("ElevenLabs istek sınırı veya karakter kotası aşıldı.", status_code=429)
            except Exception as e:
                if isinstance(e, ElevenLabsApiException):
                    raise
                logger.warning(f"with-timestamps endpoint failed ({e}), falling back to standard text-to-speech.")

            # Fallback to standard binary stream endpoint
            if not got_audio:
                standard_url = f"{self.api_base}/text-to-speech/{voice_id}"
                try:
                    with httpx.Client(timeout=35.0) as client:
                        resp = client.post(standard_url, headers=headers, json=body)
                        if resp.status_code == 200:
                            with open(output_path, "wb") as f:
                                f.write(resp.content)
                            with open(cache_file, "wb") as f:
                                f.write(resp.content)
                        elif resp.status_code == 401:
                            raise ElevenLabsApiException("Yetkilendirme hatası: Geçersiz veya süresi dolmuş API anahtarı.", status_code=401)
                        elif resp.status_code == 429:
                            raise ElevenLabsApiException("ElevenLabs istek sınırı veya karakter kotası aşıldı.", status_code=429)
                        else:
                            raise ElevenLabsApiException(
                                f"API çağrısı başarısız oldu: {resp.text[:300]}",
                                status_code=resp.status_code,
                            )
                except Exception as e:
                    if isinstance(e, ElevenLabsApiException):
                        raise
                    raise AudioSynthesisException(f"ElevenLabs ses üretimi başarısız oldu: {str(e)}")

        # 3. Measure duration via ffprobe
        measured_duration = self._get_audio_duration_seconds(output_path)
        end_time = round(start_time + measured_duration, 3)

        return DialogueAudioResult(
            dialogue_id=dialogue_id or "dlg_default",
            character_id=character_id or "char_unknown",
            voice_id=voice_id,
            text=clean_text,
            audio_file_path=output_path,
            duration_seconds=measured_duration,
            start_time=start_time,
            end_time=end_time,
            alignment_json=alignment_json,
        )
