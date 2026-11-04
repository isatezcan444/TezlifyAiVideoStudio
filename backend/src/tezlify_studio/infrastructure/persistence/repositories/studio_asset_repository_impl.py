import json
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from tezlify_studio.application.ports.studio_asset_repository_port import StudioAssetRepositoryPort
from tezlify_studio.domain.entities.studio_asset import StudioAsset
from tezlify_studio.domain.enums.studio_status import AssetCategory, AssetFormat
from tezlify_studio.infrastructure.persistence.models.studio_models import StudioAssetModel

class StudioAssetRepositoryImpl(StudioAssetRepositoryPort):
    def __init__(self, db: Session):
        self.db = db

    def _ensure_utc(self, dt: Optional[datetime]) -> Optional[datetime]:
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def _to_domain(self, model: StudioAssetModel) -> StudioAsset:
        try:
            tags = json.loads(model.tags_json) if model.tags_json else []
        except Exception:
            tags = []

        return StudioAsset(
            id=model.id,
            name=model.name,
            category=AssetCategory(model.category),
            description=model.description or "",
            file_path=model.file_path,
            asset_format=AssetFormat(model.asset_format),
            thumbnail_path=model.thumbnail_path,
            version=model.version or "1.0",
            tags=tags,
            is_builtin=bool(model.is_builtin),
            created_at=self._ensure_utc(model.created_at),
            updated_at=self._ensure_utc(model.updated_at),
        )

    def save(self, asset: StudioAsset) -> StudioAsset:
        tags_json = json.dumps(asset.tags, ensure_ascii=False)

        existing = self.db.query(StudioAssetModel).filter(StudioAssetModel.id == asset.id).first()
        if existing:
            existing.name = asset.name
            existing.category = asset.category.value
            existing.description = asset.description
            existing.file_path = asset.file_path
            existing.asset_format = asset.asset_format.value
            existing.thumbnail_path = asset.thumbnail_path
            existing.version = asset.version
            existing.tags_json = tags_json
            existing.is_builtin = asset.is_builtin
            existing.updated_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(existing)
            return self._to_domain(existing)

        new_model = StudioAssetModel(
            id=asset.id,
            name=asset.name,
            category=asset.category.value,
            description=asset.description,
            file_path=asset.file_path,
            asset_format=asset.asset_format.value,
            thumbnail_path=asset.thumbnail_path,
            version=asset.version,
            tags_json=tags_json,
            is_builtin=asset.is_builtin,
            created_at=asset.created_at or datetime.now(timezone.utc),
            updated_at=asset.updated_at or datetime.now(timezone.utc),
        )
        self.db.add(new_model)
        self.db.commit()
        self.db.refresh(new_model)
        return self._to_domain(new_model)

    def get_by_id(self, asset_id: str) -> Optional[StudioAsset]:
        model = self.db.query(StudioAssetModel).filter(StudioAssetModel.id == asset_id).first()
        return self._to_domain(model) if model else None

    def list_assets(
        self,
        category: Optional[AssetCategory] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[StudioAsset]:
        query = self.db.query(StudioAssetModel)
        if category is not None:
            query = query.filter(StudioAssetModel.category == category.value)
        models = (
            query.order_by(desc(StudioAssetModel.is_builtin), StudioAssetModel.name.asc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [self._to_domain(m) for m in models]

    def count(self, category: Optional[AssetCategory] = None) -> int:
        query = self.db.query(StudioAssetModel)
        if category is not None:
            query = query.filter(StudioAssetModel.category == category.value)
        return query.count()

    def delete(self, asset_id: str) -> bool:
        model = self.db.query(StudioAssetModel).filter(StudioAssetModel.id == asset_id).first()
        if not model:
            return False
        self.db.delete(model)
        self.db.commit()
        return True
