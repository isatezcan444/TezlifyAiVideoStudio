import uuid
from typing import Optional
from tezlify_studio.application.ports.character_repository_port import CharacterRepositoryPort
from tezlify_studio.application.ports.blender_asset_generator_port import BlenderAssetGeneratorPort
from tezlify_studio.application.dto.character_dto import CharacterDTO, CreateCharacterRequestDTO
from tezlify_studio.application.dto.mappers import character_to_dto
from tezlify_studio.domain.entities.character import Character
from tezlify_studio.domain.enums.studio_status import (
    CharacterExpression,
    CharacterPose,
    HairStyle,
    EyeStyle,
    ClothingStyle,
)
from tezlify_studio.domain.value_objects.character_models import (
    CharacterColorPalette,
    BodyProportions,
)
from tezlify_studio.domain.exceptions.studio_exceptions import DuplicateCharacterIdException

class CreateCharacterUseCase:
    def __init__(
        self,
        char_repo: CharacterRepositoryPort,
        blender_gen: Optional[BlenderAssetGeneratorPort] = None,
    ):
        self.char_repo = char_repo
        self.blender_gen = blender_gen

    def execute(self, req: CreateCharacterRequestDTO) -> CharacterDTO:
        clean_name = req.name.strip()
        if not clean_name:
            raise ValueError("Karakter adı boş olamaz.")

        char_id = req.id.strip() if req.id else f"char_{uuid.uuid4().hex[:8]}"

        existing = self.char_repo.get_by_id(char_id)
        if existing:
            raise DuplicateCharacterIdException(char_id)

        palette = CharacterColorPalette(**(req.palette or {}))
        proportions = BodyProportions(**(req.proportions or {}))

        character = Character(
            id=char_id,
            name=clean_name,
            description=req.description or "",
            gender=req.gender or "neutral",
            palette=palette,
            hair_style=req.hair_style or HairStyle.SHORT_PARTED.value,
            eye_style=req.eye_style or EyeStyle.ROUND.value,
            clothing_style=req.clothing_style or ClothingStyle.CASUAL.value,
            voice_id=req.voice_id or "",
            default_expression=CharacterExpression(req.default_expression or "neutral"),
            default_pose=CharacterPose(req.default_pose or "standing"),
            proportions=proportions,
            is_builtin=False,
        )

        # Generate Blender assets if generator available
        if self.blender_gen:
            try:
                blend_path, thumb_path = self.blender_gen.generate_character_assets(character)
                character.set_asset_paths(blend_file_path=blend_path, thumbnail_path=thumb_path)
            except Exception as e:
                # Log but do not block domain creation
                pass

        saved = self.char_repo.save(character)
        return character_to_dto(saved)
