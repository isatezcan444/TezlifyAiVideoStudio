from abc import ABC, abstractmethod
from typing import List

from tezlify_studio.domain.value_objects.creator_models import PlatformDescriptor


class PlatformCatalogPort(ABC):
    @abstractmethod
    def list_platforms(self) -> List[PlatformDescriptor]:
        """Returns every platform known to the studio and whether it is implemented."""
        pass
