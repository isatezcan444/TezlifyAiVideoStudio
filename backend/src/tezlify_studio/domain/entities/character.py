from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Dict, Any

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

@dataclass
class Character:
    id: str
    name: str
    description: str = ""
    gender: str = "neutral"
    palette: CharacterColorPalette = field(default_factory=CharacterColorPalette)
    hair_style: str = HairStyle.SHORT_PARTED.value
    eye_style: str = EyeStyle.ROUND.value
    clothing_style: str = ClothingStyle.CASUAL.value
    voice_id: str = ""
    default_expression: CharacterExpression = CharacterExpression.NEUTRAL
    default_pose: CharacterPose = CharacterPose.STANDING
    proportions: BodyProportions = field(default_factory=BodyProportions)
    blend_file_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    is_builtin: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def update_profile(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        gender: Optional[str] = None,
        voice_id: Optional[str] = None,
    ) -> None:
        if name is not None:
            clean_name = name.strip()
            if not clean_name:
                raise ValueError("Karakter adı boş olamaz.")
            self.name = clean_name
        if description is not None:
            self.description = description
        if gender is not None:
            self.gender = gender
        if voice_id is not None:
            self.voice_id = voice_id
        self.updated_at = datetime.now(timezone.utc)

    def update_appearance(
        self,
        palette: Optional[CharacterColorPalette] = None,
        hair_style: Optional[str] = None,
        eye_style: Optional[str] = None,
        clothing_style: Optional[str] = None,
        proportions: Optional[BodyProportions] = None,
    ) -> None:
        if palette is not None:
            self.palette = palette
        if hair_style is not None:
            self.hair_style = hair_style
        if eye_style is not None:
            self.eye_style = eye_style
        if clothing_style is not None:
            self.clothing_style = clothing_style
        if proportions is not None:
            self.proportions = proportions
        self.updated_at = datetime.now(timezone.utc)

    def update_defaults(
        self,
        default_expression: Optional[CharacterExpression] = None,
        default_pose: Optional[CharacterPose] = None,
    ) -> None:
        if default_expression is not None:
            self.default_expression = default_expression
        if default_pose is not None:
            self.default_pose = default_pose
        self.updated_at = datetime.now(timezone.utc)

    def set_asset_paths(
        self,
        blend_file_path: Optional[str] = None,
        thumbnail_path: Optional[str] = None,
    ) -> None:
        if blend_file_path is not None:
            self.blend_file_path = blend_file_path
        if thumbnail_path is not None:
            self.thumbnail_path = thumbnail_path
        self.updated_at = datetime.now(timezone.utc)
