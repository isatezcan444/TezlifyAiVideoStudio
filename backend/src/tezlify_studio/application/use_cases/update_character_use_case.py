from typing import Optional
from tezlify_studio.application.ports.character_repository_port import CharacterRepositoryPort
from tezlify_studio.application.ports.blender_asset_generator_port import BlenderAssetGeneratorPort
from tezlify_studio.application.dto.character_dto import CharacterDTO, UpdateCharacterRequestDTO
from tezlify_studio.application.dto.mappers import character_to_dto
from tezlify_studio.domain.enums.studio_status import CharacterExpression, CharacterPose
from tezlify_studio.domain.value_objects.character_models import CharacterColorPalette, BodyProportions
from tezlify_studio.domain.exceptions.studio_exceptions import CharacterNotFoundException

class UpdateCharacterUseCase:
    def __init__(
        self,
        char_repo: CharacterRepositoryPort,
        blender_gen: Optional[BlenderAssetGeneratorPort] = None,
    ):
        self.char_repo = char_repo
        self.blender_gen = blender_gen

    def execute(self, character_id: str, req: UpdateCharacterRequestDTO) -> CharacterDTO:
        character = self.char_repo.get_by_id(character_id)
        if not character:
            raise CharacterNotFoundException(character_id)

        # Profile update
        character.update_profile(
            name=req.name,
            description=req.description,
            gender=req.gender,
            voice_id=req.voice_id,
        )

        # Appearance update
        new_palette = CharacterColorPalette(**req.palette) if req.palette is not None else None
        new_proportions = BodyProportions(**req.proportions) if req.proportions is not None else None

        appearance_changed = any([
            new_palette is not None,
            req.hair_style is not None and req.hair_style != character.hair_style,
            req.clothing_style is not None and req.clothing_style != character.clothing_style,
            req.eye_style is not None and req.eye_style != character.eye_style,
        ])

        character.update_appearance(
            palette=new_palette,
            hair_style=req.hair_style,
            eye_style=req.eye_style,
            clothing_style=req.clothing_style,
            proportions=new_proportions,
        )

        # Defaults update
        new_expr = CharacterExpression(req.default_expression) if req.default_expression else None
        new_pose = CharacterPose(req.default_pose) if req.default_pose else None
        character.update_defaults(default_expression=new_expr, default_pose=new_pose)

        # Regenerate Blender assets if appearance changed
        if appearance_changed and self.blender_gen:
            try:
                blend_path, thumb_path = self.blender_gen.generate_character_assets(
                    character, force_regenerate=True
                )
                character.set_asset_paths(blend_file_path=blend_path, thumbnail_path=thumb_path)
            except Exception:
                pass

        saved = self.char_repo.save(character)
        return character_to_dto(saved)
