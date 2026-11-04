import os
import tempfile
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from tezlify_studio.presentation.api.app import app
from tezlify_studio.presentation.dependencies.container import get_execute_render_job_use_case
from tezlify_studio.domain.entities.render_job import RenderJob
from tezlify_studio.domain.enums.studio_status import RenderJobStatus
from tezlify_studio.domain.value_objects.render_metadata import RenderOutputMetadata
from tezlify_studio.infrastructure.persistence.database import SessionLocal
from tezlify_studio.infrastructure.persistence.repositories.render_job_repository_impl import RenderJobRepositoryImpl

client = TestClient(app)

@pytest.fixture(autouse=True)
def mock_worker():
    mock_exec = MagicMock()
    app.dependency_overrides[get_execute_render_job_use_case] = lambda: mock_exec
    yield mock_exec
    app.dependency_overrides.pop(get_execute_render_job_use_case, None)

def create_test_project_with_scene():
    project_payload = {
        "title": "API Test Project",
        "description": "Integration test render API",
        "scene_graph": {
            "schema_version": "1.0",
            "project_id": "proj_api_test",
            "title": "API Test Project",
            "resolution": {"width": 1920, "height": 1080, "fps": 30},
            "characters": [
                {"id": "char_ali", "name": "Ali"},
                {"id": "char_ayse", "name": "Ayşe"},
            ],
            "scenes": [
                {
                    "scene_id": "scene_01",
                    "duration_seconds": 5.0,
                    "background": {"type": "preset", "asset_id": "bg_modern_cafe"},
                    "camera": {"angle": "two_shot", "movement": "static"},
                    "character_placements": [
                        {"character_id": "char_ali", "position": [-0.7, 0.0, 0.0], "rotation_y": 30.0},
                        {"character_id": "char_ayse", "position": [0.7, 0.0, 0.0], "rotation_y": -30.0},
                    ],
                    "dialogues": [
                        {"character_id": "char_ali", "start_time": 1.0, "end_time": 3.0, "text": "Selam!"}
                    ],
                }
            ],
        },
    }
    res = client.post("/api/v1/studio/projects", json=project_payload)
    assert res.status_code == 201
    return res.json()["id"]

def test_start_render_non_existent_project():
    res = client.post("/api/v1/studio/projects/non_existent_project_id/render")
    assert res.status_code == 404
    assert res.json()["error_code"] == "PROJECT_NOT_FOUND"

def test_start_render_valid_project():
    proj_id = create_test_project_with_scene()

    # Dispatch render
    res = client.post(f"/api/v1/studio/projects/{proj_id}/render", json={"engine_override": "BLENDER_WORKBENCH"})
    assert res.status_code == 202
    job_data = res.json()
    assert job_data["project_id"] == proj_id
    assert job_data["status"] == "pending"
    assert "render_" in job_data["id"]
    job_id = job_data["id"]

    # Get render job status
    get_res = client.get(f"/api/v1/studio/renders/{job_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == job_id
    assert get_res.json()["project_id"] == proj_id

    # List project renders
    list_res = client.get(f"/api/v1/studio/projects/{proj_id}/renders")
    assert list_res.status_code == 200
    assert list_res.json()["total"] >= 1
    job_ids = [j["id"] for j in list_res.json()["items"]]
    assert job_id in job_ids

    # Global render history used by the unified Studio workspace.
    global_res = client.get("/api/v1/studio/renders?limit=200")
    assert global_res.status_code == 200
    assert global_res.json()["total"] >= 1
    assert job_id in [j["id"] for j in global_res.json()["items"]]

def test_get_render_job_not_found():
    res = client.get("/api/v1/studio/renders/job_does_not_exist")
    assert res.status_code == 404
    assert res.json()["error_code"] == "RENDER_JOB_NOT_FOUND"

def test_stream_render_video():
    proj_id = create_test_project_with_scene()

    db = SessionLocal()
    try:
        repo = RenderJobRepositoryImpl(db)

        # 1. Job without completed video returns 404
        job = RenderJob(
            id="job_stream_test_01",
            project_id=proj_id,
            status=RenderJobStatus.RUNNING,
            progress_percent=50.0,
            output_video_path=None,
        )
        repo.save(job)

        res_404 = client.get(f"/api/v1/studio/renders/{job.id}/video")
        assert res_404.status_code == 404

        # 2. Job with completed real video file returns 200
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp.write(b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2avc1mp41")
            tmp_path = tmp.name

        try:
            job.complete(
                video_path=tmp_path,
                metadata=RenderOutputMetadata(
                    video_file_path=tmp_path,
                    file_size_bytes=os.path.getsize(tmp_path),
                    duration_seconds=5.0,
                    width=1920,
                    height=1080,
                    fps=30,
                ),
            )
            repo.save(job)

            res_200 = client.get(f"/api/v1/studio/renders/{job.id}/video")
            assert res_200.status_code == 200
            assert "video/mp4" in res_200.headers.get("content-type", "")
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    finally:
        db.close()
