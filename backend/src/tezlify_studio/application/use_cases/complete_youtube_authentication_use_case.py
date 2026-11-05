import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from tezlify_studio.application.dto.connection_dto import ConnectionDTO, connection_to_dto
from tezlify_studio.application.ports.channel_selection_repository_port import (
    ChannelSelectionRepositoryPort,
)
from tezlify_studio.application.ports.platform_channel_repository_port import (
    PlatformChannelRepositoryPort,
)
from tezlify_studio.application.ports.platform_connection_repository_port import (
    PlatformConnectionRepositoryPort,
)
from tezlify_studio.application.ports.token_storage_port import TokenStoragePort
from tezlify_studio.application.ports.youtube_publisher_port import YouTubePublisherPort
from tezlify_studio.application.use_cases.oauth_session_store import (
    INTENT_RECONNECT,
    oauth_session_store,
)
from tezlify_studio.domain.entities.platform_channel import PlatformChannel
from tezlify_studio.domain.entities.platform_connection import PlatformConnection
from tezlify_studio.domain.enums.connection_status import ConnectionStatus
from tezlify_studio.domain.enums.publish_status import SocialPlatform
from tezlify_studio.domain.exceptions.creator_exceptions import (
    ChannelBindingMismatchException,
    CreatorStudioException,
)
from tezlify_studio.domain.exceptions.publish_exceptions import (
    AuthenticationRequiredException,
    PublishDomainException,
)


class CompleteYouTubeAuthenticationUseCase:
    """Completes OAuth for a single Google account without touching others.

    Every invocation creates or updates exactly one ``PlatformConnection`` and
    its discovered channels. Existing connections are only rewritten when the
    callback can be tied to that same Google account (matching OIDC subject or
    an already-owned channel), so adding a second account never overwrites the
    first one.
    """

    def __init__(
        self,
        connection_repo: PlatformConnectionRepositoryPort,
        channel_repo: PlatformChannelRepositoryPort,
        selection_repo: ChannelSelectionRepositoryPort,
        token_storage: TokenStoragePort,
        publisher: YouTubePublisherPort,
    ):
        self.connection_repo = connection_repo
        self.channel_repo = channel_repo
        self.selection_repo = selection_repo
        self.token_storage = token_storage
        self.publisher = publisher

    def execute(self, code: str, state: str) -> ConnectionDTO:
        session = oauth_session_store.consume_session(state)
        if not session:
            raise AuthenticationRequiredException(
                "Geçersiz veya süresi dolmuş OAuth state oturumu."
            )

        tokens = self.publisher.exchange_code_for_tokens(
            code=code,
            code_verifier=session.code_verifier,
            redirect_uri=session.redirect_uri,
        )
        access_token = tokens.get("access_token")
        if not access_token:
            raise AuthenticationRequiredException("Google'dan access_token alınamadı.")

        expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=int(tokens.get("expires_in", 3600))
        )

        identity = self._identity(access_token)
        profiles = [
            profile
            for profile in self.publisher.list_channel_profiles(access_token)
            if profile.get("channel_id")
        ]
        if not profiles:
            raise PublishDomainException(
                "Bu Google hesabına bağlı erişilebilir bir YouTube kanalı bulunamadı. "
                "Lütfen YouTube Studio üzerinden bir kanal oluşturun."
            )

        account_external_id = self._account_external_id(identity, profiles)
        connection = self._find_connection(
            session.intent, session.connection_id, account_external_id, profiles
        )
        is_new = connection is None
        if connection is None:
            connection = PlatformConnection(
                id=str(uuid.uuid4()),
                platform=SocialPlatform.YOUTUBE,
                account_external_id=account_external_id,
                account_display_name="YouTube Account",
            )
        elif connection.account_external_id.startswith("legacy:"):
            # Upgrade the migrated identity once the real Google subject is known.
            connection.account_external_id = account_external_id

        connection.platform = SocialPlatform.YOUTUBE
        connection.account_display_name = self._display_name(
            identity, profiles, connection if not is_new else None
        )
        connection.connection_status = ConnectionStatus.ACTIVE
        connection.token_expires_at = expires_at
        connection.granted_scopes = self._scopes(tokens, connection)
        if not connection.token_reference:
            connection.token_reference = f"youtube.connection.{connection.id}"
        connection.updated_at = datetime.now(timezone.utc)
        saved = self.connection_repo.save(connection)

        refresh_token = tokens.get("refresh_token")
        if not refresh_token:
            refresh_token = self.token_storage.get_refresh_token(saved.token_reference)
        if not refresh_token:
            raise AuthenticationRequiredException(
                "Google yenileme anahtarı döndürmedi. Hesabı yeniden bağlayın."
            )
        self.token_storage.store_tokens(
            saved.token_reference, access_token, refresh_token
        )

        channels = self._upsert_channels(saved, profiles)
        self._ensure_selection(saved, channels)
        return connection_to_dto(saved, channels)

    # ------------------------------------------------------------------ helpers

    def _identity(self, access_token: str) -> Dict[str, Any]:
        try:
            return self.publisher.get_account_identity(access_token) or {}
        except Exception:  # noqa: BLE001 - identity is an enhancement, not a gate
            return {}

    @staticmethod
    def _account_external_id(
        identity: Dict[str, Any], profiles: List[Dict[str, Any]]
    ) -> str:
        subject = identity.get("sub")
        if subject:
            return f"google:{subject}"
        email = identity.get("email")
        if email:
            return f"google-email:{email}"
        # A YouTube channel id is real API data and stable across grants.
        return f"youtube-channel:{profiles[0]['channel_id']}"

    def _display_name(
        self,
        identity: Dict[str, Any],
        profiles: List[Dict[str, Any]],
        existing: Optional[PlatformConnection],
    ) -> str:
        for candidate in (identity.get("name"), identity.get("email")):
            if candidate:
                return str(candidate)
        if existing and existing.account_display_name:
            return existing.account_display_name
        return str(profiles[0].get("channel_title") or "YouTube Account")

    @staticmethod
    def _scopes(
        tokens: Dict[str, Any], connection: PlatformConnection
    ) -> List[str]:
        raw = tokens.get("scope")
        if isinstance(raw, str) and raw.strip():
            return [item for item in raw.split() if item]
        return list(connection.granted_scopes)

    def _find_connection(
        self,
        intent: str,
        reconnect_id: Optional[str],
        account_external_id: str,
        profiles: List[Dict[str, Any]],
    ) -> Optional[PlatformConnection]:
        if intent == INTENT_RECONNECT and reconnect_id:
            target = self.connection_repo.get_by_id(reconnect_id)
            if target is None:
                raise CreatorStudioException(
                    "Yeniden bağlanılacak hesap bulunamadı.", "CONNECTION_NOT_FOUND"
                )
            conflict = self.connection_repo.get_by_platform_account(
                SocialPlatform.YOUTUBE.value, account_external_id
            )
            if conflict and conflict.id != target.id:
                raise ChannelBindingMismatchException(target.id)
            if target.account_external_id != account_external_id:
                self._assert_channels_not_owned_by_others(target.id, profiles)
            return target

        match = self.connection_repo.get_by_platform_account(
            SocialPlatform.YOUTUBE.value, account_external_id
        )
        if match:
            return match

        for profile in profiles:
            owner = self.channel_repo.find_by_external_id(
                SocialPlatform.YOUTUBE.value, profile["channel_id"]
            )
            if owner:
                existing = self.connection_repo.get_by_id(owner.platform_connection_id)
                if existing and existing.account_external_id.startswith("legacy:"):
                    return existing
                if existing and existing.account_external_id == account_external_id:
                    return existing
                raise ChannelBindingMismatchException(profile["channel_id"])
        return None

    def _assert_channels_not_owned_by_others(
        self, connection_id: str, profiles: List[Dict[str, Any]]
    ) -> None:
        for profile in profiles:
            owner = self.channel_repo.find_by_external_id(
                SocialPlatform.YOUTUBE.value, profile["channel_id"]
            )
            if not owner or owner.platform_connection_id == connection_id:
                continue
            owner_connection = self.connection_repo.get_by_id(owner.platform_connection_id)
            if owner_connection and owner_connection.is_active:
                raise ChannelBindingMismatchException(profile["channel_id"])

    def _upsert_channels(
        self, connection: PlatformConnection, profiles: List[Dict[str, Any]]
    ) -> List[PlatformChannel]:
        existing_channels = self.channel_repo.list_by_connection(connection.id)
        by_external = {item.channel_external_id: item for item in existing_channels}
        discovered_ids = {profile["channel_id"] for profile in profiles}
        has_primary = any(
            item.is_primary and item.channel_external_id in discovered_ids
            for item in existing_channels
        )

        result: List[PlatformChannel] = []
        for index, profile in enumerate(profiles):
            external_id = profile["channel_id"]
            owner = self.channel_repo.find_by_external_id(
                SocialPlatform.YOUTUBE.value, external_id
            )
            channel = by_external.get(external_id)
            if channel is None and owner is not None:
                if owner.platform_connection_id != connection.id:
                    owner_connection = self.connection_repo.get_by_id(
                        owner.platform_connection_id
                    )
                    if owner_connection and owner_connection.is_active:
                        raise ChannelBindingMismatchException(external_id)
                    owner.platform_connection_id = connection.id
                channel = owner
            if channel is None:
                channel = PlatformChannel(
                    id=uuid.uuid4().hex,
                    platform_connection_id=connection.id,
                    platform=connection.platform,
                    channel_external_id=external_id,
                    channel_name=str(profile.get("channel_title") or external_id),
                )

            channel.platform = SocialPlatform.YOUTUBE
            channel.platform_connection_id = connection.id
            channel.apply_profile(
                name=str(profile.get("channel_title") or channel.channel_name),
                handle=profile.get("custom_url"),
                avatar_url=profile.get("avatar_url"),
                description=profile.get("description") or "",
                subscriber_count=profile.get("subscriber_count"),
                uploads_playlist_id=profile.get("uploads_playlist_id"),
            )
            channel.is_enabled = True
            channel.is_primary = (not has_primary and index == 0) or (
                has_primary and channel.is_primary
            )
            result.append(self.channel_repo.save(channel))

        for channel in existing_channels:
            if channel.channel_external_id not in discovered_ids and channel.is_enabled:
                channel.is_enabled = False
                channel.updated_at = datetime.now(timezone.utc)
                self.channel_repo.save(channel)

        return sorted(result, key=lambda item: (not item.is_primary, item.channel_name.lower()))

    def _ensure_selection(
        self, connection: PlatformConnection, channels: List[PlatformChannel]
    ) -> None:
        selection = self.selection_repo.get()
        if selection.active_channel_id:
            current = self.channel_repo.get_by_id(selection.active_channel_id)
            if current and current.is_enabled:
                return
        if not channels:
            return
        selection.select(channels[0].id)
        selection.default_platform = connection.platform.value
        self.selection_repo.save(selection)
