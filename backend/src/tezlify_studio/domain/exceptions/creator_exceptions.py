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


class ChannelNotFoundException(CreatorStudioException):
    def __init__(self, channel_id: str | None = None):
        message = (
            f"Kanal bulunamadı: {channel_id}"
            if channel_id
            else "Yönetilecek bir kanal seçili değil. Önce bir hesap bağlayın."
        )
        super().__init__(message, "CHANNEL_NOT_FOUND")


class ChannelDisabledException(CreatorStudioException):
    def __init__(self, channel_id: str):
        super().__init__(
            f"Kanal '{channel_id}' bu çalışma alanında devre dışı bırakılmış.",
            "CHANNEL_DISABLED",
        )


class ConnectionInactiveException(CreatorStudioException):
    def __init__(self, connection_id: str, status: str):
        super().__init__(
            f"Hesap bağlantısı '{connection_id}' kullanılabilir değil (durum: {status}). "
            "Hesabı yeniden bağlayın.",
            "CONNECTION_INACTIVE",
        )


class ChannelBindingMismatchException(CreatorStudioException):
    def __init__(self, channel_id: str):
        super().__init__(
            "Bağlantının yetkisi hedef kanalla eşleşmiyor. Güvenlik nedeniyle işlem "
            f"durduruldu; hiçbir veri kanal '{channel_id}' dışına gönderilmedi.",
            "CHANNEL_BINDING_MISMATCH",
        )


class DuplicateOAuthCallbackException(CreatorStudioException):
    def __init__(self):
        super().__init__(
            "Bu OAuth yanıtı daha önce işlendi (state tek kullanımlıktır). "
            "Yeni bir bağlantı oturumu başlatın.",
            "OAUTH_CALLBACK_ALREADY_USED",
        )
