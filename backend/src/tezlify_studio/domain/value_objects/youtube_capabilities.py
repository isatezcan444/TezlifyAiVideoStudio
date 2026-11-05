"""Independent YouTube OAuth capabilities and their Google scopes.

A capability is what the product can do with one connection; a scope is what
Google actually granted. The two are deliberately mapped separately so the
application can tell "permission was never requested" apart from "permission
was requested but Google withheld it".

Identity and channel reading are the base grant every connection needs. Every
other capability is incremental and only requested when the user actively uses
that feature.
"""

from typing import Iterable, List, Optional, Sequence

CAPABILITY_IDENTITY = "identity"
CAPABILITY_CHANNEL_READ = "channel_read"
CAPABILITY_ANALYTICS = "analytics"
CAPABILITY_UPLOAD = "upload"
CAPABILITY_COMMENTS = "comments"
CAPABILITY_REVENUE = "revenue"

SCOPE_OPENID = "openid"
SCOPE_EMAIL = "https://www.googleapis.com/auth/userinfo.email"
SCOPE_PROFILE = "https://www.googleapis.com/auth/userinfo.profile"
SCOPE_CHANNEL_READ = "https://www.googleapis.com/auth/youtube.readonly"
SCOPE_ANALYTICS = "https://www.googleapis.com/auth/yt-analytics.readonly"
SCOPE_REVENUE = "https://www.googleapis.com/auth/yt-analytics-monetary.readonly"
SCOPE_UPLOAD = "https://www.googleapis.com/auth/youtube.upload"
SCOPE_COMMENTS = "https://www.googleapis.com/auth/youtube.force-ssl"

# Legacy aliases kept for the YouTube adapter's public constants.
SCOPE_IDENTITY = [SCOPE_OPENID, SCOPE_EMAIL, SCOPE_PROFILE]

CAPABILITY_SCOPE_MAP = {
    CAPABILITY_IDENTITY: (SCOPE_OPENID, SCOPE_EMAIL, SCOPE_PROFILE),
    CAPABILITY_CHANNEL_READ: (SCOPE_CHANNEL_READ,),
    CAPABILITY_ANALYTICS: (SCOPE_ANALYTICS,),
    CAPABILITY_UPLOAD: (SCOPE_UPLOAD,),
    CAPABILITY_COMMENTS: (SCOPE_COMMENTS,),
    CAPABILITY_REVENUE: (SCOPE_REVENUE,),
}

BASE_CAPABILITIES = (CAPABILITY_IDENTITY, CAPABILITY_CHANNEL_READ)
OPTIONAL_CAPABILITIES = (CAPABILITY_REVENUE,)
KNOWN_CAPABILITIES = tuple(CAPABILITY_SCOPE_MAP)

CAPABILITY_STATUS_ACTIVE = "active"
CAPABILITY_STATUS_SCOPE_REQUIRED = "scope_required"
CAPABILITY_STATUS_API_NOT_ENABLED = "api_not_enabled"
CAPABILITY_STATUS_REAUTH_REQUIRED = "reauth_required"
CAPABILITY_STATUS_UNAVAILABLE = "unavailable"


def normalize_capabilities(values: Optional[Iterable[str]]) -> List[str]:
    """Validates capability names against the whitelist, preserving order."""
    if not values:
        return []
    normalized: List[str] = []
    for raw in values:
        name = str(raw).strip().lower()
        if not name:
            continue
        if name not in CAPABILITY_SCOPE_MAP:
            raise ValueError(f"Bilinmeyen yetenek: {raw}")
        if name not in normalized:
            normalized.append(name)
    return normalized


def capabilities_for_scopes(scopes: Optional[Iterable[str]]) -> List[str]:
    granted = set(scopes or ())
    return [
        capability
        for capability, required in CAPABILITY_SCOPE_MAP.items()
        if required and all(scope in granted for scope in required)
    ]


def has_capability(scopes: Optional[Iterable[str]], capability: str) -> bool:
    if capability not in CAPABILITY_SCOPE_MAP:
        return False
    granted = set(scopes or ())
    return all(scope in granted for scope in CAPABILITY_SCOPE_MAP[capability])


def capabilities_scopes(capabilities: Iterable[str]) -> List[str]:
    scopes: List[str] = []
    for capability in normalize_capabilities(capabilities):
        for scope in CAPABILITY_SCOPE_MAP[capability]:
            if scope not in scopes:
                scopes.append(scope)
    return scopes


def scopes_for_capabilities(
    capabilities: Optional[Iterable[str]], include_base: bool = True
) -> List[str]:
    """Returns the scope union for the requested capabilities.

    The base grant is always included so an incremental authorization can never
    drop the identity/channel-read permissions the connection already relies on.
    """
    requested = list(BASE_CAPABILITIES) if include_base else []
    for capability in normalize_capabilities(capabilities):
        if capability not in requested:
            requested.append(capability)
    return capabilities_scopes(requested)


def missing_capabilities(
    scopes: Optional[Iterable[str]], capabilities: Iterable[str]
) -> List[str]:
    granted = set(capabilities_for_scopes(scopes))
    return [
        capability
        for capability in normalize_capabilities(capabilities)
        if capability not in granted
    ]


def merge_capability_scopes(
    existing_scopes: Optional[Sequence[str]], new_scopes: Optional[Sequence[str]]
) -> List[str]:
    """Union of previously granted and newly granted scopes.

    Used when re-authorizing an existing connection so an unexpected short
    Google response can never silently narrow a working grant.
    """
    merged: List[str] = []
    for scope in list(existing_scopes or []) + list(new_scopes or []):
        if scope and scope not in merged:
            merged.append(scope)
    return merged
