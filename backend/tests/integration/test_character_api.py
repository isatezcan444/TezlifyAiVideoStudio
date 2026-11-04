import pytest
from fastapi.testclient import TestClient
from tezlify_studio.presentation.api.app import app

client = TestClient(app)

def test_api_list_characters_and_builtin_seeded():
    res = client.get("/api/v1/studio/characters")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 2
    char_ids = [c["id"] for c in data["items"]]
    assert "char_ali" in char_ids
    assert "char_ayse" in char_ids

def test_api_character_crud_lifecycle():
    # 1. Create a custom character
    create_payload = {
        "name": "Mert Test",
        "description": "Özel test karakteri",
        "gender": "male",
        "palette": {
            "skin_tone": "#F5D0A9",
            "hair_color": "#1F2937",
            "shirt_color": "#6366F1",
            "pants_color": "#111827",
            "shoes_color": "#000000",
            "eye_color": "#1E293B"
        },
        "hair_style": "short_parted",
        "default_expression": "cheerful",
        "default_pose": "standing"
    }

    create_res = client.post("/api/v1/studio/characters", json=create_payload)
    assert create_res.status_code == 201
    char_data = create_res.json()
    char_id = char_data["id"]
    assert char_data["name"] == "Mert Test"
    assert char_data["palette"]["shirt_color"] == "#6366F1"
    assert char_data["is_builtin"] is False

    # 2. Get character details
    get_res = client.get(f"/api/v1/studio/characters/{char_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == char_id

    # 3. Update character
    update_payload = {
        "name": "Mert Test Updated",
        "palette": {
            "shirt_color": "#EC4899"
        },
        "default_expression": "surprised"
    }
    update_res = client.put(f"/api/v1/studio/characters/{char_id}", json=update_payload)
    assert update_res.status_code == 200
    assert update_res.json()["name"] == "Mert Test Updated"
    assert update_res.json()["palette"]["shirt_color"] == "#EC4899"
    assert update_res.json()["default_expression"] == "surprised"

    # 4. Delete character
    del_res = client.delete(f"/api/v1/studio/characters/{char_id}")
    assert del_res.status_code == 200
    assert del_res.json()["deleted"] is True

    # 5. Verify 404 after deletion
    assert client.get(f"/api/v1/studio/characters/{char_id}").status_code == 404

def test_api_builtin_character_cannot_be_deleted():
    # Attempting to delete char_ali should return 400
    del_res = client.delete("/api/v1/studio/characters/char_ali")
    assert del_res.status_code == 400
    assert "silinemez" in del_res.text.lower()

def test_api_character_thumbnail_endpoint():
    res = client.get("/api/v1/studio/characters/char_ali/thumbnail")
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/png"
    assert len(res.content) > 1000

def test_api_list_assets_and_categories():
    # All assets
    all_res = client.get("/api/v1/studio/assets")
    assert all_res.status_code == 200
    all_data = all_res.json()
    assert all_data["total"] >= 10

    # Filter backgrounds
    bg_res = client.get("/api/v1/studio/assets?category=background")
    assert bg_res.status_code == 200
    bg_data = bg_res.json()
    assert all(item["category"] == "background" for item in bg_data["items"])
    assert any(item["id"] == "bg_modern_cafe" for item in bg_data["items"])

    # Filter props
    prop_res = client.get("/api/v1/studio/assets?category=prop")
    assert prop_res.status_code == 200
    prop_data = prop_res.json()
    assert all(item["category"] == "prop" for item in prop_data["items"])
    assert any(item["id"] == "prop_table" for item in prop_data["items"])

def test_api_asset_details_and_thumbnail():
    detail_res = client.get("/api/v1/studio/assets/bg_modern_cafe")
    assert detail_res.status_code == 200
    assert detail_res.json()["name"] == "Modern Kafe"

    thumb_res = client.get("/api/v1/studio/assets/bg_modern_cafe/thumbnail")
    assert thumb_res.status_code == 200
    assert thumb_res.headers["content-type"] == "image/png"

def test_api_character_and_asset_not_found():
    assert client.get("/api/v1/studio/characters/non_existent_char_999").status_code == 404
    assert client.get("/api/v1/studio/assets/non_existent_asset_999").status_code == 404

def test_api_invalid_color_hex_rejected():
    invalid_payload = {
        "name": "Invalid Color Guy",
        "palette": {
            "skin_tone": "NOT_A_HEX"
        }
    }
    res = client.post("/api/v1/studio/characters", json=invalid_payload)
    assert res.status_code == 422
