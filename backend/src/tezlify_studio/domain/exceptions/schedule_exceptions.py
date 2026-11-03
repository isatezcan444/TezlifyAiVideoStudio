from tezlify_studio.domain.exceptions.media_exceptions import DomainException

class ScheduleDomainException(DomainException):
    """Base exception for scheduled publish domain errors."""
    pass

class InvalidScheduleStateTransitionException(ScheduleDomainException):
    def __init__(self, from_status: str, to_status: str):
        super().__init__(f"Invalid status transition from '{from_status}' to '{to_status}'.")
        self.from_status = from_status
        self.to_status = to_status

class InvalidScheduleTimeException(ScheduleDomainException):
    def __init__(self, reason: str):
        super().__init__(f"Invalid schedule time: {reason}")
        self.reason = reason

class DuplicateScheduleException(ScheduleDomainException):
    def __init__(self, media_id: str, platform: str, existing_schedule_id: str):
        super().__init__(
            f"An active scheduled publish already exists for media '{media_id}' on platform '{platform}' (Schedule ID: {existing_schedule_id})."
        )
        self.media_id = media_id
        self.platform = platform
        self.existing_schedule_id = existing_schedule_id

class ScheduledPublishNotFoundException(ScheduleDomainException):
    def __init__(self, schedule_id: str):
        super().__init__(f"Scheduled publish '{schedule_id}' not found.")
        self.schedule_id = schedule_id

class ScheduleAlreadyClaimedException(ScheduleDomainException):
    def __init__(self, schedule_id: str):
        super().__init__(f"Scheduled publish '{schedule_id}' is already claimed by another worker or in process.")
        self.schedule_id = schedule_id
