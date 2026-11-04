import os
import pytest
from tezlify_studio.infrastructure.blender.blender_asset_generator_impl import BlenderAssetGeneratorImpl
from tezlify_studio.domain.entities.character import Character
from tezlify_studio.domain.entities.studio_asset import StudioAsset
from tezlify_studio.domain.enums.studio_status import (
    AssetCategory,
    AssetFormat,
    CharacterPose,
    CharacterExpression,
    HairStyle,
)
from tezlify_studio.domain.value_objects.character_models import CharacterColorPalette

def test_blender_character_generation():
    gen = BlenderAssetGeneratorImpl()

    ali = Character(
        id="char_ali",
        name="Ali",
        gender="male",
        palette=CharacterColorPalette(
            skin_tone="#F5D0A9",
            hair_color="#2C1810",
            shirt_color="#3B82F6",
            pants_color="#1E293B",
        ),
        hair_style=HairStyle.SHORT_PARTED.value,
        default_expression=CharacterExpression.CHEERFUL,
        default_pose=CharacterPose.STANDING,
    )

    blend_path, thumb_path = gen.generate_character_assets(ali)

    assert os.path.exists(blend_path)
    assert os.path.getsize(blend_path) > 10000  # Valid .blend file
    assert os.path.exists(thumb_path)
    assert os.path.getsize(thumb_path) > 5000   # Valid PNG image

    # Test Ayşe
    ayse = Character(
        id="char_ayse",
        name="Ayşe",
        gender="female",
        palette=CharacterColorPalette(
            skin_tone="#FCE7D0",
            hair_color="#B45309",
            shirt_color="#EC4899",
            pants_color="#334155",
        ),
        hair_style=HairStyle.BOB_CUT.value,
        default_expression=CharacterExpression.CHEERFUL,
        default_pose=CharacterPose.STANDING,
    )

    blend_ayse, thumb_ayse = gen.generate_character_assets(ayse)
    assert os.path.exists(blend_ayse)
    assert os.path.getsize(blend_ayse) > 10000
    assert os.path.exists(thumb_ayse)
    assert os.path.getsize(thumb_ayse) > 5000

def test_blender_scene_asset_generation():
    gen = BlenderAssetGeneratorImpl()

    cafe_asset = StudioAsset(
        id="bg_modern_cafe",
        name="Modern Kafe",
        category=AssetCategory.BACKGROUND,
        description="Sıcak iç mekan kahve dükkanı",
        file_path="",
        asset_format=AssetFormat.BLEND,
    )

    blend_path, thumb_path = gen.generate_scene_asset(cafe_asset)

    assert os.path.exists(blend_path)
    assert os.path.getsize(blend_path) > 5000
    assert os.path.exists(thumb_path)
    assert os.path.getsize(thumb_path) > 5000

def test_blender_generator_caching():
    gen = BlenderAssetGeneratorImpl()

    char = Character(
        id="char_ali",
        name="Ali",
        gender="male",
        palette=CharacterColorPalette(),
    )

    # First call uses existing cache (or generates)
    b1, t1 = gen.generate_character_assets(char, force_regenerate=False)
    # Second call returns immediately from cache
    b2, t2 = gen.generate_character_assets(char, force_regenerate=False)

    assert b1 == b2
    assert t1 == t2
