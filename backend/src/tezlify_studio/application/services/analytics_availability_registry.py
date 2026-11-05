"""In-memory record of the last observed YouTube Analytics API state.

A missing OAuth scope and a disabled Google Cloud API both surface as HTTP 403
from Google, but they need different user actions. The resolver keeps the two
distinct by remembering whether Analytics most recently failed because the API
is not enabled for the connection's project.
"""

import threading
from typing import Dict, Optional

API_NOT_ENABLED = "api_not_enabled"


class AnalyticsAvailabilityRegistry:
    def __init__(self) -> None:
        self._states: Dict[str, str] = {}
        self._lock = threading.Lock()

    def mark(self, connection_id: str, reason: Optional[str]) -> None:
        if not connection_id:
            return
        with self._lock:
            if reason == API_NOT_ENABLED:
                self._states[connection_id] = API_NOT_ENABLED
            else:
                self._states.pop(connection_id, None)

    def get(self, connection_id: str) -> Optional[str]:
        with self._lock:
            return self._states.get(connection_id)

    def clear(self, connection_id: Optional[str] = None) -> None:
        with self._lock:
            if connection_id is None:
                self._states.clear()
            else:
                self._states.pop(connection_id, None)


analytics_availability_registry = AnalyticsAvailabilityRegistry()
