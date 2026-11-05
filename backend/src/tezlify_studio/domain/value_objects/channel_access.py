from dataclasses import dataclass

from tezlify_studio.domain.enums.publish_status import SocialPlatform


@dataclass(frozen=True)
class ChannelAccess:
    """A short-lived, channel-bound credential bundle.

    Access tokens are resolved per connection and are never exposed outside the
    adapter that consumes them.
    """

    platform: SocialPlatform
    channel_id: str
    external_channel_id: str
    connection_id: str
    access_token: str
