"""Tests for serverless endpoint provider."""

import pytest

from deuscode.endpoints.base import EndpointStatus, EndpointType
from deuscode.endpoints.serverless import (
    ServerlessProvider,
    SERVERLESS_URL,
    _build_create_input,
    _get_tool_call_parser,
    _parse_endpoint,
    get_health,
)


def test_parse_endpoint_valid():
    raw = {"id": "abc123", "name": "deus-qwen", "templateId": "t1",
           "workersMin": 0, "workersMax": 3}
    info = _parse_endpoint(raw)
    assert info.endpoint_id == "abc123"
    assert info.endpoint_type == EndpointType.SERVERLESS
    assert info.display_name == "deus-qwen"
    assert info.status == EndpointStatus.COLD
    assert info.model_id == "deus-qwen"
    assert info.workers_min == 0


def test_parse_endpoint_workers_min_propagated():
    raw = {"id": "ep-1", "name": "deus-llama", "workersMin": 1, "workersMax": 3}
    info = _parse_endpoint(raw)
    assert info.workers_min == 1


def test_get_base_url_format():
    provider = ServerlessProvider()
    url = provider.get_base_url("ep-xyz")
    assert url == SERVERLESS_URL.format(endpoint_id="ep-xyz")
    assert "ep-xyz" in url


@pytest.mark.asyncio
async def test_list_endpoints_raises_on_error(monkeypatch):
    async def _fail(*a, **kw):
        raise RuntimeError("boom")
    monkeypatch.setattr(
        "deuscode.endpoints.serverless._graphql", _fail,
    )
    provider = ServerlessProvider()
    with pytest.raises(RuntimeError, match="boom"):
        await provider.list_endpoints("fake-key")


@pytest.mark.asyncio
async def test_list_endpoints_returns_empty_when_none_exist(monkeypatch):
    async def _empty(*a, **kw):
        return {"data": {"myself": {"serverlessDiscount": 0, "endpoints": []}}}
    monkeypatch.setattr("deuscode.endpoints.serverless._graphql", _empty)
    provider = ServerlessProvider()
    assert await provider.list_endpoints("fake-key") == []


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
async def test_get_status_cold_when_all_zero(monkeypatch):
    class FakeResp:
        status_code = 200
        def json(self):
            return {"workers": {"running": 0, "ready": 0, "idle": 0, "initializing": 0}}

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
async def test_get_status_ready_when_idle(monkeypatch):
    class FakeResp:
        status_code = 200
        def json(self):
            return {"workers": {"running": 0, "ready": 0, "idle": 2}}

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
async def test_get_status_ready_when_ready(monkeypatch):
    class FakeResp:
        status_code = 200
        def json(self):
            return {"workers": {"running": 0, "ready": 3, "idle": 0}}

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
async def test_get_status_cold_when_only_initializing(monkeypatch):
    """Initializing workers are not yet warm — still show cold start warning."""
    class FakeResp:
        status_code = 200
        def json(self):
            return {"workers": {"running": 0, "ready": 0, "idle": 0, "initializing": 1}}

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


def test_tool_call_parser_qwen():
    assert _get_tool_call_parser("Qwen/Qwen2.5-Coder-32B") == "hermes"


def test_tool_call_parser_llama():
    assert _get_tool_call_parser("meta-llama/Llama-3.1-70B") == "llama3_json"


def test_tool_call_parser_default():
    assert _get_tool_call_parser("unknown/model") == "hermes"


def test_build_create_input_has_tool_choice():
    result = _build_create_input("Qwen/Qwen2.5-Coder-7B", "AMPERE_80")
    env = {e["key"]: e["value"] for e in result["env"]}
    assert env["ENABLE_AUTO_TOOL_CHOICE"] == "true"
    assert "TOOL_CALL_PARSER" in env


def test_build_create_input_uses_template_id():
    result = _build_create_input("some/model", "AMPERE_80")
    assert result["templateId"] == "d46z8rtpd0"
    assert "imageName" not in result


def test_build_create_input_workers_min_is_one():
    result = _build_create_input("some/model", "AMPERE_80")
    assert result["workersMin"] == 1


def test_build_create_input_with_quantization():
    result = _build_create_input("some/model", "ADA_80", quantization="awq")
    env = {e["key"]: e["value"] for e in result["env"]}
    assert env["QUANTIZATION"] == "awq"


def test_build_create_input_with_hf_token():
    result = _build_create_input("meta-llama/Llama-3.1-8B", "ADA_80", hf_token="hf_abc")
    env = {e["key"]: e["value"] for e in result["env"]}
    assert env["HF_TOKEN"] == "hf_abc"


def test_build_create_input_no_quantization_by_default():
    result = _build_create_input("some/model", "ADA_80")
    keys = [e["key"] for e in result["env"]]
    assert "QUANTIZATION" not in keys
    assert "HF_TOKEN" not in keys


@pytest.mark.asyncio
async def test_get_health_returns_empty_on_error(monkeypatch):
    monkeypatch.setattr(
        "deuscode.endpoints.serverless.httpx.AsyncClient",
        lambda **kw: (_ for _ in ()).throw(Exception("net error")),
    )
    assert await get_health("key", "ep-1") == {}


@pytest.mark.asyncio
async def test_get_health_returns_empty_on_non_200(monkeypatch):
    class FakeResp:
        status_code = 404

    class FakeClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def get(self, *a, **kw): return FakeResp()

    monkeypatch.setattr(
        "deuscode.endpoints.serverless.httpx.AsyncClient", lambda **kw: FakeClient(),
    )
    assert await get_health("key", "ep-1") == {}


@pytest.mark.asyncio
async def test_get_health_parses_worker_counts(monkeypatch):
    payload = {
        "workers": {"idle": 0, "initializing": 1, "ready": 0, "running": 0, "throttled": 0},
        "jobs": {"completed": 0, "failed": 0, "inProgress": 0, "inQueue": 0, "retried": 0},
    }

    class FakeResp:
        status_code = 200
        def json(self): return payload

    class FakeClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def get(self, *a, **kw): return FakeResp()

    monkeypatch.setattr(
        "deuscode.endpoints.serverless.httpx.AsyncClient", lambda **kw: FakeClient(),
    )
    result = await get_health("key", "ep-1")
    assert result["workers"]["initializing"] == 1
    assert "jobs" in result
