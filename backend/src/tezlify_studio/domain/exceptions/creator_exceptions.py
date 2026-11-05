from tezlify_studio.domain.exceptions.publish_exceptions import PublishDomainException


class CreatorStudioException(PublishDomainException):
    """Base class for creator-management failures."""

    def __init__(self, message: str, error_code: str = "CREATOR_STUDIO_ERROR"):
        super().__init__(message)
        self.error_code = error_code


class PlatformNotSupportedException(CreatorStudioException):
    def __init__(self, platform_id: str):
        super().__init__(
            f"Platform '{platform_id}' bu sürümde desteklenmiyor. Yalnızca YouTube aktiftir.",
            "PLATFORM_NOT_SUPPORTED",
        )
        self.platform_id = platform_id


class InsufficientScopeException(CreatorStudioException):
    def __init__(self, required_scope: str, action: str):
        super().__init__(
            f"'{action}' için '{required_scope}' izni gerekiyor. Bağlantıyı genişletmek için "
            "Ayarlar > Bağlı Hesaplar bölümünden YouTube hesabını yeniden yetkilendirin.",
            "INSUFFICIENT_SCOPE",
        )
        self.required_scope = required_scope
        self.action = action


class AnalyticsUnavailableException(CreatorStudioException):
    def __init__(self, reason: str, detail: str = ""):
        message = f"YouTube Analytics verisi kullanılamıyor ({reason})."
        if detail:
            message = f"{message} {detail}"
        super().__init__(message, "ANALYTICS_UNAVAILABLE")
        self.reason = reason


class CreatorApiException(CreatorStudioException):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message, "CREATOR_API_ERROR")
        self.status_code = status_code
