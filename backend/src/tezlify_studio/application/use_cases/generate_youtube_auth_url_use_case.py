from typing import Optional
from tezlify_studio.application.ports.youtube_publisher_port import YouTubePublisherPort
from tezlify_studio.application.dto.publish_dto import YouTubeAuthUrlResponseDTO
from tezlify_studio.application.use_cases.oauth_session_store import oauth_session_store

class GenerateYouTubeAuthUrlUseCase:
    def __init__(self, publisher: YouTubePublisherPort):
        self.publisher = publisher

    def execute(
        self,
        redirect_uri: Optional[str] = None,
        loopback_port: Optional[int] = None,
    ) -> YouTubeAuthUrlResponseDTO:
        state, code_challenge = oauth_session_store.create_session(redirect_uri=redirect_uri)
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
