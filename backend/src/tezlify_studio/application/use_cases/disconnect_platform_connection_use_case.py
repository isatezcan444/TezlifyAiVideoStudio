from typing import Optional

from tezlify_studio.application.ports.channel_selection_repository_port import (
    ChannelSelectionRepositoryPort,
)
from tezlify_studio.application.ports.platform_channel_repository_port import (
    PlatformChannelRepositoryPort,
)
from tezlify_studio.application.ports.platform_connection_repository_port import (
    PlatformConnectionRepositoryPort,
)
from tezlify_studio.application.ports.publish_record_repository_port import (
    PublishRecordRepositoryPort,
)
from tezlify_studio.application.ports.scheduled_publish_repository_port import (
    ScheduledPublishRepositoryPort,
)
from tezlify_studio.application.ports.token_storage_port import TokenStoragePort
from tezlify_studio.domain.enums.publish_status import SocialPlatform


class DisconnectPlatformConnectionUseCase:
    """Revokes exactly one connection and quarantines only its own work."""

    def __init__(
        self,
        connection_repo: PlatformConnectionRepositoryPort,
        channel_repo: PlatformChannelRepositoryPort,
        selection_repo: ChannelSelectionRepositoryPort,
        publish_repo: PublishRecordRepositoryPort,
        schedule_repo: ScheduledPublishRepositoryPort,
        token_storage: TokenStoragePort,
    ):
        self.connection_repo = connection_repo
        self.channel_repo = channel_repo
        self.selection_repo = selection_repo
        self.publish_repo = publish_repo
        self.schedule_repo = schedule_repo
        self.token_storage = token_storage

    def execute(self, connection_id: Optional[str] = None) -> bool:
        if connection_id:
            connection = self.connection_repo.get_by_id(connection_id)
            targets = [connection] if connection and connection.is_active else []
        else:
            targets = self.connection_repo.list_by_platform(
                SocialPlatform.YOUTUBE.value
            )

        if not targets:
            return False

        for connection in targets:
            token_ref = connection.token_reference or connection.id
            try:
                self.token_storage.delete_tokens(token_ref)
            except Exception:  # noqa: BLE001 - DB state must change even if Keychain is locked
                pass

            connection.disconnect()
            self.connection_repo.save(connection)

            for channel in self.channel_repo.list_by_connection(connection.id):
                if channel.is_enabled:
                    self.channel_repo.set_enabled(channel.id, False)

            self.publish_repo.fail_pending_for_connection(
                connection.id,
                "CONNECTION_DISCONNECTED",
                "Hesap bağlantısı kaldırıldı; bekleyen yükleme güvenli şekilde durduruldu.",
            )
            self.schedule_repo.fail_pending_for_connection(
                connection.id,
                "CONNECTION_DISCONNECTED",
                "Hesap bağlantısı kaldırıldı; planlanan yayın iptal edildi.",
            )

        self._repair_selection()
        return True

    def _repair_selection(self) -> None:
        selection = self.selection_repo.get()
        if not selection.active_channel_id:
            return
        channel = self.channel_repo.get_by_id(selection.active_channel_id)
        if channel and channel.is_enabled:
            connection = self.connection_repo.get_by_id(channel.platform_connection_id)
            if connection and connection.is_active:
                return
        replacement = None
        for candidate in self.channel_repo.list_enabled():
            connection = self.connection_repo.get_by_id(candidate.platform_connection_id)
            if connection and connection.is_active:
                replacement = candidate
                break
        if replacement:
            selection.select(replacement.id)
        else:
            selection.active_channel_id = None
        self.selection_repo.save(selection)
