from typing import List

from tezlify_studio.application.ports.creator_gateway_port import CreatorGatewayPort
from tezlify_studio.domain.value_objects.creator_models import PlatformDescriptor


class ListPlatformsUseCase:
    def __init__(self, gateway: CreatorGatewayPort):
        self.gateway = gateway

    def execute(self) -> List[PlatformDescriptor]:
        return self.gateway.list_platforms()
