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
    async with httpx.AsyncClient(timeout=30.0) as client:
        while elapsed < _TIMEOUT_SECONDS:
            r = await client.post(_API_URL, headers=_headers(api_key), json={"query": query, "variables": {"podId": pod_id}})
            r.raise_for_status()
            body = r.json()
            if body.get("errors"):
                raise RuntimeError(body["errors"][0]["message"])
            pod = body["data"]["pod"]
            if on_poll:
                on_poll(pod, elapsed)
            if pod["desiredStatus"] == "RUNNING" and pod.get("runtime"):
                return _extract_endpoint(pod)
            await asyncio.sleep(_POLL_INTERVAL)
            elapsed += _POLL_INTERVAL
    raise TimeoutError(f"Pod {pod_id} did not become ready within {_TIMEOUT_SECONDS}s")


def _extract_endpoint(pod: dict) -> str:
    pod_id = pod.get("id", "")
    for p in (pod.get("runtime") or {}).get("ports") or []:
        if p.get("privatePort") != 8000:
            continue
        if p.get("isIpPublic"):
            return f"https://{p['ip']}:{p['publicPort']}"
        return f"https://{pod_id}-8000.proxy.runpod.net"
    return ""
