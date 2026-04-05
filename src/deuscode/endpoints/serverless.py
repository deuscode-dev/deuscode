import httpx

from deuscode.endpoints.base import EndpointInfo, EndpointStatus, EndpointType

RUNPOD_API_BASE = "https://api.runpod.io/graphql"
SERVERLESS_URL = "https://api.runpod.ai/v2/{endpoint_id}/openai/v1"

_LIST_QUERY = """
{
  myself {
    serverlessDiscount
    endpoints { id name templateId workersMin workersMax }
  }
}
"""

_CREATE_MUTATION = """
mutation CreateEndpoint($input: EndpointInput!) {
  saveEndpoint(input: $input) { id name }
}
"""


class ServerlessProvider:

    async def list_endpoints(self, api_key: str) -> list[EndpointInfo]:
        try:
            data = await _graphql(api_key, _LIST_QUERY)
            endpoints = data["data"]["myself"]["endpoints"]
            return [_parse_endpoint(e) for e in endpoints]
        except Exception:
            return []

    async def create_endpoint(self, api_key: str, model_id: str) -> EndpointInfo:
        variables = {"input": _build_create_input(model_id)}
        data = await _graphql(api_key, _CREATE_MUTATION, variables)
        ep = data["data"]["saveEndpoint"]
        return EndpointInfo(
            endpoint_id=ep["id"],
            endpoint_type=EndpointType.SERVERLESS,
            model_id=model_id,
            status=EndpointStatus.COLD,
            base_url=self.get_base_url(ep["id"]),
            display_name=ep["name"],
        )

    async def get_status(self, api_key: str, endpoint_id: str) -> EndpointStatus:
        url = f"https://api.runpod.ai/v2/{endpoint_id}/health"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(url, headers=_auth_header(api_key))
                if r.status_code != 200:
                    return EndpointStatus.COLD
                workers = r.json().get("workers", {})
                if workers.get("running", 0) > 0:
                    return EndpointStatus.READY
                return EndpointStatus.COLD
        except Exception:
            return EndpointStatus.ERROR

    def get_base_url(self, endpoint_id: str) -> str:
        return SERVERLESS_URL.format(endpoint_id=endpoint_id)


def _build_create_input(model_id: str) -> dict:
    return {
        "name": f"deus-{model_id.split('/')[-1].lower()[:20]}",
        "templateId": "runpod-vllm",
        "workersMin": 0,
        "workersMax": 3,
        "idleTimeout": 5,
        "env": [
            {"key": "MODEL_NAME", "value": model_id},
            {"key": "MAX_MODEL_LEN", "value": "8192"},
            {"key": "DTYPE", "value": "half"},
        ],
    }


def _parse_endpoint(raw: dict) -> EndpointInfo:
    return EndpointInfo(
        endpoint_id=raw["id"],
        endpoint_type=EndpointType.SERVERLESS,
        model_id=raw.get("name", "unknown"),
        status=EndpointStatus.COLD,
        base_url=SERVERLESS_URL.format(endpoint_id=raw["id"]),
        display_name=raw.get("name", raw["id"]),
    )


def _auth_header(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}"}


async def _graphql(api_key: str, query: str, variables: dict | None = None) -> dict:
    """Execute RunPod GraphQL query. Raises on error."""
    payload: dict = {"query": query}
    if variables:
        payload["variables"] = variables
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            RUNPOD_API_BASE, headers=_auth_header(api_key), json=payload,
        )
        r.raise_for_status()
        body = r.json()
        if body.get("errors"):
            raise RuntimeError(body["errors"][0].get("message", "Unknown"))
        return body
