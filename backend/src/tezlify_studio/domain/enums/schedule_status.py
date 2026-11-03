from enum import Enum

class ScheduleStatus(str, Enum):
    """Lifecycle status of a scheduled video publish."""
    SCHEDULED = "scheduled"
    PROCESSING = "processing"
    PUBLISHED = "published"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    MISSED = "missed"
