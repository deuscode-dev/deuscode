"""Tests for RunPod native job API client."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from deuscode.endpoints.job_client import _extract_text, poll_job, submit_job


def test_extract_text_valid():
    output = {"choices": [{"message": {"content": "Hello!"}}]}
    assert _extract_text(output) == "Hello!"


def test_extract_text_invalid():
    output = {"unexpected": "garbage"}
    result = _extract_text(output)
    assert isinstance(result, str)
    assert "unexpected" in result  # str(output) contains the key


@pytest.mark.asyncio
async def test_poll_job_completed(monkeypatch):
    output = {"choices": [{"message": {"role": "assistant", "content": "Done"}}]}
    responses = [
        {"status": "IN_QUEUE"},
        {"status": "IN_PROGRESS"},
        {"status": "COMPLETED", "output": [output]},  # RunPod wraps in a list
    ]
    idx = {"i": 0}

    class FakeResp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            r = responses[idx["i"]]
            idx["i"] += 1
            return r

    class FakeClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def get(self, *a, **kw): return FakeResp()

    monkeypatch.setattr("deuscode.endpoints.job_client.httpx.AsyncClient", lambda **kw: FakeClient())
    monkeypatch.setattr("deuscode.endpoints.job_client.asyncio.sleep", AsyncMock())

    updates = []
    result = await poll_job("key", "ep", "job-1", lambda s, e: updates.append(s), poll_interval=0)
    assert result == output
    assert "COMPLETED" in updates


@pytest.mark.asyncio
async def test_poll_job_failed(monkeypatch):
    class FakeResp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return {"status": "FAILED", "error": "OOM"}

    class FakeClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def get(self, *a, **kw): return FakeResp()

    monkeypatch.setattr("deuscode.endpoints.job_client.httpx.AsyncClient", lambda **kw: FakeClient())
    with pytest.raises(RuntimeError, match="Job failed: OOM"):
        await poll_job("key", "ep", "job-2", lambda s, e: None, poll_interval=0)


@pytest.mark.asyncio
async def test_poll_job_unwraps_list_output(monkeypatch):
    """RunPod wraps the OpenAI response in a list — poll_job must unwrap it."""
    inner = {"choices": [{"message": {"role": "assistant", "content": "Hi"}}]}
    responses = [{"status": "COMPLETED", "output": [inner]}]
    idx = {"i": 0}

    class FakeResp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            r = responses[idx["i"]]
            idx["i"] = min(idx["i"] + 1, len(responses) - 1)
            return r

    class FakeClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def get(self, *a, **kw): return FakeResp()

    monkeypatch.setattr("deuscode.endpoints.job_client.httpx.AsyncClient", lambda **kw: FakeClient())
    result = await poll_job("key", "ep", "job-x", lambda s, e: None, poll_interval=0)
    assert result == inner
    assert "choices" in result  # dict, not list


@pytest.mark.asyncio
async def test_submit_job_posts_correct_payload(monkeypatch):
    captured = {}

    class FakeResp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return {"id": "job-abc"}

    class FakeClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def post(self, url, headers=None, json=None):
            captured["url"] = url
            captured["json"] = json
            return FakeResp()

    monkeypatch.setattr("deuscode.endpoints.job_client.httpx.AsyncClient", lambda **kw: FakeClient())
    messages = [{"role": "user", "content": "hello"}]
    job_id = await submit_job("key", "ep-1", messages, "my-model", max_tokens=100)
    assert job_id == "job-abc"
    assert "ep-1" in captured["url"]
    payload = captured["json"]
    openai_input = payload["input"]["openai_input"]
    assert openai_input["model"] == "my-model"
    assert openai_input["max_tokens"] == 100
    assert openai_input["messages"] == messages
    assert "tools" not in openai_input  # no native tool calling via job API


@pytest.mark.asyncio
async def test_poll_job_timeout(monkeypatch):
    class FakeResp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return {"status": "IN_QUEUE"}

    class FakeClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def get(self, *a, **kw): return FakeResp()

    monkeypatch.setattr("deuscode.endpoints.job_client.httpx.AsyncClient", lambda **kw: FakeClient())
    monkeypatch.setattr("deuscode.endpoints.job_client.asyncio.sleep", AsyncMock())
    with pytest.raises(RuntimeError, match="did not complete"):
        await poll_job("key", "ep", "job-3", lambda s, e: None, poll_interval=0, max_wait=0)
