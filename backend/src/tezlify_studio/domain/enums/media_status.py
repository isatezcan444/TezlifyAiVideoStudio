from enum import Enum

class MediaStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"

class ImportSource(str, Enum):
    MANUAL_UPLOAD = "manual_upload"
    AI_GENERATED = "ai_generated"
    BLENDER_RENDER = "blender_render"

