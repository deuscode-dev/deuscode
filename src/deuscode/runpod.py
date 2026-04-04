import asyncio

import httpx

_API_URL = "https://api.runpod.io/graphql"
_POLL_INTERVAL = 10
_IDLE_TIMEOUT = 300  # seconds without any status change before giving up


def _headers(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


async def get_gpu_types(api_key: str) -> list[dict]:
    query = """
    {
      gpuTypes {
        id
        displayName
        memoryInGb
        securePrice
        communityPrice
        lowestPrice(input: { gpuCount: 1 }) {
          minimumBidPrice
          uninterruptablePrice
        }
        secureCloud
        communityCloud
      }
    }
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(_API_URL, headers=_headers(api_key), json={"query": query})
        r.raise_for_status()
        gpus = r.json()["data"]["gpuTypes"]
    return [
        g for g in gpus
        if g.get("lowestPrice") and g["lowestPrice"].get("uninterruptablePrice") is not None
    ]


async def start_pod(api_key: str, gpu_type_id: str, model_id: str, cloud_type: str = "ALL") -> dict:
    mutation = """
    mutation($input: PodFindAndDeployOnDemandInput!) {
      podFindAndDeployOnDemand(input: $input) {
        id
        desiredStatus
        machine { podHostId }
      }
    }
    """
    variables = {
        "input": {
            "name": "deus-vllm",
            "gpuTypeId": gpu_type_id,
            "gpuCount": 1,
            "cloudType": cloud_type,
            "supportPublicIp": True,
            "startSsh": True,
            "imageName": "vllm/vllm-openai:latest",
            "containerDiskInGb": 100,
            "volumeInGb": 0,
            "volumeMountPath": "/runpod-volume",
            "dockerArgs": "",
            "ports": "8000/http,22/tcp",
            "minVcpuCount": 1,
            "minMemoryInGb": 1,
            "env": [
                {"key": "MODEL_ID", "value": model_id},
                {"key": "HUGGING_FACE_HUB_TOKEN", "value": ""},
            ],
        }
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(_API_URL, headers=_headers(api_key), json={"query": mutation, "variables": variables})
        r.raise_for_status()
        body = r.json()
        if "errors" in body:
            msg = body["errors"][0].get("message", "Unknown RunPod error")
            raise RuntimeError(msg)
        if not body.get("data"):
            raise RuntimeError(f"RunPod returned unexpected response: {body}")
        return body["data"]["podFindAndDeployOnDemand"]


async def stop_pod(api_key: str, pod_id: str) -> bool:
    mutation = """
    mutation($input: PodTerminateInput!) {
      podTerminate(input: $input)
    }
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(_API_URL, headers=_headers(api_key), json={"query": mutation, "variables": {"input": {"podId": pod_id}}})
        r.raise_for_status()
        return True


async def wait_for_ready(api_key: str, pod_id: str, on_poll=None) -> str:
    query = """
    query($podId: String!) {
      pod(input: { podId: $podId }) {
        id
        desiredStatus
        runtime { ports { ip isIpPublic privatePort publicPort type } }
      }
    }
    """
    elapsed = 0
    idle = 0
    last_state: tuple | None = None
    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            r = await client.post(_API_URL, headers=_headers(api_key), json={"query": query, "variables": {"podId": pod_id}})
            r.raise_for_status()
            body = r.json()
            if body.get("errors"):
                raise RuntimeError(body["errors"][0]["message"])
            pod = body["data"]["pod"]
            state = (pod.get("desiredStatus"), bool(pod.get("runtime")))
            if state != last_state:
                last_state = state
                idle = 0
            else:
                idle += _POLL_INTERVAL
            if on_poll:
                on_poll(pod, elapsed)
            if pod.get("desiredStatus") == "RUNNING" and pod.get("runtime"):
                return _extract_endpoint(pod)
            if idle >= _IDLE_TIMEOUT:
                raise TimeoutError(
                    f"Pod {pod_id} stalled — no status change for {_IDLE_TIMEOUT}s "
                    f"(last: {last_state})"
                )
            await asyncio.sleep(_POLL_INTERVAL)
            elapsed += _POLL_INTERVAL


async def wait_for_health(endpoint: str, on_poll=None) -> None:
    """Poll GET /health until vLLM responds 200, timing out only if status stops changing."""
    url = f"{endpoint.rstrip('/')}/health"
    elapsed = 0
    idle = 0
    last_status: int | None = None
    async with httpx.AsyncClient(timeout=10.0) as client:
        while True:
            try:
                r = await client.get(url)
                status = r.status_code
            except Exception:
                status = -1
            if status == 200:
                return
            if status != last_status:
                last_status = status
                idle = 0
            else:
                idle += _POLL_INTERVAL
            if on_poll:
                on_poll(elapsed)
            if idle >= _IDLE_TIMEOUT:
                raise TimeoutError(
                    f"vLLM stalled at {url} — status {last_status} unchanged for {_IDLE_TIMEOUT}s"
                )
            await asyncio.sleep(_POLL_INTERVAL)
            elapsed += _POLL_INTERVAL


def _extract_endpoint(pod: dict) -> str:
    pod_id = pod.get("id", "")
    for p in (pod.get("runtime") or {}).get("ports") or []:
        if p.get("privatePort") != 8000:
            continue
        if p.get("isIpPublic"):
            return f"https://{p['ip']}:{p['publicPort']}"
        return f"https://{pod_id}-8000.proxy.runpod.net"
    return ""
