from tezlify_studio.domain.exceptions.media_exceptions import DomainException

class PublishDomainException(DomainException):
    """Base exception for video publishing operations"""
    pass

class SocialAccountNotFoundException(PublishDomainException):
    def __init__(self, platform: str):
        super().__init__(f"No active connected account found for platform '{platform}'.")
        self.platform = platform

class InvalidPublishStateTransitionException(PublishDomainException):
    def __init__(self, from_status: str, to_status: str):
        super().__init__(f"Invalid status transition from '{from_status}' to '{to_status}'.")
        self.from_status = from_status
        self.to_status = to_status

class DuplicatePublishException(PublishDomainException):
    def __init__(self, media_id: str, platform: str, existing_publish_id: str):
        super().__init__(
            f"An active publish job already exists for media '{media_id}' on platform '{platform}' (ID: {existing_publish_id})."
        )
        self.media_id = media_id
        self.platform = platform
        self.existing_publish_id = existing_publish_id

class QuotaExceededException(PublishDomainException):
    def __init__(self, message: str, reset_time_iso: str | None = None):
        super().__init__(message)
        self.reset_time_iso = reset_time_iso

class TokenStorageException(PublishDomainException):
    def __init__(self, reason: str):
        super().__init__(f"Token storage operation failed: {reason}")
        self.reason = reason

class AuthenticationRequiredException(PublishDomainException):
    def __init__(self, reason: str = "Re-authentication required."):
        super().__init__(reason)
