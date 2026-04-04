import json
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from deuscode import runpod


def _mock_response(data: dict, status: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = data
    resp.raise_for_status = MagicMock()
    return resp


@pytest.mark.asyncio
async def test_stop_pod_sends_correct_id():
    captured = {}

    async def fake_post(url, **kwargs):
        captured["body"] = kwargs.get("json", {})
        return _mock_response({"data": {"podTerminate": None}})

    with patch("deuscode.runpod.httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.post.side_effect = fake_post
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        await runpod.stop_pod("key123", "pod-abc")

    variables = captured["body"].get("variables", {})
    assert variables.get("input", {}).get("podId") == "pod-abc"


@pytest.mark.asyncio
async def test_wait_for_ready_timeout():
    async def fake_post(url, **kwargs):
        return _mock_response({
            "data": {"pod": {"desiredStatus": "STARTING", "runtime": None}}
        })

    with patch("deuscode.runpod.httpx.AsyncClient") as MockClient, \
         patch("deuscode.runpod._TIMEOUT_SECONDS", 1), \
         patch("deuscode.runpod._POLL_INTERVAL", 1), \
         patch("asyncio.sleep", new_callable=AsyncMock):
        instance = AsyncMock()
        instance.post.side_effect = fake_post
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        with pytest.raises(TimeoutError):
            await runpod.wait_for_ready("key123", "pod-xyz")
