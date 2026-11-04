import os
import hashlib
import tempfile
import pytest
from unittest.mock import MagicMock, patch
import httpx

from tezlify_studio.infrastructure.ai.elevenlabs_client_impl import ElevenLabsClientImpl
from tezlify_studio.domain.exceptions.studio_exceptions import (
    ElevenLabsNotConfiguredException,
    ElevenLabsApiException,
    VoiceNotFoundException,
)


def test_is_configured():
    client_unconfigured = ElevenLabsClientImpl(api_key="", cache_dir=tempfile.gettempdir())
    assert client_unconfigured.is_configured() is False

    client_configured = ElevenLabsClientImpl(api_key="sk_test_12345", cache_dir=tempfile.gettempdir())
    assert client_configured.is_configured() is True


def test_resolve_voice_id_for_character():
    client = ElevenLabsClientImpl(api_key="", cache_dir=tempfile.gettempdir())

    # Ali resolution
    assert client.resolve_voice_id_for_character("char_ali", "male", "") == "IKne3meq5aSn9XLyUdCD"
    assert client.resolve_voice_id_for_character("Ali", "male", "") == "IKne3meq5aSn9XLyUdCD"
    assert client.resolve_voice_id_for_character("ali_character", "male", "tr_male_ali") == "IKne3meq5aSn9XLyUdCD"

    # Ayşe resolution
    assert client.resolve_voice_id_for_character("char_ayse", "female", "") == "cgSgspJ2msm6clMCkdW9"
    assert client.resolve_voice_id_for_character("Ayşe", "female", "") == "cgSgspJ2msm6clMCkdW9"
    assert client.resolve_voice_id_for_character("ayse_character", "female", "tr_female_ayse") == "cgSgspJ2msm6clMCkdW9"

    # Gender fallback
    assert client.resolve_voice_id_for_character("unknown_male", "male", "") == "IKne3meq5aSn9XLyUdCD"
    assert client.resolve_voice_id_for_character("unknown_female", "female", "") == "cgSgspJ2msm6clMCkdW9"

    # Explicit custom voice ID
    custom_id = "custom_voice_id_999"
    assert client.resolve_voice_id_for_character("char_custom", "neutral", custom_id) == custom_id


def test_list_voices_curated_fallback():
    # When unconfigured or offline, list_voices returns curated catalog
    with patch("httpx.get", side_effect=Exception("Network down")):
        client = ElevenLabsClientImpl(api_key="", cache_dir=tempfile.gettempdir())
        voices = client.list_voices()
        assert len(voices) >= 6
        voice_ids = [v.voice_id for v in voices]
        assert "IKne3meq5aSn9XLyUdCD" in voice_ids  # Charlie
        assert "cgSgspJ2msm6clMCkdW9" in voice_ids  # Jessica


def test_synthesize_speech_raises_when_not_configured():
    client = ElevenLabsClientImpl(api_key="", cache_dir=tempfile.gettempdir())
    with pytest.raises(ElevenLabsNotConfiguredException):
        client.synthesize_speech(
            text="Merhaba dünya",
            voice_id="IKne3meq5aSn9XLyUdCD",
            output_path="/tmp/output.mp3",
        )


def test_synthesize_speech_cache_hit():
    with tempfile.TemporaryDirectory() as tmp_dir:
        client = ElevenLabsClientImpl(api_key="sk_fake_key", cache_dir=tmp_dir)
        text = "Test önbellek metni"
        voice_id = "IKne3meq5aSn9XLyUdCD"
        output_file = os.path.join(tmp_dir, "dest.mp3")

        # Compute hash and write a mock cache file (> 1000 bytes)
        cache_key = hashlib.sha256(f"{voice_id}_eleven_multilingual_v2_{text}".encode("utf-8")).hexdigest()
        cache_path = os.path.join(tmp_dir, f"{cache_key}.mp3")
        with open(cache_path, "wb") as f:
            f.write(b"MOCK_MP3_DATA" * 100)

        # Mock duration measurement
        with patch.object(client, "_get_audio_duration_seconds", return_value=2.45):
            res = client.synthesize_speech(text=text, voice_id=voice_id, output_path=output_file)
            assert os.path.exists(output_file)
            assert res.audio_file_path == output_file
            assert res.duration_seconds == 2.45
            assert res.voice_id == voice_id
            assert res.text == text


def test_synthesize_speech_handles_api_errors():
    with tempfile.TemporaryDirectory() as tmp_dir:
        client = ElevenLabsClientImpl(api_key="sk_fake_key", cache_dir=tmp_dir)
        output_file = os.path.join(tmp_dir, "dest.mp3")

        # 401 Unauthorized
        mock_resp_401 = MagicMock()
        mock_resp_401.status_code = 401
        mock_resp_401.text = "Unauthorized: Invalid API key"

        with patch("httpx.Client.post", return_value=mock_resp_401):
            with pytest.raises(ElevenLabsApiException) as exc_info:
                client.synthesize_speech(
                    text="Test",
                    voice_id="IKne3meq5aSn9XLyUdCD",
                    output_path=output_file,
                )
            assert exc_info.value.status_code == 401

        # 429 Quota Exceeded
        mock_resp_429 = MagicMock()
        mock_resp_429.status_code = 429
        mock_resp_429.text = "Quota exceeded"

        with patch("httpx.Client.post", return_value=mock_resp_429):
            with pytest.raises(ElevenLabsApiException) as exc_info:
                client.synthesize_speech(
                    text="Test",
                    voice_id="IKne3meq5aSn9XLyUdCD",
                    output_path=output_file,
                )
            assert exc_info.value.status_code == 429
