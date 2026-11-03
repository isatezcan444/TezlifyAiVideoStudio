from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, List
from tezlify_studio.domain.enums.publish_status import SocialPlatform, PrivacyStatus, PublishStatus
from tezlify_studio.domain.exceptions.publish_exceptions import InvalidPublishStateTransitionException

ALLOWED_TRANSITIONS = {
    PublishStatus.PENDING: {
        PublishStatus.AUTHENTICATING,
        PublishStatus.UPLOADING,
        PublishStatus.REQUIRES_REAUTH,
        PublishStatus.CANCELLED,
        PublishStatus.FAILED,
    },
    PublishStatus.AUTHENTICATING: {
        PublishStatus.UPLOADING,
        PublishStatus.REQUIRES_REAUTH,
        PublishStatus.FAILED,
        PublishStatus.CANCELLED,
    },
    PublishStatus.UPLOADING: {
        PublishStatus.PAUSED,
        PublishStatus.PROCESSING,
        PublishStatus.PUBLISHED,
        PublishStatus.FAILED,
        PublishStatus.CANCELLED,
        PublishStatus.REQUIRES_REAUTH,
    },
    PublishStatus.PAUSED: {
        PublishStatus.UPLOADING,
        PublishStatus.PUBLISHED,
        PublishStatus.CANCELLED,
        PublishStatus.FAILED,
    },
    PublishStatus.PROCESSING: {
        PublishStatus.PUBLISHED,
        PublishStatus.FAILED,
    },
    PublishStatus.REQUIRES_REAUTH: {
        PublishStatus.AUTHENTICATING,
        PublishStatus.PENDING,
        PublishStatus.CANCELLED,
    },
    PublishStatus.FAILED: {
        PublishStatus.PENDING,
        PublishStatus.UPLOADING,
    },
    PublishStatus.CANCELLED: {
        PublishStatus.PENDING,
    },
    PublishStatus.PUBLISHED: set(),  # Terminal state
}

@dataclass
class PublishRecord:
    id: str
    media_asset_id: str
    platform: SocialPlatform = SocialPlatform.YOUTUBE
    external_video_id: Optional[str] = None
    external_video_url: Optional[str] = None
    title: str = ""
    description: str = ""
    tags: List[str] = field(default_factory=list)
    category_id: str = "22"  # Default: People & Blogs
    privacy_status: PrivacyStatus = PrivacyStatus.PRIVATE
    status: PublishStatus = PublishStatus.PENDING
    progress_percentage: int = 0
    uploaded_bytes: int = 0
    total_bytes: int = 0
    upload_session_uri: Optional[str] = None
    thumbnail_path: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    published_at: Optional[datetime] = None

    def transition_to(self, new_status: PublishStatus, error_code: Optional[str] = None, error_message: Optional[str] = None) -> None:
        if new_status == self.status:
            return

        allowed = ALLOWED_TRANSITIONS.get(self.status, set())
        if new_status not in allowed:
            raise InvalidPublishStateTransitionException(self.status.value, new_status.value)

        self.status = new_status
        self.updated_at = datetime.now(timezone.utc)

        if error_code or error_message:
            self.error_code = error_code
            self.error_message = error_message

        if new_status == PublishStatus.PUBLISHED:
            self.published_at = datetime.now(timezone.utc)
            self.progress_percentage = 100

    def update_progress(self, uploaded_bytes: int, total_bytes: int) -> None:
        self.uploaded_bytes = uploaded_bytes
        self.total_bytes = total_bytes
        if total_bytes > 0:
            self.progress_percentage = min(99, int((uploaded_bytes / total_bytes) * 100))
        self.updated_at = datetime.now(timezone.utc)
