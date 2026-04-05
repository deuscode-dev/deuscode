from deuscode.endpoints.base import EndpointInfo, EndpointStatus, EndpointType

_LIST_PODS_QUERY = """
{
  myself {
    pods {
      id
      name
      desiredStatus
      runtime { ports { ip isIpPublic privatePort publicPort type } }
    }
  }
}
"""


class PodProvider:

    async def list_endpoints(self, api_key: str) -> list[EndpointInfo]:
        try:
            from deuscode.endpoints.serverless import _graphql
            data = await _graphql(api_key, _LIST_PODS_QUERY)
            pods = data["data"]["myself"]["pods"]
            return [
                _parse_pod(p) for p in pods
                if p.get("desiredStatus") == "RUNNING"
            ]
        except Exception:
            return []

    async def create_endpoint(self, api_key: str, model_id: str) -> EndpointInfo:
        raise NotImplementedError(
            "Pod creation requires GPU selection. Use: deus setup --runpod"
        )

    async def get_status(self, api_key: str, endpoint_id: str) -> EndpointStatus:
        return EndpointStatus.READY

    def get_base_url(self, endpoint_id: str) -> str:
        return f"https://{endpoint_id}-8000.proxy.runpod.net/v1"


def _parse_pod(raw: dict) -> EndpointInfo:
    ports = (raw.get("runtime") or {}).get("ports") or []
    port_8000 = next(
        (p for p in ports if p.get("privatePort") == 8000), None,
    )
    base_url = ""
    if port_8000 and port_8000.get("ip"):
        ip = port_8000["ip"]
        pub = port_8000.get("publicPort", 8000)
        base_url = f"https://{ip}:{pub}/v1"
    return EndpointInfo(
        endpoint_id=raw["id"],
        endpoint_type=EndpointType.POD,
        model_id=raw.get("name", "unknown"),
        status=EndpointStatus.READY,
        base_url=base_url,
        display_name=raw.get("name", raw["id"]),
    )
