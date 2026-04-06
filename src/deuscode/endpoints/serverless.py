import httpx

from deuscode.endpoints.base import EndpointInfo, EndpointStatus, EndpointType

RUNPOD_API_BASE = "https://api.runpod.io/graphql"
SERVERLESS_URL = "https://api.runpod.ai/v2/{endpoint_id}/openai/v1"

TOOL_CALL_PARSERS = {
    "qwen": "hermes",
    "llama": "llama3_json",
    "mistral": "mistral",
    "deepseek": "hermes",
    "default": "hermes",
}

_LIST_QUERY = """
{
  myself {
    endpoints { id name templateId workersMin workersMax }
  }
}
"""

_CREATE_MUTATION = """
mutation CreateEndpoint($input: EndpointInput!) {
  saveEndpoint(input: $input) { id name }
}
"""


def _get_tool_call_parser(model_id: str) -> str:
    model_lower = model_id.lower()
    for family, parser in TOOL_CALL_PARSERS.items():
        if family == "default":
            continue
        if family in model_lower:
            return parser
    return TOOL_CALL_PARSERS["default"]


class ServerlessProvider:

    async def list_endpoints(self, api_key: str) -> list[EndpointInfo]:
        """Raises on API/network error. Returns [] when no endpoints exist."""
        data = await _graphql(api_key, _LIST_QUERY)
        endpoints = data["data"]["myself"]["endpoints"]
        return [_parse_endpoint(e) for e in endpoints]

    async def create_endpoint(
        self,
        api_key: str,
        model_id: str,
        gpu_ids: str = "",
        quantization: str | None = None,
        hf_token: str = "",
    ) -> EndpointInfo:
        variables = {"input": _build_create_input(
            model_id, gpu_ids, quantization, hf_token,
        )}
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
                warm = (
                    workers.get("running", 0)
                    + workers.get("ready", 0)
                    + workers.get("idle", 0)
                )
                return EndpointStatus.READY if warm > 0 else EndpointStatus.COLD
        except Exception:
            return EndpointStatus.ERROR

    def get_base_url(self, endpoint_id: str) -> str:
        return SERVERLESS_URL.format(endpoint_id=endpoint_id)


async def get_health(api_key: str, endpoint_id: str) -> dict:
    """Return full RunPod health dict. Never raises — returns {} on any error."""
    url = f"https://api.runpod.ai/v2/{endpoint_id}/health"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(url, headers=_auth_header(api_key))
            if r.status_code == 200:
                return r.json()
        return {}
    except Exception:
        return {}


def _build_create_input(
    model_id: str,
    gpu_ids: str,
    quantization: str | None = None,
    hf_token: str = "",
) -> dict:
    env = [
        {"key": "MODEL_NAME", "value": model_id},
        {"key": "MAX_MODEL_LEN", "value": "8192"},
        {"key": "DTYPE", "value": "half"},
        {"key": "ENABLE_AUTO_TOOL_CHOICE", "value": "true"},
        {"key": "TOOL_CALL_PARSER", "value": _get_tool_call_parser(model_id)},
        {"key": "GPU_MEMORY_UTILIZATION", "value": "0.90"},
    ]
    if quantization:
        env.append({"key": "QUANTIZATION", "value": quantization})
    if hf_token:
        env.append({"key": "HF_TOKEN", "value": hf_token})
    return {
        "name": f"deus-{model_id.split('/')[-1].lower()[:20]}",
        "templateId": "d46z8rtpd0",  # vLLM v2.14.0 serverless template
        "gpuIds": gpu_ids,
        "workersMin": 1,
        "workersMax": 3,
        "idleTimeout": 5,
        "env": env,
    }


def _parse_endpoint(raw: dict) -> EndpointInfo:
    env = {e["key"]: e["value"] for e in raw.get("env") or []}
    model_id = env.get("MODEL_NAME") or raw.get("name", "unknown")
    return EndpointInfo(
        endpoint_id=raw["id"],
        endpoint_type=EndpointType.SERVERLESS,
        model_id=model_id,
        status=EndpointStatus.COLD,
        base_url=SERVERLESS_URL.format(endpoint_id=raw["id"]),
        display_name=raw.get("name", raw["id"]),
        workers_min=raw.get("workersMin", 0),
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
