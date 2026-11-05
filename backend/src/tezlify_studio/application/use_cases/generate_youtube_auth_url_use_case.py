from typing import Optional

from tezlify_studio.application.dto.publish_dto import YouTubeAuthUrlResponseDTO
from tezlify_studio.application.ports.platform_connection_repository_port import (
    PlatformConnectionRepositoryPort,
)
from tezlify_studio.application.ports.youtube_publisher_port import YouTubePublisherPort
from tezlify_studio.application.use_cases.oauth_session_store import (
    INTENT_ADD_ACCOUNT,
    INTENT_RECONNECT,
    oauth_session_store,
)
from tezlify_studio.domain.exceptions.creator_exceptions import ChannelNotFoundException


class GenerateYouTubeAuthUrlUseCase:
    def __init__(
        self,
        publisher: YouTubePublisherPort,
        connection_repo: Optional[PlatformConnectionRepositoryPort] = None,
    ):
        self.publisher = publisher
        self.connection_repo = connection_repo

    def execute(
        self,
        redirect_uri: Optional[str] = None,
        loopback_port: Optional[int] = None,
        intent: str = INTENT_ADD_ACCOUNT,
        connection_id: Optional[str] = None,
    ) -> YouTubeAuthUrlResponseDTO:
        if intent == INTENT_RECONNECT:
            if not connection_id:
                raise ValueError("Yeniden bağlanmak için connection_id zorunludur.")
            if self.connection_repo and not self.connection_repo.get_by_id(connection_id):
                raise ChannelNotFoundException(connection_id)

        state, code_challenge = oauth_session_store.create_session(
            redirect_uri=redirect_uri,
            intent=intent,
            connection_id=connection_id,
        )
        auth_url = self.publisher.generate_auth_url(
            state=state,
            code_challenge=code_challenge,
            redirect_uri=redirect_uri,
        )

        return YouTubeAuthUrlResponseDTO(
            auth_url=auth_url,
            state=state,
            loopback_port=loopback_port or 0,
        )
