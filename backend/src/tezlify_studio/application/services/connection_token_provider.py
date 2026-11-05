from datetime import datetime, timedelta, timezone

from tezlify_studio.application.ports.channel_access_provider_port import (
    ChannelAccessProviderPort,
)
from tezlify_studio.application.ports.platform_connection_repository_port import (
    PlatformConnectionRepositoryPort,
)
from tezlify_studio.application.ports.token_storage_port import TokenStoragePort
from tezlify_studio.application.ports.youtube_publisher_port import YouTubePublisherPort
from tezlify_studio.domain.exceptions.creator_exceptions import ConnectionInactiveException
from tezlify_studio.domain.exceptions.publish_exceptions import AuthenticationRequiredException
from tezlify_studio.domain.value_objects.channel_access import ChannelAccess
from tezlify_studio.domain.value_objects.channel_context import ChannelContext


class ConnectionTokenProvider(ChannelAccessProviderPort):
    """Resolves and refreshes the token of exactly one connection.

    Keychain reads/writes use ``connection.token_reference``; disconnected or
    failed connections raise instead of silently borrowing another grant.
    """

    def __init__(
        self,
        connection_repo: PlatformConnectionRepositoryPort,
        token_storage: TokenStoragePort,
        publisher: YouTubePublisherPort,
    ) -> None:
        self.connection_repo = connection_repo
        self.token_storage = token_storage
        self.publisher = publisher

    def get_access(self, context: ChannelContext) -> ChannelAccess:
        connection = self.connection_repo.get_by_id(context.connection_id) or context.connection
        if not connection.is_active:
            raise ConnectionInactiveException(
                connection.id, connection.connection_status.value
            )

        token_ref = connection.token_reference or connection.id
        access_token = self.token_storage.get_access_token(token_ref)
        if access_token and not connection.is_token_expired():
            return self._bundle(context, connection.id, access_token)

        refresh_token = self.token_storage.get_refresh_token(token_ref)
        if not refresh_token:
            connection.require_reauth()
            self.connection_repo.save(connection)
            raise AuthenticationRequiredException(
                "Bu hesap için yenileme anahtarı bulunamadı. Lütfen hesabı yeniden bağlayın."
            )

        try:
            refreshed = self.publisher.refresh_access_token(refresh_token)
        except AuthenticationRequiredException:
            connection.require_reauth()
            self.connection_repo.save(connection)
            raise

        new_access = refreshed.get("access_token")
        if not new_access:
            raise AuthenticationRequiredException("Hesabın erişim anahtarı yenilenemedi.")

        expires_in = int(refreshed.get("expires_in", 3600))
        connection.mark_refreshed(
            datetime.now(timezone.utc) + timedelta(seconds=max(expires_in - 120, 60))
        )
        self.connection_repo.save(connection)
        self.token_storage.store_tokens(token_ref, new_access, refresh_token)
        return self._bundle(context, connection.id, new_access)

    @staticmethod
    def _bundle(context: ChannelContext, connection_id: str, token: str) -> ChannelAccess:
        return ChannelAccess(
            platform=context.channel.platform,
            channel_id=context.channel.id,
            external_channel_id=context.channel.channel_external_id,
            connection_id=connection_id,
            access_token=token,
        )
