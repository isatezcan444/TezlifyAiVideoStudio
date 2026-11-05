from typing import Optional

from tezlify_studio.application.dto.connection_dto import (
    ChannelSelectionDTO,
    iso_or_empty,
)
from tezlify_studio.application.ports.channel_context_resolver_port import (
    ChannelContextResolverPort,
)
from tezlify_studio.application.ports.platform_channel_repository_port import (
    PlatformChannelRepositoryPort,
)
from tezlify_studio.domain.exceptions.creator_exceptions import ChannelNotFoundException


class ChannelSelectionUseCase:
    """Reads or changes the globally active channel."""

    def __init__(
        self,
        resolver: ChannelContextResolverPort,
        channel_repo: PlatformChannelRepositoryPort,
    ):
        self.resolver = resolver
        self.channel_repo = channel_repo

    def get(self) -> ChannelSelectionDTO:
        selection = self.resolver.get_selection()
        return ChannelSelectionDTO(
            active_channel_id=selection.active_channel_id or "",
            default_platform=selection.default_platform,
            updated_at=iso_or_empty(selection.updated_at),
        )

    def select(self, channel_id: str) -> ChannelSelectionDTO:
        self.resolver.select(channel_id)
        selection = self.resolver.get_selection()
        return ChannelSelectionDTO(
            active_channel_id=selection.active_channel_id or "",
            default_platform=selection.default_platform,
            updated_at=iso_or_empty(selection.updated_at),
        )

    def set_enabled(self, channel_id: str, enabled: bool) -> bool:
        channel = self.channel_repo.get_by_id(channel_id)
        if not channel:
            raise ChannelNotFoundException(channel_id)
        updated = self.channel_repo.set_enabled(channel_id, enabled)
        if not enabled:
            selection = self.resolver.get_selection()
            if selection.active_channel_id == channel_id:
                self.resolver.clear_selection()
        return bool(updated)
