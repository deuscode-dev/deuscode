from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable


class EndpointType(str, Enum):
    SERVERLESS = "serverless"
    POD = "pod"


class EndpointStatus(str, Enum):
    READY = "ready"
    COLD = "cold"
    STARTING = "starting"
    ERROR = "error"


@dataclass
class EndpointInfo:
    endpoint_id: str
    endpoint_type: EndpointType
    model_id: str
    status: EndpointStatus
    base_url: str
    display_name: str = ""
    workers_min: int = 0


@runtime_checkable
class EndpointProvider(Protocol):
    async def list_endpoints(self, api_key: str) -> list[EndpointInfo]: ...
    async def create_endpoint(self, api_key: str, model_id: str) -> EndpointInfo: ...
    async def get_status(self, api_key: str, endpoint_id: str) -> EndpointStatus: ...
    def get_base_url(self, endpoint_id: str) -> str: ...
