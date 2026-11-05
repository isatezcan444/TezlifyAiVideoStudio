from abc import ABC, abstractmethod
from typing import List, Optional

from tezlify_studio.domain.value_objects.creator_models import AnalyticsResult, DateRange


class AnalyticsPort(ABC):
    @abstractmethod
    def query(
        self,
        date_range: DateRange,
        metrics: Optional[List[str]] = None,
        dimensions: Optional[List[str]] = None,
        include_revenue: bool = False,
    ) -> AnalyticsResult:
        pass
