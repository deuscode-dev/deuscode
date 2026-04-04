from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from deuscode.model_manager import list_downloaded_models
from deuscode.models import get_models_by_size, MODELS


# ── list_downloaded_models ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_downloaded_models_parses_response():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "data": [
            {"id": "Qwen/Qwen2.5-Coder-7B-Instruct"},
            {"id": "meta-llama/Llama-3.2-1B-Instruct"},
        ]
    }

    with patch("deuscode.model_manager.httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.get = AsyncMock(return_value=mock_resp)
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        result = await list_downloaded_models("https://pod-8000.proxy.runpod.net/v1")

    assert result == [
        "Qwen/Qwen2.5-Coder-7B-Instruct",
        "meta-llama/Llama-3.2-1B-Instruct",
    ]


@pytest.mark.asyncio
async def test_list_downloaded_models_returns_empty_on_error():
    with patch("deuscode.model_manager.httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.get = AsyncMock(side_effect=Exception("connection refused"))
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        result = await list_downloaded_models("https://pod-8000.proxy.runpod.net/v1")

    assert result == []


# ── get_models_by_size ────────────────────────────────────────────────────────

def test_get_models_by_size_small():
    result = get_models_by_size("small")
    assert len(result) > 0
    assert all(m["vram_gb"] <= 16 for m in result)


def test_get_models_by_size_all():
    result = get_models_by_size("all")
    assert result == MODELS
