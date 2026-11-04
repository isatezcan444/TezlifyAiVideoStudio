import pytest
from fastapi.testclient import TestClient
from tezlify_studio.presentation.api.app import app

client = TestClient(app)

def test_api_generate_story():
    payload = {
        "prompt": "İki karakter kafede komik diyalog yapıyor 30 saniye",
        "aspect_ratio": "16:9",
        "genre": "comedy"
    }
    res = client.post("/api/v1/studio/generate-story", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "scene_graph" in data
    assert data["scene_graph"]["schema_version"] == "1.0"
    assert data["total_duration_seconds"] >= 20
    assert data["scene_count"] >= 2
    assert data["character_count"] >= 2

def test_api_generate_story_validation_error():
    # Empty prompt should be rejected
    payload = {
        "prompt": "   ",
        "aspect_ratio": "16:9"
    }
    res = client.post("/api/v1/studio/generate-story", json=payload)
    assert res.status_code == 422

def test_api_studio_crud_lifecycle():
    # 1. Create a project
    create_payload = {
        "title": "API Test Animation",
        "description": "Integration test created project"
    }
    create_res = client.post("/api/v1/studio/projects", json=create_payload)
    assert create_res.status_code == 201
    created = create_res.json()
    project_id = created["id"]
    assert created["title"] == "API Test Animation"
    assert created["status"] == "draft"

    # 2. Get the project by ID
    get_res = client.get(f"/api/v1/studio/projects/{project_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == project_id
    assert get_res.json()["title"] == "API Test Animation"

    # 3. List projects and find the created one
    list_res = client.get("/api/v1/studio/projects?limit=20&offset=0")
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total"] >= 1
    assert any(p["id"] == project_id for p in list_data["items"])

    # 4. Update the project
    update_payload = {
        "title": "API Test Animation - Renamed",
        "description": "Updated description",
        "status": "scenario_ready"
    }
    update_res = client.put(f"/api/v1/studio/projects/{project_id}", json=update_payload)
    assert update_res.status_code == 200
    updated = update_res.json()
    assert updated["title"] == "API Test Animation - Renamed"
    assert updated["status"] == "scenario_ready"

    # 5. Delete the project
    del_res = client.delete(f"/api/v1/studio/projects/{project_id}")
    assert del_res.status_code == 200
    assert del_res.json()["deleted"] is True

    # 6. Verify 404 after deletion
    after_del_res = client.get(f"/api/v1/studio/projects/{project_id}")
    assert after_del_res.status_code == 404

def test_api_studio_project_not_found():
    non_existent = "non-existent-proj-uuid-1234"
    assert client.get(f"/api/v1/studio/projects/{non_existent}").status_code == 404
    assert client.put(f"/api/v1/studio/projects/{non_existent}", json={"title": "Test"}).status_code == 404
    assert client.delete(f"/api/v1/studio/projects/{non_existent}").status_code == 404

def test_api_create_project_with_generated_scenegraph():
    # 1. Generate story
    gen_res = client.post("/api/v1/studio/generate-story", json={"prompt": "Bilim kurgu uzay hikayesi 20 saniye"})
    assert gen_res.status_code == 200
    sg_data = gen_res.json()["scene_graph"]

    # 2. Create project using the generated scene graph
    create_payload = {
        "title": sg_data["title"],
        "description": sg_data["description"],
        "scene_graph": sg_data
    }
    create_res = client.post("/api/v1/studio/projects", json=create_payload)
    assert create_res.status_code == 201
    proj = create_res.json()
    proj_id = proj["id"]
    assert proj["scene_graph"] is not None
    assert proj["scene_graph"]["schema_version"] == "1.0"
    assert len(proj["scene_graph"]["scenes"]) >= 1

    # Cleanup
    client.delete(f"/api/v1/studio/projects/{proj_id}")
