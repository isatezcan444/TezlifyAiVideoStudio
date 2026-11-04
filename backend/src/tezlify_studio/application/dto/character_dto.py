from dataclasses import dataclass
from typing import Optional, List, Dict, Any

@dataclass
class CharacterDTO:
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
    blend_file_path: Optional[str]
    thumbnail_path: Optional[str]
    is_builtin: bool
    created_at: str
    updated_at: str

@dataclass
class CreateCharacterRequestDTO:
    name: str
    id: Optional[str] = None
    description: str = ""
    gender: str = "neutral"
    palette: Optional[Dict[str, str]] = None
    hair_style: str = "short_parted"
    eye_style: str = "round"
    clothing_style: str = "casual"
    voice_id: str = ""
    default_expression: str = "neutral"
    default_pose: str = "standing"
    proportions: Optional[Dict[str, float]] = None

@dataclass
class UpdateCharacterRequestDTO:
    name: Optional[str] = None
    description: Optional[str] = None
    gender: Optional[str] = None
    palette: Optional[Dict[str, str]] = None
    hair_style: Optional[str] = None
    eye_style: Optional[str] = None
    clothing_style: Optional[str] = None
    voice_id: Optional[str] = None
    default_expression: Optional[str] = None
    default_pose: Optional[str] = None
    proportions: Optional[Dict[str, float]] = None

@dataclass
class StudioAssetDTO:
    id: str
    name: str
    category: str
    description: str
    file_path: str
    asset_format: str
    thumbnail_path: Optional[str]
    version: str
    tags: List[str]
    is_builtin: bool
    created_at: str
    updated_at: str
