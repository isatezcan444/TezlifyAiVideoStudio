from typing import List

from tezlify_studio.application.dto.connection_dto import ConnectionDTO, connection_to_dto
from tezlify_studio.application.ports.platform_channel_repository_port import (
    PlatformChannelRepositoryPort,
)
from tezlify_studio.application.ports.platform_connection_repository_port import (
    PlatformConnectionRepositoryPort,
)


class ListPlatformConnectionsUseCase:
    """Lists every connected account, grouped by platform, with its channels."""

    def __init__(
        self,
        connection_repo: PlatformConnectionRepositoryPort,
        channel_repo: PlatformChannelRepositoryPort,
    ):
        self.connection_repo = connection_repo
        self.channel_repo = channel_repo

    def execute(self, include_disconnected: bool = False) -> List[ConnectionDTO]:
        connections = self.connection_repo.list_all(
            include_disconnected=include_disconnected
        )
        order = {"youtube": 0, "instagram": 1, "tiktok": 2}
        connections.sort(
            key=lambda item: (
                order.get(item.platform.value, 99),
                item.connected_at,
            )
        )
        return [
            connection_to_dto(
                connection, self.channel_repo.list_by_connection(connection.id)
            )
            for connection in connections
        ]
