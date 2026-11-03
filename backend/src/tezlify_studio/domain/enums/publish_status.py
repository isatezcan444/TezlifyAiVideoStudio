from enum import Enum

class SocialPlatform(str, Enum):
    YOUTUBE = "youtube"
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"

class PrivacyStatus(str, Enum):
    PRIVATE = "private"
    UNLISTED = "unlisted"
    PUBLIC = "public"

class PublishStatus(str, Enum):
    PENDING = "pending"
    AUTHENTICATING = "authenticating"
    UPLOADING = "uploading"
    PAUSED = "paused"
    PROCESSING = "processing"
    PUBLISHED = "published"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REQUIRES_REAUTH = "requires_reauth"
