from abc import ABC, abstractmethod
from typing import Optional, List, Tuple, Dict, Any

class YouTubePublisherPort(ABC):
    @abstractmethod
    def generate_auth_url(self, state: str, code_challenge: str) -> str:
        """Constructs Google OAuth 2.0 PKCE desktop authorization URL."""
        pass

    @abstractmethod
    def exchange_code_for_tokens(self, code: str, code_verifier: str) -> Dict[str, Any]:
        """Exchanges auth code with PKCE verifier for access and refresh tokens."""
        pass

    @abstractmethod
    def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """Obtains new access token using stored refresh token."""
        pass

    @abstractmethod
    def get_channel_profile(self, access_token: str) -> Dict[str, Any]:
        """Fetches YouTube channel title, ID, and thumbnail avatar."""
        pass

    @abstractmethod
    def initiate_resumable_upload(
        self,
        access_token: str,
        title: str,
        description: str,
        tags: List[str],
        category_id: str,
        privacy: str,
        total_bytes: int,
    ) -> str:
        """Initiates resumable upload session and returns Google upload URI."""
        pass

    @abstractmethod
    def upload_chunk(
        self,
        upload_session_uri: str,
        chunk_data: bytes,
        start_byte: int,
        total_bytes: int,
    ) -> Tuple[int, Optional[Dict[str, Any]]]:
        """
        Uploads a single chunk (multiple of 256KB) to the resumable session URI.
        Returns: (http_status_code, response_json_dict_if_completed)
        Status 308 indicates chunk accepted, resume incomplete.
        Status 200/201 indicates video finalized.
        """
        pass

    @abstractmethod
    def query_upload_status(self, upload_session_uri: str, total_bytes: int) -> int:
        """Queries Google for the last byte received to resume an interrupted upload."""
        pass

    @abstractmethod
    def upload_custom_thumbnail(
        self,
        access_token: str,
        video_id: str,
        thumbnail_path: str,
    ) -> bool:
        """Uploads custom thumbnail for the specified YouTube video."""
        pass
