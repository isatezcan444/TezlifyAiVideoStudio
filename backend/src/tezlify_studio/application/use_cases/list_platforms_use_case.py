from typing import List

from tezlify_studio.application.ports.platform_catalog_port import PlatformCatalogPort
from tezlify_studio.domain.value_objects.creator_models import PlatformDescriptor


class ListPlatformsUseCase:
    def __init__(self, catalog: PlatformCatalogPort):
        self.catalog = catalog

    def execute(self) -> List[PlatformDescriptor]:
        return self.catalog.list_platforms()
