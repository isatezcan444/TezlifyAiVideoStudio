from typing import List

from tezlify_studio.domain.value_objects.creator_models import PlatformDescriptor

YOUTUBE_CAPABILITIES = {
    "connect_oauth": True,
    "disconnect": True,
    "list_accounts": True,
    "list_channels": True,
    "get_channel_profile": True,
    "list_videos": True,
    "upload_video": True,
    "update_video": True,
    "get_analytics": True,
    "read_comments": True,
    "write_comments": True,
    "schedule_publish": True,
    "monetization_revenue": False,
}

_UNSUPPORTED_CAPABILITIES = {
    "connect_oauth": False,
    "disconnect": False,
    "list_accounts": False,
    "list_channels": False,
    "get_channel_profile": False,
    "list_videos": False,
    "upload_video": False,
    "update_video": False,
    "get_analytics": False,
    "read_comments": False,
    "write_comments": False,
    "schedule_publish": False,
    "monetization_revenue": False,
}


class PlatformCatalog:
    """Static capability map.

    Instagram and TikTok are described so the UI can render them as unavailable;
    they expose no OAuth flow, no API calls and no sample data.
    """

    def list_platforms(self) -> List[PlatformDescriptor]:
        return [
            PlatformDescriptor(
                id="youtube",
                display_name="YouTube",
                implemented=True,
                capabilities=dict(YOUTUBE_CAPABILITIES),
            ),
            PlatformDescriptor(
                id="instagram",
                display_name="Instagram",
                implemented=False,
                capabilities=dict(_UNSUPPORTED_CAPABILITIES),
            ),
            PlatformDescriptor(
                id="tiktok",
                display_name="TikTok",
                implemented=False,
                capabilities=dict(_UNSUPPORTED_CAPABILITIES),
            ),
        ]
