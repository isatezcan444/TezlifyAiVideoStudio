import pytest
from tezlify_studio.domain.entities.character import Character
from tezlify_studio.domain.enums.studio_status import (
    CharacterPose,
    CharacterExpression,
    HairStyle,
    EyeStyle,
    ClothingStyle,
)
from tezlify_studio.domain.value_objects.character_models import (
    CharacterColorPalette,
    BodyProportions,
)
from tezlify_studio.domain.exceptions.studio_exceptions import InvalidColorHexException

def test_character_color_palette_valid():
    palette = CharacterColorPalette(
        skin_tone="#F5D0A9",
        hair_color="#2C1810",
        eye_color="#1E293B",
        shirt_color="#3B82F6",
        pants_color="#1E293B",
        shoes_color="#0F172A",
    )
    assert palette.skin_tone == "#F5D0A9"
    assert palette.hair_color == "#2C1810"
    assert palette.shirt_color == "#3B82F6"

def test_character_color_palette_invalid_hex():
    with pytest.raises(InvalidColorHexException) as exc_info:
        CharacterColorPalette(skin_tone="invalid_hex_color")
    assert "skin_tone" in str(exc_info.value)
    assert exc_info.value.error_code == "INVALID_HEX_COLOR"

    with pytest.raises(InvalidColorHexException):
        CharacterColorPalette(shirt_color="#12345")  # Too short

    with pytest.raises(InvalidColorHexException):
        CharacterColorPalette(pants_color="#GGG123")  # Non-hex chars

def test_body_proportions_validation():
    # Valid
    props = BodyProportions(head_scale=1.2, torso_length=0.9)
    assert props.head_scale == 1.2
    assert props.torso_length == 0.9

    # Out of bounds
    with pytest.raises(Exception):
        BodyProportions(head_scale=0.1)  # ge=0.5

    with pytest.raises(Exception):
        BodyProportions(head_scale=3.5)  # le=2.0

def test_character_entity_creation_and_updates():
    char = Character(
        id="char_test_1",
        name="Test Ali",
        gender="male",
        palette=CharacterColorPalette(shirt_color="#10B981"),
        hair_style=HairStyle.SHORT_PARTED.value,
        eye_style=EyeStyle.ROUND.value,
        default_expression=CharacterExpression.CHEERFUL,
        default_pose=CharacterPose.STANDING,
    )
    assert char.id == "char_test_1"
    assert char.name == "Test Ali"
    assert char.default_expression == CharacterExpression.CHEERFUL
    assert char.default_pose == CharacterPose.STANDING
    assert char.is_builtin is False

    # Update profile
    char.update_profile(name="Test Ali Updated", description="Yeni açıklama")
    assert char.name == "Test Ali Updated"
    assert char.description == "Yeni açıklama"

    # Update empty name raises ValueError
    with pytest.raises(ValueError):
        char.update_profile(name="   ")

    # Update appearance
    new_palette = CharacterColorPalette(shirt_color="#EC4899")
    char.update_appearance(palette=new_palette, hair_style=HairStyle.BOB_CUT.value)
    assert char.palette.shirt_color == "#EC4899"
    assert char.hair_style == HairStyle.BOB_CUT.value

    # Update defaults
    char.update_defaults(default_expression=CharacterExpression.SURPRISED, default_pose=CharacterPose.GESTURING)
    assert char.default_expression == CharacterExpression.SURPRISED
    assert char.default_pose == CharacterPose.GESTURING

    # Set asset paths
    char.set_asset_paths("/path/to/ali.blend", "/path/to/ali.png")
    assert char.blend_file_path == "/path/to/ali.blend"
    assert char.thumbnail_path == "/path/to/ali.png"
