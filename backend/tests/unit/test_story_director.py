import json
import pytest
from unittest.mock import MagicMock
import httpx

from tezlify_studio.infrastructure.ai.template_story_planner_impl import TemplateStoryPlannerImpl
from tezlify_studio.infrastructure.ai.ollama_story_planner_impl import OllamaStoryPlannerImpl
from tezlify_studio.domain.value_objects.scene_graph import SceneGraph

def test_template_story_planner_turkish_cafe_prompt():
    planner = TemplateStoryPlannerImpl()
    prompt = "İki karakter bir kafede karşılaşıyor. Komik bir diyalog yaşanıyor. Video yaklaşık 30 saniye sürsün."
    
    sg = planner.plan_story(prompt=prompt)
    
    assert isinstance(sg, SceneGraph)
    assert sg.schema_version == "1.0"
    assert "Kafede" in sg.title or "Sohbet" in sg.title or len(sg.title) > 0
    assert sg.resolution.width == 1920
    assert sg.resolution.height == 1080
    assert sg.resolution.fps == 30
    assert len(sg.characters) >= 2
    assert len(sg.scenes) >= 2
    assert sg.total_duration_seconds >= 25 and sg.total_duration_seconds <= 35

    # Check background and character placement references
    char_ids = {c.id for c in sg.characters}
    for scene in sg.scenes:
        for placement in scene.character_placements:
            assert placement.character_id in char_ids
        for dialogue in scene.dialogues:
            assert dialogue.character_id in char_ids
            assert dialogue.end_time > dialogue.start_time
            assert dialogue.end_time <= scene.duration_seconds

def test_template_story_planner_genres():
    planner = TemplateStoryPlannerImpl()
    
    genres = ["comedy", "education", "product", "story", "explainer"]
    for g in genres:
        sg = planner.plan_story(f"Test prompt for {g}", genre=g)
        assert isinstance(sg, SceneGraph)
        assert len(sg.characters) >= 2
        assert len(sg.scenes) >= 2

def test_template_story_planner_duration_and_vertical():
    planner = TemplateStoryPlannerImpl()
    
    # 15 seconds vertical shorts
    sg_vertical = planner.plan_story("Dikey reels formatında 15 saniyelik video", aspect_ratio="9:16")
    assert sg_vertical.resolution.width == 1080
    assert sg_vertical.resolution.height == 1920
    assert sg_vertical.total_duration_seconds >= 14 and sg_vertical.total_duration_seconds <= 16

    # 45 seconds horizontal
    sg_horizontal = planner.plan_story("45 saniye süren açıklayıcı video")
    assert sg_horizontal.resolution.width == 1920
    assert sg_horizontal.resolution.height == 1080
    assert sg_horizontal.total_duration_seconds >= 40 and sg_horizontal.total_duration_seconds <= 50

def test_template_story_planner_setting_presets():
    planner = TemplateStoryPlannerImpl()
    
    sg_office = planner.plan_story("Ofiste geçen bir toplantı")
    assert any("office" in s.background.asset_id for s in sg_office.scenes)

    sg_park = planner.plan_story("Parkta yürüyen iki arkadaş")
    assert any("park" in s.background.asset_id for s in sg_park.scenes)

def test_ollama_fallback_when_offline():
    # Mock HTTP client that raises ConnectError
    mock_client = MagicMock(spec=httpx.Client)
    mock_client.get.side_effect = httpx.ConnectError("Connection refused")
    
    fallback = TemplateStoryPlannerImpl()
    ollama_planner = OllamaStoryPlannerImpl(
        base_url="http://localhost:11434",
        model="llama3.2",
        fallback_planner=fallback,
        http_client=mock_client,
    )
    
    assert ollama_planner.is_available() is False
    assert ollama_planner.list_installed_models() == []
    
    # Should fall back cleanly without raising any exception
    sg = ollama_planner.plan_story("Kahve dükkanında eğlenceli sohbet 20 saniye")
    assert isinstance(sg, SceneGraph)
    assert sg.schema_version == "1.0"
    assert len(sg.characters) >= 2

def test_ollama_fallback_on_malformed_json():
    mock_client = MagicMock(spec=httpx.Client)
    
    # is_available succeeds
    mock_tags_resp = MagicMock()
    mock_tags_resp.status_code = 200
    mock_tags_resp.json.return_value = {"models": [{"name": "llama3.2:latest"}]}
    mock_client.get.return_value = mock_tags_resp
    
    # chat returns invalid JSON
    mock_chat_resp = MagicMock()
    mock_chat_resp.status_code = 200
    mock_chat_resp.json.return_value = {
        "message": {"content": "Bu bir JSON değil veya geçersiz: { broken json ..."}
    }
    mock_client.post.return_value = mock_chat_resp
    
    fallback = TemplateStoryPlannerImpl()
    ollama_planner = OllamaStoryPlannerImpl(
        base_url="http://localhost:11434",
        model="llama3.2",
        fallback_planner=fallback,
        http_client=mock_client,
    )
    
    assert ollama_planner.is_available() is True
    
    # Should safely fall back to template planner
    sg = ollama_planner.plan_story("Komik video 15 saniye")
    assert isinstance(sg, SceneGraph)
    assert sg.schema_version == "1.0"
    assert len(sg.characters) >= 2

def test_ollama_success_parses_valid_scenegraph():
    template_planner = TemplateStoryPlannerImpl()
    sample_sg = template_planner.plan_story("Kısa test sahnesi 10 saniye")
    sample_sg_json = sample_sg.model_dump_json()

    mock_client = MagicMock(spec=httpx.Client)
    
    # is_available
    mock_tags_resp = MagicMock()
    mock_tags_resp.status_code = 200
    mock_client.get.return_value = mock_tags_resp
    
    # chat response with valid json
    mock_chat_resp = MagicMock()
    mock_chat_resp.status_code = 200
    mock_chat_resp.json.return_value = {
        "message": {"content": sample_sg_json}
    }
    mock_client.post.return_value = mock_chat_resp
    
    ollama_planner = OllamaStoryPlannerImpl(
        base_url="http://localhost:11434",
        model="llama3.2",
        http_client=mock_client,
    )
    
    sg = ollama_planner.plan_story("Kısa test sahnesi 10 saniye")
    assert isinstance(sg, SceneGraph)
    assert sg.schema_version == "1.0"
    assert sg.title == sample_sg.title
    assert len(sg.scenes) == len(sample_sg.scenes)
