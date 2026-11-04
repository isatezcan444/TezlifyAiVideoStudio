import re
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator

from tezlify_studio.domain.exceptions.studio_exceptions import InvalidColorHexException

HEX_COLOR_REGEX = re.compile(r"^#[0-9A-Fa-f]{6}$")

def validate_hex_color(val: str, field_name: str) -> str:
    if not isinstance(val, str) or not HEX_COLOR_REGEX.match(val.strip()):
        raise InvalidColorHexException(color_field=field_name, value=str(val))
    return val.strip().upper()

class CharacterColorPalette(BaseModel):
    skin_tone: str = Field(default="#F5D0A9")
    hair_color: str = Field(default="#2C1810")
    eye_color: str = Field(default="#1E293B")
    shirt_color: str = Field(default="#3B82F6")
    pants_color: str = Field(default="#1E293B")
    shoes_color: str = Field(default="#0F172A")

    @field_validator("skin_tone")
    @classmethod
    def check_skin(cls, v: str) -> str:
        return validate_hex_color(v, "skin_tone")

    @field_validator("hair_color")
    @classmethod
    def check_hair(cls, v: str) -> str:
        return validate_hex_color(v, "hair_color")

    @field_validator("eye_color")
    @classmethod
    def check_eye(cls, v: str) -> str:
        return validate_hex_color(v, "eye_color")

    @field_validator("shirt_color")
    @classmethod
    def check_shirt(cls, v: str) -> str:
        return validate_hex_color(v, "shirt_color")

    @field_validator("pants_color")
    @classmethod
    def check_pants(cls, v: str) -> str:
        return validate_hex_color(v, "pants_color")

    @field_validator("shoes_color")
    @classmethod
    def check_shoes(cls, v: str) -> str:
        return validate_hex_color(v, "shoes_color")

class BodyProportions(BaseModel):
    head_scale: float = Field(default=1.0, ge=0.5, le=2.0)
    torso_length: float = Field(default=1.0, ge=0.5, le=2.0)
    arm_length: float = Field(default=1.0, ge=0.5, le=2.0)
    leg_length: float = Field(default=1.0, ge=0.5, le=2.0)
    shoulder_width: float = Field(default=1.0, ge=0.5, le=2.0)
