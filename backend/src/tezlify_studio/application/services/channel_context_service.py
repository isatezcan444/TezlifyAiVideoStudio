from typing import Dict, List, Optional

from tezlify_studio.application.ports.channel_context_resolver_port import (
    ChannelContextResolverPort,
)
from tezlify_studio.application.ports.channel_selection_repository_port import (
    ChannelSelectionRepositoryPort,
)
from tezlify_studio.application.ports.platform_channel_repository_port import (
    PlatformChannelRepositoryPort,
)
from tezlify_studio.application.ports.platform_connection_repository_port import (
    PlatformConnectionRepositoryPort,
)
from tezlify_studio.domain.entities.channel_selection import ChannelSelection
from tezlify_studio.domain.entities.platform_channel import PlatformChannel
from tezlify_studio.domain.exceptions.creator_exceptions import (
    ChannelDisabledException,
    ChannelNotFoundException,
    ConnectionInactiveException,
)
from tezlify_studio.domain.value_objects.channel_context import ChannelContext


class ChannelContextService(ChannelContextResolverPort):
    """Resolves channel ids coming from the UI into validated contexts.

    The frontend never supplies a token or a connection id; it only selects a
    channel id that already exists in the local database.
    """

    def __init__(
        self,
        connection_repo: PlatformConnectionRepositoryPort,
        channel_repo: PlatformChannelRepositoryPort,
        selection_repo: ChannelSelectionRepositoryPort,
    ) -> None:
        self.connection_repo = connection_repo
        self.channel_repo = channel_repo
        self.selection_repo = selection_repo

    def resolve(self, channel_id: Optional[str] = None) -> ChannelContext:
        if channel_id:
            channel = self.channel_repo.get_by_id(channel_id)
            if not channel:
                raise ChannelNotFoundException(channel_id)
            return self._build_context(channel)

        selection = self.selection_repo.get()
        if selection.active_channel_id:
            channel = self.channel_repo.get_by_id(selection.active_channel_id)
            if channel and channel.is_enabled:
                connection = self.connection_repo.get_by_id(channel.platform_connection_id)
                if connection and connection.is_active:
                    return ChannelContext(channel=channel, connection=connection)

        channels = self.channel_repo.list_enabled()
        for channel in channels:
            connection = self.connection_repo.get_by_id(channel.platform_connection_id)
            if connection and connection.is_active:
                selection.select(channel.id)
                self.selection_repo.save(selection)
                return ChannelContext(channel=channel, connection=connection)

        raise ChannelNotFoundException()

    def list_contexts(
        self,
        platform: Optional[str] = None,
        include_disabled: bool = False,
        include_disconnected: bool = False,
    ) -> List[ChannelContext]:
        connections = self.connection_repo.list_all(include_disconnected=include_disconnected)
        by_id = {connection.id: connection for connection in connections}
        channels = (
            self.channel_repo.list_enabled(platform)
            if not include_disabled
            else self._list_all_channels(platform)
        )
        contexts: List[ChannelContext] = []
        for channel in channels:
            connection = by_id.get(channel.platform_connection_id)
            if not connection:
                continue
            if not include_disconnected and not connection.is_active:
                continue
            contexts.append(ChannelContext(channel=channel, connection=connection))
        contexts.sort(key=self._sort_key)
        return contexts

    def list_by_connection(self, connection_id: str) -> List[ChannelContext]:
        connection = self.connection_repo.get_by_id(connection_id)
        if not connection:
            return []
        channels = self.channel_repo.list_by_connection(connection_id)
        return [ChannelContext(channel=channel, connection=connection) for channel in channels]

    def get_selection(self) -> ChannelSelection:
        return self.selection_repo.get()

    def select(self, channel_id: str) -> ChannelContext:
        channel = self.channel_repo.get_by_id(channel_id)
        if not channel:
            raise ChannelNotFoundException(channel_id)
        context = self._build_context(channel)
        selection = self.selection_repo.get()
        selection.select(channel.id)
        selection.default_platform = channel.platform.value
        self.selection_repo.save(selection)
        return context

    def clear_selection(self) -> None:
        selection = self.selection_repo.get()
        selection.active_channel_id = None
        self.selection_repo.save(selection)

    def _build_context(self, channel: PlatformChannel) -> ChannelContext:
        if not channel.is_enabled:
            raise ChannelDisabledException(channel.id)
        connection = self.connection_repo.get_by_id(channel.platform_connection_id)
        if not connection:
            raise ChannelNotFoundException(channel.id)
        if not connection.is_active:
            raise ConnectionInactiveException(connection.id, connection.connection_status.value)
        return ChannelContext(channel=channel, connection=connection)

    def _list_all_channels(self, platform: Optional[str]) -> List[PlatformChannel]:
        channels: List[PlatformChannel] = []
        for connection in self.connection_repo.list_all(include_disconnected=True):
            if platform and connection.platform.value != platform:
                continue
            channels.extend(self.channel_repo.list_by_connection(connection.id))
        return channels

    @staticmethod
    def _sort_key(context: ChannelContext) -> tuple:
        return (
            context.channel.platform.value,
            context.connection.account_display_name.lower(),
            not context.channel.is_primary,
            context.channel.channel_name.lower(),
        )
