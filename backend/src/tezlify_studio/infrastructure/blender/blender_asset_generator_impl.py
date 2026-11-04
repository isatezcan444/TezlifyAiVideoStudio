import os
import sys
import subprocess
import logging
from typing import Tuple, Optional

from tezlify_studio.application.ports.blender_asset_generator_port import BlenderAssetGeneratorPort
from tezlify_studio.domain.entities.character import Character
from tezlify_studio.domain.entities.studio_asset import StudioAsset
from tezlify_studio.domain.exceptions.studio_exceptions import BlenderRenderException
from tezlify_studio.infrastructure.configuration.settings import settings

logger = logging.getLogger(__name__)

class BlenderAssetGeneratorImpl(BlenderAssetGeneratorPort):
    def __init__(
        self,
        assets_base_dir: Optional[str] = None,
        blender_executable: Optional[str] = None,
        timeout_seconds: float = 30.0,
    ):
        self.base_dir = assets_base_dir or os.path.join(settings.resolved_data_dir, "studio_assets")
        self.blender_bin = blender_executable or self._find_blender()
        self.timeout_seconds = timeout_seconds

        # Ensure subdirectories
        os.makedirs(os.path.join(self.base_dir, "characters"), exist_ok=True)
        os.makedirs(os.path.join(self.base_dir, "backgrounds"), exist_ok=True)
        os.makedirs(os.path.join(self.base_dir, "props"), exist_ok=True)
        os.makedirs(os.path.join(self.base_dir, "thumbnails"), exist_ok=True)

    def _find_blender(self) -> str:
        for candidate in [
            "/opt/homebrew/bin/blender",
            "/usr/local/bin/blender",
            "/Applications/Blender.app/Contents/MacOS/Blender",
        ]:
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate
        return "blender"

    def _get_builder_script_path(self, script_name: str) -> str:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(current_dir, script_name)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Blender builder script not found: {path}")
        return path

    def generate_character_assets(
        self,
        character: Character,
        force_regenerate: bool = False,
    ) -> Tuple[str, str]:
        char_dir = os.path.join(self.base_dir, "characters", character.id)
        os.makedirs(char_dir, exist_ok=True)

        blend_path = os.path.join(char_dir, f"{character.id}.blend")
        thumb_path = os.path.join(self.base_dir, "thumbnails", f"{character.id}.png")

        # Caching check
        if not force_regenerate and os.path.exists(blend_path) and os.path.exists(thumb_path):
            if os.path.getsize(blend_path) > 1024 and os.path.getsize(thumb_path) > 1024:
                return blend_path, thumb_path

        script_path = self._get_builder_script_path("blender_character_builder.py")

        cmd = [
            self.blender_bin,
            "-b",
            "-P", script_path,
            "--",
            "--char-id", character.id,
            "--name", character.name,
            "--gender", character.gender,
            "--skin-tone", character.palette.skin_tone,
            "--hair-color", character.palette.hair_color,
            "--hair-style", character.hair_style,
            "--shirt-color", character.palette.shirt_color,
            "--pants-color", character.palette.pants_color,
            "--shoes-color", character.palette.shoes_color,
            "--eye-color", character.palette.eye_color,
            "--eye-style", character.eye_style,
            "--expression", character.default_expression.value,
            "--pose", character.default_pose.value,
            "--head-scale", str(character.proportions.head_scale),
            "--torso-length", str(character.proportions.torso_length),
            "--arm-length", str(character.proportions.arm_length),
            "--leg-length", str(character.proportions.leg_length),
            "--shoulder-width", str(character.proportions.shoulder_width),
            "--output-blend", blend_path,
            "--output-thumb", thumb_path,
        ]

        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
            if res.returncode != 0:
                logger.error("Blender character generation failed: %s", res.stderr)
                raise BlenderRenderException(
                    f"Karakter '{character.name}' Blender varlığı üretilemedi.",
                    details=res.stderr
                )

            if not os.path.exists(blend_path) or not os.path.exists(thumb_path):
                raise BlenderRenderException("Blender çıktı dosyaları diske yazılamadı.")

            return blend_path, thumb_path

        except subprocess.TimeoutExpired as e:
            logger.error("Blender process timed out for character %s", character.id)
            raise BlenderRenderException(f"Blender karakter üretimi zaman aşımına uğradı ({self.timeout_seconds}s).") from e

    def generate_scene_asset(
        self,
        asset: StudioAsset,
        force_regenerate: bool = False,
    ) -> Tuple[str, str]:
        sub_folder = "backgrounds" if asset.id.startswith("bg_") else "props"
        target_dir = os.path.join(self.base_dir, sub_folder)
        os.makedirs(target_dir, exist_ok=True)

        blend_path = os.path.join(target_dir, f"{asset.id}.blend")
        thumb_path = os.path.join(self.base_dir, "thumbnails", f"{asset.id}.png")

        # Caching check
        if not force_regenerate and os.path.exists(blend_path) and os.path.exists(thumb_path):
            if os.path.getsize(blend_path) > 1024 and os.path.getsize(thumb_path) > 1024:
                return blend_path, thumb_path

        script_path = self._get_builder_script_path("blender_scene_asset_builder.py")

        cmd = [
            self.blender_bin,
            "-b",
            "-P", script_path,
            "--",
            "--asset-id", asset.id,
            "--output-blend", blend_path,
            "--output-thumb", thumb_path,
        ]

        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
            if res.returncode != 0:
                logger.error("Blender scene asset generation failed: %s", res.stderr)
                raise BlenderRenderException(
                    f"Varlık '{asset.name}' Blender varlığı üretilemedi.",
                    details=res.stderr
                )

            if not os.path.exists(blend_path) or not os.path.exists(thumb_path):
                raise BlenderRenderException("Blender varlık dosyaları diske yazılamadı.")

            return blend_path, thumb_path

        except subprocess.TimeoutExpired as e:
            logger.error("Blender process timed out for asset %s", asset.id)
            raise BlenderRenderException(f"Blender varlık üretimi zaman aşımına uğradı ({self.timeout_seconds}s).") from e
