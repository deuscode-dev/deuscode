"""Tests for serverless endpoint provider."""

import pytest

from deuscode.endpoints.base import EndpointStatus, EndpointType
from deuscode.endpoints.serverless import (
    ServerlessProvider,
    SERVERLESS_URL,
    _parse_endpoint,
)


def test_parse_endpoint_valid():
    raw = {"id": "abc123", "name": "deus-qwen", "templateId": "t1",
           "workersMin": 0, "workersMax": 3}
    info = _parse_endpoint(raw)
    assert info.endpoint_id == "abc123"
    assert info.endpoint_type == EndpointType.SERVERLESS
    assert info.display_name == "deus-qwen"
    assert info.status == EndpointStatus.COLD


def test_get_base_url_format():
    provider = ServerlessProvider()
    url = provider.get_base_url("ep-xyz")
    assert url == SERVERLESS_URL.format(endpoint_id="ep-xyz")
    assert "ep-xyz" in url


@pytest.mark.asyncio
async def test_list_endpoints_returns_empty_on_error(monkeypatch):
    async def _fail(*a, **kw):
        raise RuntimeError("boom")
    monkeypatch.setattr(
        "deuscode.endpoints.serverless._graphql", _fail,
    )
    provider = ServerlessProvider()
    result = await provider.list_endpoints("fake-key")
    assert result == []


@pytest.mark.asyncio
async def test_get_status_ready(monkeypatch):
    class FakeResp:
        status_code = 200
        def json(self):
            return {"workers": {"running": 1, "idle": 0}}

    class FakeClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def get(self, *a, **kw): return FakeResp()

    monkeypatch.setattr(
        "deuscode.endpoints.serverless.httpx.AsyncClient",
        lambda **kw: FakeClient(),
    )
    provider = ServerlessProvider()
    assert await provider.get_status("k", "ep") == EndpointStatus.READY


@pytest.mark.asyncio
async def test_get_status_cold(monkeypatch):
    class FakeResp:
        status_code = 200
        def json(self):
            return {"workers": {"running": 0, "idle": 2}}

    class FakeClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def get(self, *a, **kw): return FakeResp()

    monkeypatch.setattr(
        "deuscode.endpoints.serverless.httpx.AsyncClient",
        lambda **kw: FakeClient(),
    )
    provider = ServerlessProvider()
    assert await provider.get_status("k", "ep") == EndpointStatus.COLD


@pytest.mark.asyncio
async def test_get_status_error_on_exception(monkeypatch):
    monkeypatch.setattr(
        "deuscode.endpoints.serverless.httpx.AsyncClient",
        lambda **kw: (_ for _ in ()).throw(Exception("fail")),
    )
    provider = ServerlessProvider()
    assert await provider.get_status("k", "ep") == EndpointStatus.ERROR
