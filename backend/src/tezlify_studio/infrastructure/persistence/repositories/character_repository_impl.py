import json
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from tezlify_studio.application.ports.character_repository_port import CharacterRepositoryPort
from tezlify_studio.domain.entities.character import Character
from tezlify_studio.domain.enums.studio_status import (
    CharacterPose,
    CharacterExpression,
)
from tezlify_studio.domain.value_objects.character_models import (
    CharacterColorPalette,
    BodyProportions,
)
from tezlify_studio.infrastructure.persistence.models.studio_models import CharacterModel

class CharacterRepositoryImpl(CharacterRepositoryPort):
    def __init__(self, db: Session):
        self.db = db

    def _ensure_utc(self, dt: Optional[datetime]) -> Optional[datetime]:
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def _to_domain(self, model: CharacterModel) -> Character:
        try:
            palette = CharacterColorPalette.model_validate_json(model.palette_json)
        except Exception:
            palette = CharacterColorPalette()

        try:
            proportions = BodyProportions.model_validate_json(model.proportions_json)
        except Exception:
            proportions = BodyProportions()

        return Character(
            id=model.id,
            name=model.name,
            description=model.description or "",
            gender=model.gender,
            palette=palette,
            hair_style=model.hair_style,
            eye_style=model.eye_style,
            clothing_style=model.clothing_style,
            voice_id=model.voice_id or "",
            default_expression=CharacterExpression(model.default_expression),
            default_pose=CharacterPose(model.default_pose),
            proportions=proportions,
            blend_file_path=model.blend_file_path,
            thumbnail_path=model.thumbnail_path,
            is_builtin=bool(model.is_builtin),
            created_at=self._ensure_utc(model.created_at),
            updated_at=self._ensure_utc(model.updated_at),
        )

    def save(self, character: Character) -> Character:
        palette_json = character.palette.model_dump_json()
        proportions_json = character.proportions.model_dump_json()

        existing = self.db.query(CharacterModel).filter(CharacterModel.id == character.id).first()
        if existing:
            existing.name = character.name
            existing.description = character.description
            existing.gender = character.gender
            existing.palette_json = palette_json
            existing.hair_style = character.hair_style
            existing.eye_style = character.eye_style
            existing.clothing_style = character.clothing_style
            existing.voice_id = character.voice_id
            existing.default_expression = character.default_expression.value
            existing.default_pose = character.default_pose.value
            existing.proportions_json = proportions_json
            existing.blend_file_path = character.blend_file_path
            existing.thumbnail_path = character.thumbnail_path
            existing.is_builtin = character.is_builtin
            existing.updated_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(existing)
            return self._to_domain(existing)

        new_model = CharacterModel(
            id=character.id,
            name=character.name,
            description=character.description,
            gender=character.gender,
            palette_json=palette_json,
            hair_style=character.hair_style,
            eye_style=character.eye_style,
            clothing_style=character.clothing_style,
            voice_id=character.voice_id,
            default_expression=character.default_expression.value,
            default_pose=character.default_pose.value,
            proportions_json=proportions_json,
            blend_file_path=character.blend_file_path,
            thumbnail_path=character.thumbnail_path,
            is_builtin=character.is_builtin,
            created_at=character.created_at or datetime.now(timezone.utc),
            updated_at=character.updated_at or datetime.now(timezone.utc),
        )
        self.db.add(new_model)
        self.db.commit()
        self.db.refresh(new_model)
        return self._to_domain(new_model)

    def get_by_id(self, character_id: str) -> Optional[Character]:
        model = self.db.query(CharacterModel).filter(CharacterModel.id == character_id).first()
        return self._to_domain(model) if model else None

    def list_characters(
        self,
        limit: int = 50,
        offset: int = 0,
        gender: Optional[str] = None,
        is_builtin: Optional[bool] = None,
    ) -> List[Character]:
        query = self.db.query(CharacterModel)
        if gender is not None:
            query = query.filter(CharacterModel.gender == gender)
        if is_builtin is not None:
            query = query.filter(CharacterModel.is_builtin == is_builtin)
        models = (
            query.order_by(desc(CharacterModel.is_builtin), CharacterModel.name.asc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [self._to_domain(m) for m in models]

    def count(self, gender: Optional[str] = None, is_builtin: Optional[bool] = None) -> int:
        query = self.db.query(CharacterModel)
        if gender is not None:
            query = query.filter(CharacterModel.gender == gender)
        if is_builtin is not None:
            query = query.filter(CharacterModel.is_builtin == is_builtin)
        return query.count()

    def delete(self, character_id: str) -> bool:
        model = self.db.query(CharacterModel).filter(CharacterModel.id == character_id).first()
        if not model:
            return False
        self.db.delete(model)
        self.db.commit()
        return True
