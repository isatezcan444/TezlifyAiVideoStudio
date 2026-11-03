from tezlify_studio.application.ports.youtube_publisher_port import YouTubePublisherPort
from tezlify_studio.application.dto.publish_dto import YouTubeAuthUrlResponseDTO
from tezlify_studio.application.use_cases.oauth_session_store import oauth_session_store

class GenerateYouTubeAuthUrlUseCase:
    def __init__(self, publisher: YouTubePublisherPort):
        self.publisher = publisher

    def execute(self) -> YouTubeAuthUrlResponseDTO:
        state, code_challenge = oauth_session_store.create_session()
        auth_url = self.publisher.generate_auth_url(state=state, code_challenge=code_challenge)

        return YouTubeAuthUrlResponseDTO(
            auth_url=auth_url,
            state=state,
            loopback_port=8000,
        )
