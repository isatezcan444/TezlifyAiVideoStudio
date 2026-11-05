"""Guard that the video-generation product surface stays removed.

These assertions are deliberately source-level: deleting a route or a module can
silently come back through an import, so the check covers both the tree and the
live OpenAPI schema.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from tezlify_studio.presentation.api.app import app

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_SRC = REPO_ROOT / "backend" / "src" / "tezlify_studio"
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"

REMOVED_PACKAGES = [
    "infrastructure/blender",
    "infrastructure/ai",
    "infrastructure/alignment",
    "infrastructure/video",
    "application/use_cases/render_video_use_case.py",
    "application/use_cases/generate_story_use_case.py",
    "domain/value_objects/scene_graph.py",
    "domain/services/story_planner.py",
]

FORBIDDEN_IMPORT_FRAGMENTS = [
    "infrastructure.blender",
    "infrastructure.ai",
    "infrastructure.alignment",
    "infrastructure.video",
    "studio_models",
    "studio_exceptions",
    "render_job",
    "render_worker",
    "composition_",
    "character_repository",
    "studio_asset_repository",
    "voice_port",
    "lip_sync",
]


@pytest.mark.parametrize("relative", REMOVED_PACKAGES)
def test_generation_module_is_gone(relative: str) -> None:
    assert not (BACKEND_SRC / relative).exists(), f"{relative} should be deleted"


def test_no_backend_module_imports_generation_code() -> None:
    offenders = []
    for path in BACKEND_SRC.rglob("*.py"):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if line.lstrip().startswith("#"):
                continue
            for fragment in FORBIDDEN_IMPORT_FRAGMENTS:
                if fragment in line:
                    offenders.append(f"{path.relative_to(REPO_ROOT)}:{number}: {fragment}")
    assert offenders == []


def test_no_frontend_studio_generation_screens() -> None:
    removed_paths = [
        "components/studio",
        "pages/CompositionStudioPage.tsx",
        "pages/CharacterStudioPage.tsx",
        "pages/StudioWorkspacePage.tsx",
        "lib/composition.ts",
        "types/studio.ts",
    ]
    for relative in removed_paths:
        assert not (FRONTEND_SRC / relative).exists(), f"{relative} should be deleted"

    app_source = (FRONTEND_SRC / "App.tsx").read_text(encoding="utf-8")
    for fragment in ("studio-workspace", "composition-studio", "character-studio"):
        assert fragment not in app_source


def test_api_surface_has_no_generation_endpoints() -> None:
    paths = set(app.openapi()["paths"])

    assert not [path for path in paths if "/studio" in path or "/renders" in path]
    assert not [path for path in paths if "compos" in path or "character" in path]

    for expected in (
        "/api/v1/dashboard",
        "/api/v1/platforms",
        "/api/v1/channels/youtube/overview",
        "/api/v1/channels/youtube/analytics",
        "/api/v1/comments",
        "/api/v1/social/youtube/publish",
        "/api/v1/scheduler",
    ):
        assert expected in paths


def test_blender_is_not_a_runtime_requirement() -> None:
    settings_source = (
        BACKEND_SRC / "infrastructure" / "configuration" / "settings.py"
    ).read_text(encoding="utf-8")
    app_source = (BACKEND_SRC / "presentation" / "api" / "app.py").read_text(encoding="utf-8")

    assert "blender" not in settings_source.lower()
    assert "blender" not in app_source.lower()
    # Startup must not wait on (or fail because of) an external 3D binary.
    assert "render_worker" not in app_source
    assert os.path.exists(REPO_ROOT / "backend" / "src" / "tezlify_studio")
