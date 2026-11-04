import os
import tempfile
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from tezlify_studio.domain.entities.render_job import RenderJob
from tezlify_studio.domain.enums.studio_status import RenderJobStatus
from tezlify_studio.domain.value_objects.render_metadata import RenderOutputMetadata
from tezlify_studio.infrastructure.persistence.database import SessionLocal
from tezlify_studio.infrastructure.persistence.repositories.render_job_repository_impl import (
    RenderJobRepositoryImpl,
)
from tezlify_studio.presentation.api.app import app
from tezlify_studio.presentation.dependencies.container import (
    get_execute_composition_render_use_case,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def mock_composition_worker():
    mock_exec = MagicMock()
    app.dependency_overrides[get_execute_composition_render_use_case] = lambda: mock_exec
    yield mock_exec
    app.dependency_overrides.pop(get_execute_composition_render_use_case, None)


def create_composition_project() -> str:
    payload = {
        "title": "Kompozisyon API Projesi",
        "description": "Stage 4.5 integration test",
        "scene_graph": {
            "schema_version": "1.0",
            "project_id": "proj_comp_api",
            "title": "Kompozisyon API Projesi",
            "resolution": {"width": 1920, "height": 1080, "fps": 30, "aspect_ratio": "16:9"},
            "characters": [
                {"id": "char_ali", "name": "Ali"},
                {"id": "char_ayse", "name": "Ayşe"},
            ],
            "scenes": [
                {
                    "scene_id": "scene_01",
                    "sequence_order": 1,
                    "duration_seconds": 3.0,
                    "character_placements": [
                        {"character_id": "char_ali", "position": [-0.7, 0.0, 0.0]},
                        {"character_id": "char_ayse", "position": [0.7, 0.0, 0.0]},
                    ],
                },
                {
                    "scene_id": "scene_02",
                    "sequence_order": 2,
                    "duration_seconds": 4.0,
                    "character_placements": [
                        {"character_id": "char_ali", "position": [-0.7, 0.0, 0.0]},
                    ],
                    "dialogues": [
                        {
                            "character_id": "char_ali",
                            "start_time": 0.5,
                            "end_time": 2.0,
                            "text": "Merhaba Ayşe!",
                        }
                    ],
                },
                {
                    "scene_id": "scene_03",
                    "sequence_order": 3,
                    "duration_seconds": 2.5,
                    "character_placements": [
                        {"character_id": "char_ayse", "position": [0.7, 0.0, 0.0]},
                    ],
                },
            ],
        },
    }
    response = client.post("/api/v1/studio/projects", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def composition_payload() -> dict:
    return {
        "id": "comp_test_api",
        "project_id": "will_be_overridden",
        "name": "API Kompozisyonu",
        "format": "9:16",
        "fps": 30,
        "scenes": [
            {
                "scene_id": "scene_03",
                "transition": "crossfade",
                "transition_duration_seconds": 0.6,
            },
            {
                "scene_id": "scene_01",
                "transition": "fade_out",
                "transition_duration_seconds": 0.5,
            },
            {
                "scene_id": "scene_02",
                "transition": "cut",
                "transition_duration_seconds": 0.0,
            },
        ],
        "text_layers": [
            {
                "id": "opening",
                "text": "Açılış: ŞİĞÜÖÇ",
                "start_time": 0.2,
                "end_time": 2.0,
                "anchor": "top_center",
                "x_ratio": 0.5,
                "y_ratio": 0.12,
                "font_size": 64,
                "color": "#FFFFFF",
                "background_color": "#000000",
                "background_opacity": 0.5,
                "fade_in_seconds": 0.3,
                "fade_out_seconds": 0.3,
                "max_width_ratio": 0.82,
                "bold": True,
            }
        ],
        "subtitles": {
            "enabled": True,
            "burn_in": True,
            "save_srt": True,
            "font_size": 46,
            "color": "#FFFFFF",
            "background_color": "#000000",
            "background_opacity": 0.62,
            "margin_bottom_ratio": 0.075,
            "max_width_ratio": 0.84,
            "max_chars_per_line": 44,
        },
        "audio": {
            "dialogue_volume_db": 0.0,
            "music_file": None,
            "music_volume_db": -20.0,
            "limiter_enabled": True,
            "limiter_limit": 0.95,
        },
        "output_format": "mp4",
    }


def test_get_default_composition_for_project():
    project_id = create_composition_project()
    response = client.get(f"/api/v1/studio/projects/{project_id}/composition")
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["is_saved"] is False
    assert data["scene_count"] == 3
    assert data["composition"]["format"] == "16:9"
    assert [entry["scene_id"] for entry in data["timeline"]] == ["scene_01", "scene_02", "scene_03"]
    assert data["total_duration_seconds"] == pytest.approx(9.5)


def test_save_composition_reorders_scenes_and_changes_format():
    project_id = create_composition_project()
    response = client.put(
        f"/api/v1/studio/projects/{project_id}/composition",
        json={"composition": composition_payload()},
    )
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["is_saved"] is True
    assert data["composition"]["format"] == "9:16"
    assert data["composition"]["width"] == 1080
    assert data["composition"]["height"] == 1920
    assert [entry["scene_id"] for entry in data["timeline"]] == ["scene_03", "scene_01", "scene_02"]
    # 9.5s - 0.6s crossfade
    assert data["total_duration_seconds"] == pytest.approx(8.9)
    assert data["transition_count"] == 2

    get_response = client.get(f"/api/v1/studio/projects/{project_id}/composition")
    assert get_response.status_code == 200
    assert get_response.json()["composition"]["name"] == "API Kompozisyonu"


def test_save_composition_rejects_missing_scene():
    project_id = create_composition_project()
    payload = composition_payload()
    payload["scenes"] = payload["scenes"][:2]

    response = client.put(
        f"/api/v1/studio/projects/{project_id}/composition",
        json={"composition": payload},
    )
    assert response.status_code == 400
    assert response.json()["error_code"] == "INVALID_COMPOSITION"


def test_get_composition_for_missing_project_returns_404():
    response = client.get("/api/v1/studio/projects/does-not-exist/composition")
    assert response.status_code == 404
    assert response.json()["error_code"] == "PROJECT_NOT_FOUND"


def test_start_composition_render_dispatches_job():
    project_id = create_composition_project()
    response = client.post(
        f"/api/v1/studio/projects/{project_id}/composition/render",
        json={"composition": composition_payload(), "synthesize_voices": False},
    )
    assert response.status_code == 202, response.text
    job = response.json()
    assert job["project_id"] == project_id
    assert job["status"] == "pending"
    assert job["id"].startswith("comp_")

    status = client.get(f"/api/v1/studio/renders/{job['id']}")
    assert status.status_code == 200
    assert status.json()["id"] == job["id"]

    listed = client.get(f"/api/v1/studio/projects/{project_id}/renders")
    assert listed.status_code == 200
    assert any(item["id"] == job["id"] for item in listed.json()["items"])


def test_download_composition_subtitles_endpoint():
    project_id = create_composition_project()
    db = SessionLocal()
    srt_path = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".srt", delete=False, encoding="utf-8") as handle:
            handle.write("1\n00:00:00,000 --> 00:00:01,000\nMerhaba ŞİĞÜÖÇ\n")
            srt_path = handle.name

        repo = RenderJobRepositoryImpl(db)
        job = RenderJob(id="comp_subtitle_job", project_id=project_id, status=RenderJobStatus.PENDING)
        job.complete(
            video_path="/tmp/nonexistent.mp4",
            metadata=RenderOutputMetadata(
                video_file_path="/tmp/nonexistent.mp4",
                duration_seconds=1.0,
                subtitle_file_path=srt_path,
            ),
        )
        repo.save(job)

        response = client.get("/api/v1/studio/renders/comp_subtitle_job/subtitles")
        assert response.status_code == 200
        assert "Merhaba ŞİĞÜÖÇ" in response.text
        assert "application/x-subrip" in response.headers.get("content-type", "")
    finally:
        db.close()
        if srt_path and os.path.exists(srt_path):
            os.unlink(srt_path)
