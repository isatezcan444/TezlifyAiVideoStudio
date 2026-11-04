from abc import ABC, abstractmethod
from typing import Tuple, Optional
from tezlify_studio.domain.entities.character import Character
from tezlify_studio.domain.entities.studio_asset import StudioAsset

class BlenderAssetGeneratorPort(ABC):
    @abstractmethod
    def generate_character_assets(
        self,
        character: Character,
        force_regenerate: bool = False,
    ) -> Tuple[str, str]:
        """
        Generates Blender .blend model and high-res PNG thumbnail for character.
        Returns (blend_file_path, thumbnail_path).
        """
        pass

    @abstractmethod
    def generate_scene_asset(
        self,
        asset: StudioAsset,
        force_regenerate: bool = False,
    ) -> Tuple[str, str]:
        """
        Generates Blender .blend model and high-res PNG thumbnail for background/prop.
        Returns (blend_file_path, thumbnail_path).
        """
        pass
