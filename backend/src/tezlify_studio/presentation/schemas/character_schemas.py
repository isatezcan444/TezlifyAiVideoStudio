from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator
import re

HEX_REGEX = re.compile(r"^#[0-9A-Fa-f]{6}$")

def check_hex(v: Optional[str]) -> Optional[str]:
    if v is not None and not HEX_REGEX.match(v.strip()):
        raise ValueError(f"Geçersiz HEX renk kodu '{v}'. Örnek: #3B82F6")
    return v.strip().upper() if v else v

class ColorPaletteSchema(BaseModel):
    skin_tone: Optional[str] = Field(default="#F5D0A9")
    hair_color: Optional[str] = Field(default="#2C1810")
    eye_color: Optional[str] = Field(default="#1E293B")
    shirt_color: Optional[str] = Field(default="#3B82F6")
    pants_color: Optional[str] = Field(default="#1E293B")
    shoes_color: Optional[str] = Field(default="#0F172A")

    @field_validator("skin_tone", "hair_color", "eye_color", "shirt_color", "pants_color", "shoes_color")
    @classmethod
    def validate_hex(cls, v: Optional[str]) -> Optional[str]:
        return check_hex(v)

class BodyProportionsSchema(BaseModel):
    head_scale: float = Field(default=1.0, ge=0.5, le=2.0)
    torso_length: float = Field(default=1.0, ge=0.5, le=2.0)
    arm_length: float = Field(default=1.0, ge=0.5, le=2.0)
    leg_length: float = Field(default=1.0, ge=0.5, le=2.0)
    shoulder_width: float = Field(default=1.0, ge=0.5, le=2.0)

class CreateCharacterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    id: Optional[str] = Field(None, max_length=64)
    description: Optional[str] = Field(default="", max_length=1000)
    gender: Optional[str] = Field(default="neutral", pattern="^(male|female|neutral)$")
    palette: Optional[ColorPaletteSchema] = None
    hair_style: Optional[str] = Field(default="short_parted")
    eye_style: Optional[str] = Field(default="round")
    clothing_style: Optional[str] = Field(default="casual")
    voice_id: Optional[str] = Field(default="", max_length=64)
    default_expression: Optional[str] = Field(default="neutral", pattern="^(neutral|cheerful|surprised|angry|sad|thinking)$")
    default_pose: Optional[str] = Field(default="standing", pattern="^(standing|sitting|sitting_table|walking|gesturing|pointing|idle)$")
    proportions: Optional[BodyProportionsSchema] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Karakter adı boş olamaz.")
        return v.strip()

class UpdateCharacterRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    gender: Optional[str] = Field(None, pattern="^(male|female|neutral)$")
    palette: Optional[ColorPaletteSchema] = None
    hair_style: Optional[str] = None
    eye_style: Optional[str] = None
    clothing_style: Optional[str] = None
    voice_id: Optional[str] = None
    default_expression: Optional[str] = Field(None, pattern="^(neutral|cheerful|surprised|angry|sad|thinking)$")
    default_pose: Optional[str] = Field(None, pattern="^(standing|sitting|sitting_table|walking|gesturing|pointing|idle)$")
    proportions: Optional[BodyProportionsSchema] = None

class CharacterResponse(BaseModel):
    id: str
    name: str
    description: str
    gender: str
    palette: Dict[str, str]
    hair_style: str
    eye_style: str
    clothing_style: str
    voice_id: str
    default_expression: str
    default_pose: str
    proportions: Dict[str, float]
    blend_file_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    is_builtin: bool
    created_at: str
    updated_at: str

class CharacterListResponse(BaseModel):
    items: List[CharacterResponse]
    total: int
    limit: int
    offset: int

class StudioAssetResponse(BaseModel):
    id: str
    name: str
    category: str
    description: str
    file_path: str
    asset_format: str
    thumbnail_path: Optional[str] = None
    version: str
    tags: List[str]
    is_builtin: bool
    created_at: str
    updated_at: str

class StudioAssetListResponse(BaseModel):
    items: List[StudioAssetResponse]
    total: int
    limit: int
    offset: int
