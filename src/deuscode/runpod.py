import asyncio

import httpx

_API_URL = "https://api.runpod.io/graphql"
_POLL_INTERVAL = 10
_TIMEOUT_SECONDS = 300


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
    return [g for g in gpus if g.get("secureCloud") or g.get("communityCloud")]


async def start_pod(api_key: str, gpu_type_id: str, model_id: str, cloud_type: str = "COMMUNITY") -> dict:
    mutation = """
    mutation($input: PodFindAndDeployOnDemandInput!) {
      podFindAndDeployOnDemand(input: $input) {
        id
        desiredStatus
      }
    }
    """
    variables = {
        "input": {
            "gpuTypeId": gpu_type_id,
            "cloudType": cloud_type,
            "imageName": "vllm/vllm-openai:latest",
            "containerDiskInGb": 50,
            "volumeInGb": 50,
            "ports": "8000/http",
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
        print(f"[debug] start_pod response: {body}")
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


async def wait_for_ready(api_key: str, pod_id: str) -> str:
    query = """
    query($podId: String!) {
      pod(input: { podId: $podId }) {
        desiredStatus
        runtime { ports { ip port isIpPublic } }
      }
    }
    """
    elapsed = 0
    async with httpx.AsyncClient(timeout=30.0) as client:
        while elapsed < _TIMEOUT_SECONDS:
            r = await client.post(_API_URL, headers=_headers(api_key), json={"query": query, "variables": {"podId": pod_id}})
            r.raise_for_status()
            pod = r.json()["data"]["pod"]
            if pod["desiredStatus"] == "RUNNING":
                return _extract_endpoint(pod)
            await asyncio.sleep(_POLL_INTERVAL)
            elapsed += _POLL_INTERVAL
    raise TimeoutError(f"Pod {pod_id} did not become ready within {_TIMEOUT_SECONDS}s")


def _extract_endpoint(pod: dict) -> str:
    for port_info in (pod.get("runtime") or {}).get("ports") or []:
        if port_info.get("isIpPublic") and port_info.get("port") == 8000:
            return f"https://{port_info['ip']}:{port_info['port']}"
    return ""
