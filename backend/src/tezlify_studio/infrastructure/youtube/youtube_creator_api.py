import html
import re
from typing import Any, Dict, List, Optional

import httpx

from tezlify_studio.application.ports.analytics_port import AnalyticsPort
from tezlify_studio.application.ports.channel_port import ChannelPort
from tezlify_studio.application.ports.comment_port import CommentPort
from tezlify_studio.domain.exceptions.creator_exceptions import (
    AnalyticsUnavailableException,
    ChannelBindingMismatchException,
    CreatorApiException,
    InsufficientScopeException,
)
from tezlify_studio.domain.exceptions.publish_exceptions import (
    AuthenticationRequiredException,
    QuotaExceededException,
)
from tezlify_studio.domain.value_objects.channel_access import ChannelAccess
from tezlify_studio.domain.value_objects.creator_models import (
    AnalyticsResult,
    AnalyticsRow,
    ChannelPlaylist,
    ChannelProfile,
    ChannelVideo,
    DateRange,
    VideoComment,
    YOUTUBE_ANALYTICS_METRICS,
)
from tezlify_studio.domain.value_objects.youtube_capabilities import (
    BASE_CAPABILITIES,
    CAPABILITY_SCOPE_MAP,
    SCOPE_ANALYTICS as _SCOPE_ANALYTICS,
    SCOPE_CHANNEL_READ as _SCOPE_CHANNEL_READ,
    SCOPE_COMMENTS as _SCOPE_COMMENTS,
    SCOPE_EMAIL,
    SCOPE_OPENID,
    SCOPE_PROFILE,
    SCOPE_REVENUE as _SCOPE_REVENUE,
    SCOPE_UPLOAD as _SCOPE_UPLOAD,
)

SCOPE_IDENTITY = [SCOPE_OPENID, SCOPE_EMAIL, SCOPE_PROFILE]
SCOPE_CHANNEL_READ = [_SCOPE_CHANNEL_READ]
SCOPE_ANALYTICS = [_SCOPE_ANALYTICS]
SCOPE_REVENUE = [_SCOPE_REVENUE]
SCOPE_UPLOAD = [_SCOPE_UPLOAD]
SCOPE_COMMENTS = [_SCOPE_COMMENTS]

# Capability boundaries are explicit so incremental authorization can request
# only what a feature needs. Revenue stays opt-in.
SCOPE_CAPABILITIES = {
    capability: [scope for scope in scopes]
    for capability, scopes in CAPABILITY_SCOPE_MAP.items()
    if capability != "revenue"
}

OPTIONAL_SCOPES = {"revenue": SCOPE_REVENUE}

BASE_SCOPES = [
    scope
    for capability in BASE_CAPABILITIES
    for scope in CAPABILITY_SCOPE_MAP[capability]
]

YOUTUBE_SCOPES = [
    *SCOPE_IDENTITY,
    *SCOPE_CHANNEL_READ,
    *SCOPE_ANALYTICS,
    *SCOPE_UPLOAD,
    *SCOPE_COMMENTS,
]

_ISO_DURATION = re.compile(
    r"^P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+(?:\.\d+)?)S)?)?$"
)


def parse_iso_duration(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    match = _ISO_DURATION.match(value)
    if not match:
        return None
    parts = {key: float(raw) for key, raw in match.groupdict().items() if raw is not None}
    seconds = (
        parts.get("days", 0) * 86400
        + parts.get("hours", 0) * 3600
        + parts.get("minutes", 0) * 60
        + parts.get("seconds", 0)
    )
    return int(seconds)


# YouTube Analytics v2 exposes the traffic-source report as
# ``insightTrafficSourceType``, and some report dimensions reject the
# subscriber metrics. Public dimension keys stay unchanged for the UI/API; only
# the Google request is adapted. Top-videos reports additionally require both a
# sort and maxResults, otherwise Google answers "The query is not supported".
_ANALYTICS_DIMENSION_ALIASES = {"trafficSourceType": "insightTrafficSourceType"}
_ANALYTICS_UNSUPPORTED_METRICS = {
    "trafficSourceType": frozenset({"subscribersGained", "subscribersLost"}),
    "deviceType": frozenset({"subscribersGained", "subscribersLost"}),
}
_ANALYTICS_TOP_VIDEOS_LIMIT = 25


class YouTubeCreatorApi(ChannelPort, AnalyticsPort, CommentPort):
    """Channel-bound YouTube Data API v3 + Analytics API v2 adapter.

    Every request carries the access token of one connection and is scoped to
    one channel id. ``mine=true`` / ``channel==MINE`` are deliberately not used:
    a Google account can own several channels, so "mine" would silently operate
    on whichever channel YouTube considers default.
    """

    API_BASE = "https://www.googleapis.com/youtube/v3"
    ANALYTICS_BASE = "https://youtubeanalytics.googleapis.com/v2/reports"

    def __init__(
        self,
        access: ChannelAccess,
        client: Optional[httpx.Client] = None,
    ) -> None:
        if not access.external_channel_id:
            raise ChannelBindingMismatchException(access.channel_id)
        self.access = access
        self._client = client or httpx.Client(timeout=30.0)

    # ------------------------------------------------------------------ helpers

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.access.access_token}"}

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        action: str = "YouTube isteği",
    ) -> Dict[str, Any]:
        try:
            response = self._client.request(
                method, url, headers=self._headers(), params=params, json=json_body
            )
        except httpx.HTTPError as exc:
            raise CreatorApiException(f"{action} sırasında ağ hatası: {exc}")

        if response.status_code == 401:
            raise AuthenticationRequiredException(
                f"{action} sırasında YouTube erişim anahtarı geçersiz. Hesabı yeniden bağlayın."
            )
        if response.status_code == 403:
            self._raise_forbidden(response, action)
        if response.status_code == 404:
            raise CreatorApiException(f"{action}: kayıt bulunamadı.", status_code=404)
        if response.status_code >= 400:
            raise CreatorApiException(
                f"{action} başarısız (HTTP {response.status_code}): {response.text[:400]}",
                status_code=response.status_code,
            )
        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError:
            raise CreatorApiException(f"{action}: YouTube geçersiz JSON döndürdü.")

    def _raise_forbidden(self, response: httpx.Response, action: str) -> None:
        try:
            error = response.json().get("error", {})
        except ValueError:
            raise CreatorApiException(f"{action} reddedildi (HTTP 403): {response.text[:300]}")

        reasons = [item.get("reason", "") for item in error.get("errors", [])]
        message = error.get("message", response.text[:300])

        if any(reason in ("quotaExceeded", "dailyLimitExceeded") for reason in reasons):
            raise QuotaExceededException(
                "YouTube API günlük kota sınırına ulaşıldı. Kota Pasifik Saati gece yarısı sıfırlanır."
            )
        if any(
            reason in ("insufficientPermissions", "ACCESS_TOKEN_SCOPE_INSUFFICIENT")
            for reason in reasons
        ) or "insufficient" in message.lower():
            required = "https://www.googleapis.com/auth/yt-analytics.readonly"
            if "comment" in action.lower():
                required = "https://www.googleapis.com/auth/youtube.force-ssl"
            raise InsufficientScopeException(required, action)
        if any(reason == "accessNotConfigured" for reason in reasons):
            raise CreatorApiException(
                f"{action}: ilgili YouTube API Google Cloud projesinde etkin değil.", status_code=403
            )
        if any(reason == "commentsDisabled" for reason in reasons):
            raise CreatorApiException(
                "Bu videoda yorumlar kapalı. Yorumları görüntülemek veya yönetmek "
                "için YouTube Studio üzerinden yorumları açın.",
                status_code=403,
            )
        raise CreatorApiException(f"{action} reddedildi: {_plain_text(message)}", status_code=403)

    # ------------------------------------------------------------------ channel

    def _channel_payload(self) -> Dict[str, Any]:
        data = self._request(
            "GET",
            f"{self.API_BASE}/channels",
            params={
                "part": "snippet,statistics,contentDetails",
                "id": self.access.external_channel_id,
            },
            action="Kanal bilgisi alınamadı",
        )
        items = data.get("items", [])
        if not items:
            raise ChannelBindingMismatchException(self.access.channel_id)
        return items[0]

    def get_channel(self) -> ChannelProfile:
        channel = self._channel_payload()
        snippet = channel.get("snippet", {})
        stats = channel.get("statistics", {})
        thumbs = snippet.get("thumbnails", {})
        hidden = stats.get("hiddenSubscriberCount", False)
        return ChannelProfile(
            channel_id=channel.get("id", ""),
            title=snippet.get("title", ""),
            description=snippet.get("description", ""),
            avatar_url=(thumbs.get("medium") or thumbs.get("default") or {}).get("url"),
            custom_url=snippet.get("customUrl"),
            country=snippet.get("country"),
            published_at=snippet.get("publishedAt"),
            subscriber_count=None if hidden else _as_int(stats.get("subscriberCount")),
            video_count=_as_int(stats.get("videoCount")),
            view_count=_as_int(stats.get("viewCount")),
            hidden_subscriber_count=bool(hidden),
            uploads_playlist_id=channel.get("contentDetails", {})
            .get("relatedPlaylists", {})
            .get("uploads"),
        )

    # ------------------------------------------------------------------ videos

    def list_videos(self, max_results: int = 25, page_token: Optional[str] = None) -> Dict[str, Any]:
        channel = self._channel_payload()
        uploads = channel.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
        if not uploads:
            return {"items": [], "next_page_token": None, "total_results": 0}

        playlist_params: Dict[str, Any] = {
            "part": "contentDetails",
            "playlistId": uploads,
            "maxResults": min(max(max_results, 1), 50),
        }
        if page_token:
            playlist_params["pageToken"] = page_token
        playlist = self._request(
            "GET",
            f"{self.API_BASE}/playlistItems",
            params=playlist_params,
            action="Kanal videoları listelenemedi",
        )
        ids = [
            item.get("contentDetails", {}).get("videoId")
            for item in playlist.get("items", [])
            if item.get("contentDetails", {}).get("videoId")
        ]
        videos = self._fetch_videos(ids) if ids else []
        return {
            "items": videos,
            "next_page_token": playlist.get("nextPageToken"),
            "total_results": playlist.get("pageInfo", {}).get("totalResults", len(videos)),
        }

    def _fetch_videos(self, ids: List[str]) -> List[ChannelVideo]:
        data = self._request(
            "GET",
            f"{self.API_BASE}/videos",
            params={
                "part": "snippet,status,statistics,contentDetails",
                "id": ",".join(ids),
                "maxResults": 50,
            },
            action="Video detayları alınamadı",
        )
        return [self._map_video(item) for item in data.get("items", [])]

    def _assert_video_owned(self, video_id: str) -> None:
        channel = self._channel_payload()
        uploads = channel.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
        if not uploads:
            raise ChannelBindingMismatchException(self.access.channel_id)
        data = self._request(
            "GET",
            f"{self.API_BASE}/playlistItems",
            params={
                "part": "contentDetails",
                "playlistId": uploads,
                "videoId": video_id,
                "maxResults": 1,
            },
            action="Video sahipliği doğrulanamadı",
        )
        for item in data.get("items", []):
            if item.get("contentDetails", {}).get("videoId") == video_id:
                return
        raise ChannelBindingMismatchException(self.access.channel_id)

    def _map_video(self, item: Dict[str, Any]) -> ChannelVideo:
        snippet = item.get("snippet", {})
        status = item.get("status", {})
        stats = item.get("statistics", {})
        thumbs = snippet.get("thumbnails", {})
        return ChannelVideo(
            video_id=item.get("id", ""),
            title=snippet.get("title", ""),
            description=snippet.get("description", ""),
            published_at=snippet.get("publishedAt"),
            thumbnail_url=(thumbs.get("medium") or thumbs.get("default") or {}).get("url"),
            privacy_status=status.get("privacyStatus"),
            upload_status=status.get("uploadStatus"),
            duration_seconds=parse_iso_duration(item.get("contentDetails", {}).get("duration")),
            view_count=_as_int(stats.get("viewCount")),
            like_count=_as_int(stats.get("likeCount")),
            comment_count=_as_int(stats.get("commentCount")),
            tags=snippet.get("tags", []),
            category_id=snippet.get("categoryId"),
        )

    def get_video(self, video_id: str) -> ChannelVideo:
        self._assert_video_owned(video_id)
        items = self._fetch_videos([video_id])
        if not items:
            raise CreatorApiException("Video bulunamadı.", status_code=404)
        return items[0]

    def update_video(self, video_id: str, changes: Dict[str, Any]) -> ChannelVideo:
        current = self.get_video(video_id)
        snippet: Dict[str, Any] = {
            "title": changes.get("title") or current.title,
            "description": (
                changes["description"]
                if changes.get("description") is not None
                else current.description
            ),
            "tags": changes.get("tags") if changes.get("tags") is not None else current.tags,
            "categoryId": changes.get("category_id") or current.category_id or "22",
        }
        body: Dict[str, Any] = {"id": video_id, "snippet": snippet}
        privacy = changes.get("privacy_status")
        if privacy:
            body["status"] = {"privacyStatus": privacy}

        data = self._request(
            "PUT",
            f"{self.API_BASE}/videos",
            params={"part": "snippet,status"},
            json_body=body,
            action="Video bilgileri güncellenemedi",
        )
        return self._map_video(data)

    def list_playlists(self, max_results: int = 25) -> List[ChannelPlaylist]:
        data = self._request(
            "GET",
            f"{self.API_BASE}/playlists",
            params={
                "part": "snippet,contentDetails",
                "channelId": self.access.external_channel_id,
                "maxResults": min(max(max_results, 1), 50),
            },
            action="Oynatma listeleri alınamadı",
        )
        playlists: List[ChannelPlaylist] = []
        for item in data.get("items", []):
            snippet = item.get("snippet", {})
            playlists.append(
                ChannelPlaylist(
                    playlist_id=item.get("id", ""),
                    title=snippet.get("title", ""),
                    description=snippet.get("description", ""),
                    item_count=_as_int(item.get("contentDetails", {}).get("itemCount")),
                    published_at=snippet.get("publishedAt"),
                )
            )
        return playlists

    def list_video_categories(self) -> List[Dict[str, str]]:
        data = self._request(
            "GET",
            f"{self.API_BASE}/videoCategories",
            params={"part": "snippet", "regionCode": "TR"},
            action="Video kategorileri alınamadı",
        )
        return [
            {
                "id": item.get("id", ""),
                "title": item.get("snippet", {}).get("title", ""),
            }
            for item in data.get("items", [])
            if item.get("snippet", {}).get("assignable", True)
        ]

    # ------------------------------------------------------------------ analytics

    def query(
        self,
        date_range: DateRange,
        metrics: Optional[List[str]] = None,
        dimensions: Optional[List[str]] = None,
        include_revenue: bool = False,
    ) -> AnalyticsResult:
        requested = list(metrics or YOUTUBE_ANALYTICS_METRICS)
        invalid = [metric for metric in requested if metric not in YOUTUBE_ANALYTICS_METRICS]
        if invalid:
            raise CreatorApiException(f"Desteklenmeyen metrikler: {', '.join(invalid)}", 400)
        dimension_list = list(dimensions or ["day"])

        try:
            totals = self._analytics_query(requested, [], date_range)
            rows = self._analytics_query(requested, dimension_list, date_range)
        except (AnalyticsUnavailableException, InsufficientScopeException) as exc:
            reason = "insufficient_scope" if isinstance(exc, InsufficientScopeException) else exc.reason
            return AnalyticsResult(
                available=False,
                reason=reason,
                start_date=date_range.start_date.isoformat(),
                end_date=date_range.end_date.isoformat(),
                metrics=requested,
                dimensions=dimension_list,
            )
        except AuthenticationRequiredException:
            raise

        revenue: Optional[Dict[str, Any]] = None
        if include_revenue:
            try:
                revenue_rows = self._analytics_query(["estimatedRevenue"], [], date_range)
                revenue = {
                    "available": True,
                    "amount": revenue_rows["totals"].get("estimatedRevenue"),
                    "currency": "USD",
                    "note": "YouTube Analytics tarafından raporlanan tahmini gelir.",
                }
            except (AnalyticsUnavailableException, InsufficientScopeException) as exc:
                revenue = {
                    "available": False,
                    "reason": getattr(exc, "reason", "insufficient_scope"),
                    "note": "Gelir metriği için yt-analytics-monetary.readonly izni gerekir.",
                }

        return AnalyticsResult(
            available=True,
            start_date=date_range.start_date.isoformat(),
            end_date=date_range.end_date.isoformat(),
            metrics=requested,
            dimensions=dimension_list,
            totals=totals["totals"],
            rows=rows["rows"],
            revenue=revenue,
        )

    def _analytics_query(
        self,
        metrics: List[str],
        dimensions: List[str],
        date_range: DateRange,
    ) -> Dict[str, Any]:
        requested_dimensions = list(dimensions)
        google_dimensions = [
            _ANALYTICS_DIMENSION_ALIASES.get(name, name)
            for name in requested_dimensions
        ]
        unsupported_metrics = set().union(
            *(
                _ANALYTICS_UNSUPPORTED_METRICS.get(name, frozenset())
                for name in requested_dimensions
            )
        )
        effective_metrics = [
            metric for metric in metrics if metric not in unsupported_metrics
        ]

        params: Dict[str, Any] = {
            "ids": f"channel=={self.access.external_channel_id}",
            "startDate": date_range.start_date.isoformat(),
            "endDate": date_range.end_date.isoformat(),
            "metrics": ",".join(effective_metrics),
        }
        if google_dimensions:
            params["dimensions"] = ",".join(google_dimensions)
            params["sort"] = (
                "-views" if "views" in effective_metrics else google_dimensions[0]
            )
            if "video" in requested_dimensions:
                params["maxResults"] = _ANALYTICS_TOP_VIDEOS_LIMIT

        try:
            response = self._client.get(
                self.ANALYTICS_BASE, headers=self._headers(), params=params
            )
        except httpx.HTTPError as exc:
            raise CreatorApiException(f"YouTube Analytics isteği başarısız: {exc}")

        if response.status_code == 401:
            raise AuthenticationRequiredException(
                "YouTube Analytics isteği için erişim anahtarı geçersiz."
            )
        if response.status_code == 403:
            try:
                error = response.json().get("error", {})
            except ValueError:
                raise AnalyticsUnavailableException("forbidden", response.text[:200])
            reasons = [item.get("reason", "") for item in error.get("errors", [])]
            message = error.get("message", "")
            if any(
                reason in ("insufficientPermissions", "ACCESS_TOKEN_SCOPE_INSUFFICIENT")
                for reason in reasons
            ) or "insufficient" in message.lower():
                raise InsufficientScopeException(
                    "https://www.googleapis.com/auth/yt-analytics.readonly",
                    "YouTube Analytics",
                )
            if any(reason == "accessNotConfigured" for reason in reasons):
                raise AnalyticsUnavailableException(
                    "api_not_enabled",
                    "YouTube Analytics API Google Cloud projesinde etkin değil.",
                )
            if any(reason in ("quotaExceeded", "dailyLimitExceeded") for reason in reasons):
                raise QuotaExceededException("YouTube Analytics kotası aşıldı.")
            raise AnalyticsUnavailableException("forbidden", message)
        if response.status_code >= 400:
            raise AnalyticsUnavailableException(
                "api_error", f"HTTP {response.status_code}: {response.text[:200]}"
            )

        data = response.json()
        headers = data.get("columnHeaders", [])
        raw_rows = data.get("rows", [])
        reverse_dimension_names = {
            google: requested
            for requested, google in zip(requested_dimensions, google_dimensions)
        }
        dimension_names = [
            reverse_dimension_names.get(header["name"], header["name"])
            for header in headers
            if header.get("columnType") == "DIMENSION"
        ]
        metric_names = [header["name"] for header in headers if header.get("columnType") == "METRIC"]

        parsed_rows: List[AnalyticsRow] = []
        for raw in raw_rows:
            dim_values = raw[: len(dimension_names)]
            metric_values = raw[len(dimension_names):]
            parsed_rows.append(
                AnalyticsRow(
                    dimensions=dict(zip(dimension_names, [str(value) for value in dim_values])),
                    metrics=dict(zip(metric_names, [float(value) for value in metric_values])),
                )
            )

        # The totals query is sent without dimensions, so its single row already
        # holds YouTube's authoritative period totals (no client-side summing of
        # average metrics).
        totals = parsed_rows[0].metrics if not dimension_names and parsed_rows else {}

        return {"rows": parsed_rows, "totals": totals}

    # ------------------------------------------------------------------ comments

    def _assert_comment_owned(self, comment_id: str) -> None:
        data = self._request(
            "GET",
            f"{self.API_BASE}/comments",
            params={"part": "snippet", "id": comment_id},
            action="Yorum sahipliği doğrulanamadı",
        )
        items = data.get("items", [])
        if not items:
            raise CreatorApiException("Yorum bulunamadı.", status_code=404)
        channel_id = items[0].get("snippet", {}).get("channelId")
        if channel_id != self.access.external_channel_id:
            raise ChannelBindingMismatchException(self.access.channel_id)

    def list_comments(
        self,
        video_id: Optional[str] = None,
        max_results: int = 25,
        page_token: Optional[str] = None,
    ) -> List[VideoComment]:
        params: Dict[str, Any] = {
            "part": "snippet,replies",
            "maxResults": min(max(max_results, 1), 100),
            "order": "time",
        }
        if video_id:
            self._assert_video_owned(video_id)
            params["videoId"] = video_id
        else:
            params["allThreadsRelatedToChannelId"] = self.access.external_channel_id
        if page_token:
            params["pageToken"] = page_token

        data = self._request(
            "GET",
            f"{self.API_BASE}/commentThreads",
            params=params,
            action="Yorumlar alınamadı",
        )
        comments: List[VideoComment] = []
        for thread in data.get("items", []):
            top = thread.get("snippet", {}).get("topLevelComment", {})
            snippet = top.get("snippet", {})
            comments.append(
                VideoComment(
                    comment_id=top.get("id", ""),
                    video_id=snippet.get("videoId", video_id or ""),
                    author=snippet.get("authorDisplayName", ""),
                    text=snippet.get("textOriginal") or snippet.get("textDisplay", ""),
                    like_count=_as_int(snippet.get("likeCount")) or 0,
                    published_at=snippet.get("publishedAt"),
                    updated_at=snippet.get("updatedAt"),
                    total_reply_count=_as_int(thread.get("snippet", {}).get("totalReplyCount")) or 0,
                )
            )
        return comments

    def reply_to_comment(self, parent_comment_id: str, text: str) -> VideoComment:
        self._assert_comment_owned(parent_comment_id)
        data = self._request(
            "POST",
            f"{self.API_BASE}/comments",
            params={"part": "snippet"},
            json_body={"snippet": {"parentId": parent_comment_id, "textOriginal": text}},
            action="Yoruma yanıt verilemedi",
        )
        snippet = data.get("snippet", {})
        return VideoComment(
            comment_id=data.get("id", ""),
            video_id=snippet.get("videoId", ""),
            author=snippet.get("authorDisplayName", ""),
            text=snippet.get("textOriginal", text),
            like_count=_as_int(snippet.get("likeCount")) or 0,
            published_at=snippet.get("publishedAt"),
            updated_at=snippet.get("updatedAt"),
        )

    def set_moderation_status(self, comment_id: str, status: str) -> VideoComment:
        allowed = {"published", "heldForReview", "rejected"}
        if status not in allowed:
            raise CreatorApiException(
                f"Geçersiz moderasyon durumu '{status}'. Geçerli: {', '.join(sorted(allowed))}'",
                400,
            )
        self._assert_comment_owned(comment_id)
        self._request(
            "POST",
            f"{self.API_BASE}/comments/setModerationStatus",
            params={"id": comment_id, "moderationStatus": status},
            action="Yorum moderasyonu güncellenemedi",
        )
        return VideoComment(
            comment_id=comment_id,
            video_id="",
            author="",
            text="",
            moderation_status=status,
        )


def _plain_text(value: Any) -> str:
    """Google error messages sometimes embed HTML; never surface markup in the UI."""
    return html.unescape(re.sub(r"<[^>]+>", "", str(value))).strip()


def _as_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
