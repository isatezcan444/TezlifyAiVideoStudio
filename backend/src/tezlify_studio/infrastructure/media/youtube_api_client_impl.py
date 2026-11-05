import os
import re
import time
import urllib.parse
from typing import Optional, List, Tuple, Dict, Any
import httpx
from tezlify_studio.application.ports.youtube_publisher_port import (
    YouTubePublisherPort,
    UploadStatusResult,
)
from tezlify_studio.domain.exceptions.publish_exceptions import (
    AuthenticationRequiredException,
    QuotaExceededException,
    PublishDomainException,
    UploadSessionExpiredException,
)
from tezlify_studio.infrastructure.configuration.settings import settings

class YouTubeApiClientImpl(YouTubePublisherPort):
    """
    YouTube Data API v3 client implementing OAuth 2.0 PKCE and Resumable Upload protocol.
    """
    AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
    API_BASE = "https://www.googleapis.com/youtube/v3"
    UPLOAD_BASE = "https://www.googleapis.com/upload/youtube/v3"
    # Creator Studio needs channel management, analytics and comments on top of
    # upload. Existing grants keep working for upload/read; the new scopes are
    # only requested when the user chooses to reconnect.
    from tezlify_studio.infrastructure.youtube.youtube_creator_api import YOUTUBE_SCOPES

    SCOPES = YOUTUBE_SCOPES

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        redirect_uri: Optional[str] = None,
        client: Optional[httpx.Client] = None,
    ) -> None:
        self.client_id = client_id if client_id is not None else settings.resolved_youtube_client_id
        self.client_secret = client_secret if client_secret is not None else settings.resolved_youtube_client_secret
        self.redirect_uri = redirect_uri or settings.youtube_redirect_uri
        self._client = client or httpx.Client(timeout=30.0)

    def _ensure_credentials(self) -> None:
        if not self.client_id:
            raise AuthenticationRequiredException(
                "Google Client ID is not configured. Please set GOOGLE_CLIENT_ID or YOUTUBE_CLIENT_ID in .env."
            )

    def generate_auth_url(
        self,
        state: str,
        code_challenge: str,
        redirect_uri: Optional[str] = None,
    ) -> str:
        self._ensure_credentials()
        effective_redirect = redirect_uri or self.redirect_uri
        params = {
            "client_id": self.client_id,
            "redirect_uri": effective_redirect,
            "response_type": "code",
            "scope": " ".join(self.SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        return f"{self.AUTH_ENDPOINT}?{urllib.parse.urlencode(params)}"

    def exchange_code_for_tokens(
        self,
        code: str,
        code_verifier: str,
        redirect_uri: Optional[str] = None,
    ) -> Dict[str, Any]:
        self._ensure_credentials()
        effective_redirect = redirect_uri or self.redirect_uri
        data = {
            "client_id": self.client_id,
            "code": code,
            "code_verifier": code_verifier,
            "grant_type": "authorization_code",
            "redirect_uri": effective_redirect,
        }
        if self.client_secret:
            data["client_secret"] = self.client_secret

        try:
            resp = self._client.post(self.TOKEN_ENDPOINT, data=data)
        except Exception as e:
            raise PublishDomainException(f"Network error exchanging OAuth code: {str(e)}")

        if resp.status_code != 200:
            err_data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            err_desc = err_data.get("error_description", resp.text)
            raise AuthenticationRequiredException(f"Failed to exchange authorization code: {err_desc}")

        return resp.json()

    def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        self._ensure_credentials()
        data = {
            "client_id": self.client_id,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
        if self.client_secret:
            data["client_secret"] = self.client_secret

        try:
            resp = self._client.post(self.TOKEN_ENDPOINT, data=data)
        except Exception as e:
            raise PublishDomainException(f"Network error refreshing access token: {str(e)}")

        if resp.status_code != 200:
            err_data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            err_code = err_data.get("error", "")
            err_desc = err_data.get("error_description", resp.text)
            if err_code == "invalid_grant":
                raise AuthenticationRequiredException(
                    "Google yetkilendirme anahtarının (refresh token) süresi dolmuş veya yetki geri çekilmiş. Lütfen YouTube kanalınızı yeniden bağlayın."
                )
            raise AuthenticationRequiredException(f"Failed to refresh access token ({err_code}): {err_desc}")

        return resp.json()

    def get_channel_profile(self, access_token: str) -> Dict[str, Any]:
        profiles = self.list_channel_profiles(access_token)
        if not profiles:
            raise PublishDomainException("Bu Google hesabına bağlı bir YouTube kanalı bulunamadı. Lütfen önce YouTube Studio üzerinde bir kanal oluşturun.")
        first = profiles[0]
        return {
            "channel_id": first.get("channel_id"),
            "channel_title": first.get("channel_title", "My YouTube Channel"),
            "avatar_url": first.get("avatar_url"),
        }

    def list_channel_profiles(self, access_token: str) -> List[Dict[str, Any]]:
        url = f"{self.API_BASE}/channels?part=snippet,statistics,contentDetails&mine=true"
        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            resp = self._client.get(url, headers=headers)
        except Exception as e:
            raise PublishDomainException(f"Network error getting YouTube profile: {str(e)}")

        if resp.status_code == 401:
            raise AuthenticationRequiredException("Access token expired while fetching YouTube channel.")
        if resp.status_code == 403:
            self._check_quota_and_forbidden_error(resp, "fetching YouTube channel")
        if resp.status_code != 200:
            raise PublishDomainException(f"Failed to fetch channel profile: {resp.text}")

        profiles: List[Dict[str, Any]] = []
        for channel in resp.json().get("items", []):
            snippet = channel.get("snippet", {})
            stats = channel.get("statistics", {})
            thumbs = snippet.get("thumbnails", {})
            avatar = (
                (thumbs.get("medium") or {}).get("url")
                or (thumbs.get("default") or {}).get("url")
            )
            hidden = bool(stats.get("hiddenSubscriberCount", False))
            profiles.append(
                {
                    "channel_id": channel.get("id"),
                    "channel_title": snippet.get("title", "My YouTube Channel"),
                    "avatar_url": avatar,
                    "description": snippet.get("description", ""),
                    "custom_url": snippet.get("customUrl"),
                    "subscriber_count": (
                        None if hidden or stats.get("subscriberCount") in (None, "")
                        else int(stats.get("subscriberCount"))
                    ),
                    "uploads_playlist_id": channel.get("contentDetails", {})
                    .get("relatedPlaylists", {})
                    .get("uploads"),
                }
            )
        return profiles

    def get_account_identity(self, access_token: str) -> Dict[str, Any]:
        url = "https://openidconnect.googleapis.com/v1/userinfo"
        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            resp = self._client.get(url, headers=headers)
        except Exception:
            return {}
        if resp.status_code != 200:
            return {}
        try:
            data = resp.json()
        except ValueError:
            return {}
        return {
            "sub": data.get("sub"),
            "email": data.get("email"),
            "name": data.get("name"),
        }

    def list_authorized_channel_ids(self, access_token: str) -> List[str]:
        return [
            profile["channel_id"]
            for profile in self.list_channel_profiles(access_token)
            if profile.get("channel_id")
        ]

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
        url = f"{self.UPLOAD_BASE}/videos?uploadType=resumable&part=snippet,status"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Length": str(total_bytes),
            "X-Upload-Content-Type": "video/*",
        }
        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags,
                "categoryId": category_id,
            },
            "status": {
                "privacyStatus": privacy,
                "selfDeclaredMadeForKids": False,
            },
        }

        try:
            resp = self._client.post(url, headers=headers, json=body)
        except Exception as e:
            raise PublishDomainException(f"Network error initiating YouTube upload: {str(e)}")

        if resp.status_code == 401:
            raise AuthenticationRequiredException("Access token expired during upload initiation.")
        if resp.status_code == 403:
            self._check_quota_and_forbidden_error(resp, "upload initiation")
        if resp.status_code == 400:
            err = resp.json().get("error", {}) if resp.headers.get("content-type", "").startswith("application/json") else {}
            msg = err.get("message", resp.text)
            raise PublishDomainException(f"YouTube video parametre hatası (HTTP 400): {msg}")
        if resp.status_code != 200:
            raise PublishDomainException(f"Failed to initiate upload session: HTTP {resp.status_code}: {resp.text}")

        session_uri = resp.headers.get("Location")
        if not session_uri:
            raise PublishDomainException("YouTube did not return a session URI (Location header missing).")

        return session_uri

    def upload_chunk(
        self,
        upload_session_uri: str,
        chunk_data: bytes,
        start_byte: int,
        total_bytes: int,
        max_retries: int = 3,
    ) -> Tuple[int, Optional[Dict[str, Any]]]:
        end_byte = start_byte + len(chunk_data) - 1
        headers = {
            "Content-Length": str(len(chunk_data)),
            "Content-Range": f"bytes {start_byte}-{end_byte}/{total_bytes}",
            "Content-Type": "application/octet-stream",
        }

        attempt = 0
        backoff = 1.0

        while True:
            try:
                resp = self._client.put(upload_session_uri, headers=headers, content=chunk_data)
            except (httpx.TimeoutException, httpx.NetworkError) as e:
                attempt += 1
                if attempt > max_retries:
                    raise PublishDomainException(f"Network error sending upload chunk after {max_retries} retries: {str(e)}")
                time.sleep(backoff)
                backoff = min(backoff * 2, 32.0)
                continue
            except Exception as e:
                raise PublishDomainException(f"Unexpected error sending upload chunk: {str(e)}")

            if resp.status_code == 308:
                return (308, None)
            elif resp.status_code in (200, 201):
                return (resp.status_code, resp.json())
            elif resp.status_code == 404:
                raise UploadSessionExpiredException("Upload session expired or invalid (HTTP 404).")
            elif resp.status_code == 401:
                raise AuthenticationRequiredException("Access token expired during chunk upload.")
            elif resp.status_code == 403:
                self._check_quota_and_forbidden_error(resp, "chunk upload")
            elif resp.status_code in (500, 502, 503, 504):
                attempt += 1
                if attempt > max_retries:
                    raise PublishDomainException(f"Upload chunk failed with server error HTTP {resp.status_code}: {resp.text}")

                retry_after = resp.headers.get("Retry-After")
                wait_seconds = backoff
                if retry_after:
                    try:
                        wait_seconds = float(retry_after)
                    except ValueError:
                        wait_seconds = backoff
                time.sleep(min(wait_seconds, 60.0))
                backoff = min(backoff * 2, 32.0)
                continue
            else:
                raise PublishDomainException(f"Upload chunk error HTTP {resp.status_code}: {resp.text}")

    def query_upload_status(self, upload_session_uri: str, total_bytes: int) -> int:
        headers = {
            "Content-Length": "0",
            "Content-Range": f"bytes */{total_bytes}",
        }
        try:
            resp = self._client.put(upload_session_uri, headers=headers)
        except Exception as e:
            raise PublishDomainException(f"Network error querying upload status: {str(e)}")

        if resp.status_code == 404:
            raise UploadSessionExpiredException("Upload session expired or invalid (HTTP 404).")

        if resp.status_code in (200, 201):
            data = None
            try:
                data = resp.json()
            except Exception:
                pass
            return UploadStatusResult(total_bytes, finalized_data=data)

        if resp.status_code == 308:
            range_header = resp.headers.get("Range")
            if not range_header:
                return UploadStatusResult(0)
            # Format: bytes=0-4194303
            m = re.search(r"bytes=0-(\d+)", range_header)
            if m:
                return UploadStatusResult(int(m.group(1)) + 1)
            return UploadStatusResult(0)

        if resp.status_code == 401:
            raise AuthenticationRequiredException("Access token expired during status query.")
        if resp.status_code == 403:
            self._check_quota_and_forbidden_error(resp, "status query")

        raise PublishDomainException(f"Query upload status returned HTTP {resp.status_code}: {resp.text}")

    def upload_custom_thumbnail(
        self,
        access_token: str,
        video_id: str,
        thumbnail_path: str,
    ) -> bool:
        if not os.path.exists(thumbnail_path):
            return False

        ext = os.path.splitext(thumbnail_path)[1].lower()
        content_type = "image/png" if ext == ".png" else "image/jpeg"

        url = f"{self.UPLOAD_BASE}/thumbnails/set?videoId={video_id}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": content_type,
        }

        try:
            with open(thumbnail_path, "rb") as f:
                content = f.read()
            resp = self._client.post(url, headers=headers, content=content)
            return resp.status_code in (200, 201)
        except Exception:
            return False

    def get_video_details(self, access_token: str, video_id: str) -> Dict[str, Any]:
        url = f"{self.API_BASE}/videos?part=snippet,status,processingDetails&id={video_id}"
        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            resp = self._client.get(url, headers=headers)
        except Exception as e:
            raise PublishDomainException(f"Network error querying video details: {str(e)}")

        if resp.status_code == 401:
            raise AuthenticationRequiredException("Access token expired querying video details.")
        if resp.status_code == 403:
            self._check_quota_and_forbidden_error(resp, "querying video details")
        if resp.status_code != 200:
            raise PublishDomainException(f"Failed to query video details (HTTP {resp.status_code}): {resp.text}")

        data = resp.json()
        items = data.get("items", [])
        return items[0] if items else {"not_found": True, "items": []}

    def _check_quota_and_forbidden_error(self, resp: httpx.Response, action_desc: str = "") -> None:
        try:
            err = resp.json().get("error", {})
            message = err.get("message", resp.text)
            errors = err.get("errors", [])
            for e in errors:
                reason = e.get("reason", "")
                if reason in ("quotaExceeded", "dailyLimitExceeded"):
                    raise QuotaExceededException(
                        "YouTube API günlük kota sınırına ulaşıldı (videos.insert günlük havuzu aşıldı). Pasifik Saati (PT) gece yarısı sıfırlanacaktır."
                    )
                if reason == "uploadLimitExceeded":
                    raise PublishDomainException(
                        "YouTube günlük video yükleme sınırına ulaşıldı (Kanal doğrulama veya YouTube yükleme kısıtı)."
                    )
                if reason == "accessNotConfigured":
                    raise PublishDomainException(
                        "YouTube Data API v3 Google Cloud Console üzerinde etkinleştirilmemiş."
                    )
            raise PublishDomainException(f"YouTube erişimi reddedildi ({action_desc}): {message}")
        except (ValueError, KeyError):
            raise PublishDomainException(f"YouTube 403 Forbidden: {resp.text}")

    def _check_quota_error(self, resp: httpx.Response) -> None:
        self._check_quota_and_forbidden_error(resp, "operation")
