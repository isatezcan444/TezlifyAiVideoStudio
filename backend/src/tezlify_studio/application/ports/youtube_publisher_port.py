from abc import ABC, abstractmethod
from typing import Optional, List, Tuple, Dict, Any

class UploadStatusResult(int):
    """
    Subclasses int so callers expecting an int byte count continue to work,
    while optionally carrying finalized YouTube response data when upload completed (200/201).
    """
    def __new__(cls, confirmed_bytes: int, finalized_data: Optional[Dict[str, Any]] = None):
        instance = super().__new__(cls, confirmed_bytes)
        instance.finalized_data = finalized_data
        return instance

class YouTubePublisherPort(ABC):
    @abstractmethod
    def generate_auth_url(
        self,
        state: str,
        code_challenge: str,
        redirect_uri: Optional[str] = None,
        scopes: Optional[List[str]] = None,
    ) -> str:
        """Constructs Google OAuth 2.0 PKCE desktop authorization URL.

        ``scopes`` defaults to the minimal base grant; callers request extra
        capabilities incrementally.
        """
        pass

    @abstractmethod
    def exchange_code_for_tokens(
        self,
        code: str,
        code_verifier: str,
        redirect_uri: Optional[str] = None,
    ) -> Dict[str, Any]:
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

    def list_channel_profiles(self, access_token: str) -> List[Dict[str, Any]]:
        """Discovers every channel the token can manage.

        The default keeps older fakes working with a single profile; the real
        adapter overrides it with channels.list?mine=true.
        """
        return [self.get_channel_profile(access_token)]

    def get_account_identity(self, access_token: str) -> Dict[str, Any]:
        """Returns Google account identity when the grant allows it."""
        return {}

    def list_authorized_channel_ids(self, access_token: str) -> Optional[List[str]]:
        """Returns channel ids the token is authorized for.

        None means the adapter cannot verify the binding; callers must treat
        that as "unverified", never as a match.
        """
        return None

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

    def get_video_details(self, access_token: str, video_id: str) -> Dict[str, Any]:
        """Queries video details (snippet, status) from YouTube Data API."""
        return {}
