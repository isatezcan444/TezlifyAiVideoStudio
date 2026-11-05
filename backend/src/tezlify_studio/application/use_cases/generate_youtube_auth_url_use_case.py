from typing import Iterable, List, Optional

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
from tezlify_studio.domain.value_objects.youtube_capabilities import (
    BASE_CAPABILITIES,
    capabilities_for_scopes,
    normalize_capabilities,
    scopes_for_capabilities,
)


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
        capabilities: Optional[Iterable[str]] = None,
    ) -> YouTubeAuthUrlResponseDTO:
        requested = normalize_capabilities(capabilities)
        existing_capabilities: List[str] = []

        if intent == INTENT_RECONNECT:
            if not connection_id:
                raise ValueError("Yeniden bağlanmak için connection_id zorunludur.")
            connection = (
                self.connection_repo.get_by_id(connection_id)
                if self.connection_repo
                else None
            )
            if self.connection_repo and not connection:
                raise ChannelNotFoundException(connection_id)
            if connection is not None:
                # Never request fewer permissions than the connection already
                # has: an extra grant must not narrow a working connection.
                existing_capabilities = capabilities_for_scopes(
                    connection.granted_scopes
                )

        if intent == INTENT_RECONNECT:
            final_capabilities: List[str] = []
            for capability in [*existing_capabilities, *requested]:
                if capability not in final_capabilities:
                    final_capabilities.append(capability)
        else:
            final_capabilities = list(requested)

        scopes = scopes_for_capabilities(final_capabilities, include_base=True)
        session_capabilities = list(BASE_CAPABILITIES) + [
            capability
            for capability in final_capabilities
            if capability not in BASE_CAPABILITIES
        ]

        state, code_challenge = oauth_session_store.create_session(
            redirect_uri=redirect_uri,
            intent=intent,
            connection_id=connection_id,
            capabilities=session_capabilities,
            requested_scopes=scopes,
        )
        auth_url = self.publisher.generate_auth_url(
            state=state,
            code_challenge=code_challenge,
            redirect_uri=redirect_uri,
            scopes=scopes,
        )

        return YouTubeAuthUrlResponseDTO(
            auth_url=auth_url,
            state=state,
            loopback_port=loopback_port or 0,
            capabilities=session_capabilities,
            requested_scopes=scopes,
        )
