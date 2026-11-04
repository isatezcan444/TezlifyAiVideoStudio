from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, List

from tezlify_studio.domain.enums.studio_status import AssetCategory, AssetFormat

@dataclass
class StudioAsset:
    id: str
    name: str
    category: AssetCategory
    description: str = ""
    file_path: str = ""
    asset_format: AssetFormat = AssetFormat.BLEND
    thumbnail_path: Optional[str] = None
    version: str = "1.0"
    tags: List[str] = field(default_factory=list)
    is_builtin: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def update_metadata(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> None:
        if name is not None:
            clean = name.strip()
            if not clean:
                raise ValueError("Varlık adı boş olamaz.")
            self.name = clean
        if description is not None:
            self.description = description
        if tags is not None:
            self.tags = tags
        self.updated_at = datetime.now(timezone.utc)

    def set_file_paths(self, file_path: Optional[str] = None, thumbnail_path: Optional[str] = None) -> None:
        if file_path is not None:
            self.file_path = file_path
        if thumbnail_path is not None:
            self.thumbnail_path = thumbnail_path
        self.updated_at = datetime.now(timezone.utc)
