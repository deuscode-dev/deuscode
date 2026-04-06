"""RunPod native async job API client for serverless endpoints."""

import asyncio
import time

import httpx

RUNPOD_RUN_URL = "https://api.runpod.ai/v2/{endpoint_id}/run"
RUNPOD_STATUS_URL = "https://api.runpod.ai/v2/{endpoint_id}/status/{job_id}"


async def submit_job(
    api_key: str,
    endpoint_id: str,
    messages: list[dict],
    model: str,
    max_tokens: int = 8192,
) -> str:
    """Submit job to RunPod native API. Returns job_id.

    Tool calling via job API requires ENABLE_AUTO_TOOL_CHOICE env var on the endpoint.
    Use XML fallback instead (caller's responsibility).
    """
    openai_input: dict = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
    }
    payload = {"input": {"openai_route": "/v1/chat/completions", "openai_input": openai_input}}
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            RUNPOD_RUN_URL.format(endpoint_id=endpoint_id),
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
        )
        r.raise_for_status()
        return r.json()["id"]


async def poll_job(
    api_key: str,
    endpoint_id: str,
    job_id: str,
    on_status_update: callable,
    poll_interval: float = 2.0,
    max_wait: int = 900,
) -> dict:
    """
    Poll job until COMPLETED or FAILED.
    Calls on_status_update(status, elapsed) on each poll.
    Returns full OpenAI-compatible output dict on success.
    Raises RuntimeError on failure or timeout.
    """
    start = time.monotonic()
    async with httpx.AsyncClient(timeout=10.0) as client:
        while True:
            elapsed = int(time.monotonic() - start)
            if elapsed > max_wait:
                raise RuntimeError(f"Job {job_id} did not complete after {max_wait}s")
            r = await client.get(
                RUNPOD_STATUS_URL.format(endpoint_id=endpoint_id, job_id=job_id),
                headers={"Authorization": f"Bearer {api_key}"},
            )
            r.raise_for_status()
            data = r.json()
            status = data.get("status", "UNKNOWN")
            on_status_update(status, elapsed)
            if status == "COMPLETED":
                output = data.get("output", [{}])
                # RunPod wraps the OpenAI response in a list; guard empty list
                if isinstance(output, list):
                    return output[0] if output else {}
                return output
            if status == "FAILED":
                raise RuntimeError(f"Job failed: {data.get('error', 'Unknown error')}")
            await asyncio.sleep(poll_interval)


def _extract_text(output: dict) -> str:
    """Extract assistant text from vLLM OpenAI-compatible output."""
    try:
        return output["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return str(output)
