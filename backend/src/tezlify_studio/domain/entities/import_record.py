from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from tezlify_studio.domain.enums.media_status import ImportSource

@dataclass
class ImportRecord:
    id: str
    media_asset_id: str
    source_type: ImportSource = ImportSource.MANUAL_UPLOAD
    status: str = "success"
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

