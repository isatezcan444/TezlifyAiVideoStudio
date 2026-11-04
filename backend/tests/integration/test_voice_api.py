import pytest
from fastapi.testclient import TestClient
from tezlify_studio.presentation.api.app import app

client = TestClient(app)


def test_list_voices_endpoint():
    res = client.get("/api/v1/studio/voices")
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "total" in data
    assert "is_configured" in data
    assert data["total"] > 0
    assert len(data["items"]) > 0

    # Verify voice properties
    voice_ids = [v["voice_id"] for v in data["items"]]
    assert "IKne3meq5aSn9XLyUdCD" in voice_ids  # Charlie
    assert "cgSgspJ2msm6clMCkdW9" in voice_ids  # Jessica

    first_voice = data["items"][0]
    assert "voice_id" in first_voice
    assert "name" in first_voice
    assert "gender" in first_voice
    assert "category" in first_voice


def test_get_voice_status_endpoint():
    res = client.get("/api/v1/studio/voices/status")
    assert res.status_code == 200
    data = res.json()
    assert "is_configured" in data
    assert "default_model" in data
    assert "provider" in data
    assert data["provider"] == "ElevenLabs"
    assert "eleven_multilingual_v2" in data["default_model"]

