from enum import Enum


class ConnectionStatus(str, Enum):
    ACTIVE = "active"
    REAUTH_REQUIRED = "reauth_required"
    DISCONNECTED = "disconnected"
    ERROR = "error"
