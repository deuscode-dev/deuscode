"""Tests for agent.py — pure helper functions."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from deuscode.agent import (
    _strip_thinking,
    _clean_response,
    _parse_xml_tools,
    _normalize_args,
    _build_system_prompt,
    _request_with_cold_start_handling,
    _cold_start_timeout,
    _call_serverless,
    _warn_if_cold,
    run_agent,
    _keep_for_history,
    _MAX_HISTORY_TURNS,
    COLD_START_STATUS_CODES,
)
import deuscode.agent as _agent_module


# ── _strip_thinking ─────────────────────────────────────────────────────────

def test_strip_thinking_removes_tags():
    text = "<think>internal reasoning</think>Hello user"
    assert _strip_thinking(text) == "Hello user"


def test_strip_thinking_multiline():
    text = "<think>\nstep 1\nstep 2\n</think>\nResult here"
    assert _strip_thinking(text) == "Result here"


def test_strip_thinking_no_tags():
    assert _strip_thinking("plain text") == "plain text"


def test_strip_thinking_empty():
    assert _strip_thinking("") == ""


# ── _clean_response ─────────────────────────────────────────────────────────

def test_clean_response_strips_tool_result():
    text = "Summary <tool_result>raw output</tool_result> done"
    assert _clean_response(text) == "Summary  done"


def test_clean_response_strips_tool_call():
    text = "Before <tool_call>call data</tool_call> After"
    assert _clean_response(text) == "Before  After"


def test_clean_response_strips_all_xml():
    text = "<foo>bar</foo>plain"
    assert _clean_response(text) == "barplain"


def test_clean_response_empty_input():
    assert _clean_response("") == ""


# ── _parse_xml_tools ────────────────────────────────────────────────────────

def test_parse_xml_tools_bash():
    text = "<bash><command>ls -la</command></bash>"
    calls = _parse_xml_tools(text)
    assert len(calls) == 1
    assert calls[0] == ("bash", {"command": "ls -la"})


def test_parse_xml_tools_read_file():
    text = "<read_file><path>foo.py</path></read_file>"
    calls = _parse_xml_tools(text)
    assert len(calls) == 1
    assert calls[0] == ("read_file", {"path": "foo.py"})


def test_parse_xml_tools_write_file():
    text = "<write_file><path>out.txt</path><content>hello</content></write_file>"
    calls = _parse_xml_tools(text)
    assert len(calls) == 1
    assert calls[0] == ("write_file", {"path": "out.txt", "content": "hello"})


def test_parse_xml_tools_multiple():
    text = (
        "<read_file><path>a.py</path></read_file>"
        "<bash><command>echo hi</command></bash>"
    )
    calls = _parse_xml_tools(text)
    assert len(calls) == 2


def test_parse_xml_tools_no_tools():
    assert _parse_xml_tools("just plain text") == []


# ── _normalize_args ─────────────────────────────────────────────────────────

def test_normalize_args_write_file():
    raw = {"path": "f.py", "content": "code"}
    assert _normalize_args("write_file", raw, "") == {"path": "f.py", "content": "code"}


def test_normalize_args_write_file_missing_content():
    raw = {"path": "f.py", "body": "code"}
    result = _normalize_args("write_file", raw, "")
    assert result["path"] == "f.py"
    assert result["content"] == "code"


def test_normalize_args_bash_cmd_alias():
    raw = {"cmd": "ls"}
    assert _normalize_args("bash", raw, "") == {"command": "ls"}


# ── _request_with_cold_start_handling ───────────────────────────────────────

@pytest.mark.asyncio
async def test_cold_start_returns_on_200():
    resp = MagicMock(status_code=200)
    client = MagicMock()
    client.post = AsyncMock(return_value=resp)
    result = await _request_with_cold_start_handling(client, "http://x", {}, {})
    assert result.status_code == 200
    assert client.post.call_count == 1


@pytest.mark.asyncio
async def test_cold_start_retries_on_500(monkeypatch):
    monkeypatch.setattr("deuscode.agent.COLD_START_POLL_INTERVAL", 0)
    monkeypatch.setattr("deuscode.agent.ui.console.print", lambda *a, **kw: None)
    cold = MagicMock(status_code=500)
    ok = MagicMock(status_code=200)
    client = MagicMock()
    client.post = AsyncMock(side_effect=[cold, cold, ok])
    result = await _request_with_cold_start_handling(client, "http://x", {}, {})
    assert result.status_code == 200
    assert client.post.call_count == 3


@pytest.mark.asyncio
async def test_cold_start_retries_on_read_timeout(monkeypatch):
    import httpx as _httpx
    monkeypatch.setattr("deuscode.agent.COLD_START_POLL_INTERVAL", 0)
    monkeypatch.setattr("deuscode.agent._cold_start_timeout", lambda *a: 9999)
    monkeypatch.setattr("deuscode.agent.ui.console.print", lambda *a, **kw: None)
    ok = MagicMock(status_code=200)
    client = MagicMock()
    client.post = AsyncMock(side_effect=[_httpx.ReadTimeout("timeout"), ok])
    result = await _request_with_cold_start_handling(client, "http://x", {}, {})
    assert result.status_code == 200
    assert client.post.call_count == 2


@pytest.mark.asyncio
async def test_cold_start_passes_through_400():
    resp = MagicMock(status_code=400)
    client = MagicMock()
    client.post = AsyncMock(return_value=resp)
    result = await _request_with_cold_start_handling(client, "http://x", {}, {})
    assert result.status_code == 400


@pytest.mark.asyncio
async def test_cold_start_raises_after_timeout(monkeypatch):
    monkeypatch.setattr("deuscode.agent.COLD_START_POLL_INTERVAL", 0)
    monkeypatch.setattr("deuscode.agent._cold_start_timeout", lambda *a: 0)
    monkeypatch.setattr("deuscode.agent.ui.console.print", lambda *a, **kw: None)
    cold = MagicMock(status_code=503)
    client = MagicMock()
    client.post = AsyncMock(return_value=cold)
    with pytest.raises(RuntimeError, match="did not become ready"):
        await _request_with_cold_start_handling(client, "http://x", {}, {})


def test_cold_start_constants():
    assert 500 in COLD_START_STATUS_CODES
    assert 502 in COLD_START_STATUS_CODES
    assert 503 in COLD_START_STATUS_CODES
    assert 504 not in COLD_START_STATUS_CODES  # gateway timeout, not cold start


def test_cold_start_timeout_by_model_size():
    assert _cold_start_timeout("Qwen/Qwen2.5-Coder-7B-Instruct") == 900
    assert _cold_start_timeout("Qwen/Qwen2.5-Coder-14B-Instruct") == 1200
    assert _cold_start_timeout("Qwen/Qwen2.5-Coder-32B-Instruct") == 1800
    assert _cold_start_timeout("meta-llama/Llama-3.1-70B-Instruct") == 2400
    assert _cold_start_timeout("unknown/model") == 900  # unknown → 0 params → ≤7 bucket


# ── _build_system_prompt ────────────────────────────────────────────────────

def test_build_system_prompt_no_map():
    prompt = _build_system_prompt("/tmp", no_map=True)
    assert "Working directory:" in prompt
    assert "Files in working directory" not in prompt


# ── _call_serverless ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_call_serverless_uses_xml_fallback_and_returns_false(monkeypatch):
    """_call_serverless must inject XML system prompt and always return use_tools=False."""
    output = {"choices": [{"message": {"role": "assistant", "content": "Hello"}}]}

    async def fake_submit(*a, **kw):
        return "job-id-1"

    async def fake_poll(*a, **kw):
        return output

    monkeypatch.setattr("deuscode.agent.ui.console.print", lambda *a, **kw: None)
    monkeypatch.setattr("deuscode.endpoints.job_client.submit_job", fake_submit)
    monkeypatch.setattr("deuscode.endpoints.job_client.poll_job", fake_poll)

    from unittest.mock import MagicMock
    config = MagicMock()
    config.api_key = "key"
    config.endpoint_id = "ep-1"
    config.model = "Qwen/Qwen2.5-Coder-7B-Instruct"
    config.max_tokens = 512

    messages = [
        {"role": "system", "content": "You are Deus."},
        {"role": "user", "content": "hello"},
    ]
    result_output, use_tools = await _call_serverless(messages, config, use_tools=True)
    assert use_tools is False  # always XML path
    assert result_output == output
    # XML instructions must have been injected into system message
    assert "<write_file>" in messages[0]["content"]


# ── _warn_if_cold session flag ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_warn_if_cold_shows_once_per_session(monkeypatch):
    """Cold start warning must not repeat on subsequent prompts."""
    _agent_module._cold_warned_this_session = False
    warnings_shown = []

    async def fake_get_status(*a, **kw):
        from deuscode.endpoints.base import EndpointStatus
        return EndpointStatus.COLD

    monkeypatch.setattr(
        "deuscode.agent.ui.print_cold_start_warning",
        lambda *a, **kw: warnings_shown.append(1),
    )

    class FakeProvider:
        async def get_status(self, *a, **kw):
            from deuscode.endpoints.base import EndpointStatus
            return EndpointStatus.COLD

    monkeypatch.setattr(
        "deuscode.agent.get_endpoint_provider" if hasattr(_agent_module, "get_endpoint_provider") else
        "deuscode.endpoints.get_endpoint_provider",
        lambda *a: FakeProvider(),
    )

    config = MagicMock()
    config.endpoint_type = "serverless"
    config.endpoint_id = "ep-1"
    config.api_key = "key"
    config.model = "Qwen/Qwen2.5-Coder-7B-Instruct"

    await _warn_if_cold(config)
    await _warn_if_cold(config)
    await _warn_if_cold(config)
    assert len(warnings_shown) == 1  # only once


@pytest.mark.asyncio
async def test_warn_if_cold_skips_when_ready(monkeypatch):
    """No warning when workers are warm."""
    _agent_module._cold_warned_this_session = False
    warnings_shown = []

    class FakeProvider:
        async def get_status(self, *a, **kw):
            from deuscode.endpoints.base import EndpointStatus
            return EndpointStatus.READY

    monkeypatch.setattr(
        "deuscode.endpoints.get_endpoint_provider",
        lambda *a: FakeProvider(),
    )
    monkeypatch.setattr(
        "deuscode.agent.ui.print_cold_start_warning",
        lambda *a, **kw: warnings_shown.append(1),
    )

    config = MagicMock()
    config.endpoint_type = "serverless"
    config.endpoint_id = "ep-1"
    config.api_key = "key"
    config.model = "Qwen/Qwen2.5-Coder-7B-Instruct"

    await _warn_if_cold(config)
    assert len(warnings_shown) == 0


# ── _keep_for_history ────────────────────────────────────────────────────────

def test_keep_for_history_drops_tool_role():
    assert not _keep_for_history({"role": "tool", "content": "result"})

def test_keep_for_history_drops_tool_result_user_message():
    assert not _keep_for_history({"role": "user", "content": "<tool_result>big blob</tool_result>"})

def test_keep_for_history_drops_summarize_prompt():
    assert not _keep_for_history({"role": "user", "content": "Summarize what you just did in one or two sentences, no XML tags."})

def test_keep_for_history_drops_intermediate_tool_call():
    assert not _keep_for_history({"role": "assistant", "content": "", "tool_calls": [{"id": "x"}]})

def test_keep_for_history_keeps_normal_user():
    assert _keep_for_history({"role": "user", "content": "fix the bug"})

def test_keep_for_history_keeps_final_assistant():
    assert _keep_for_history({"role": "assistant", "content": "Done, I fixed it."})


# ── run_agent conversation history ───────────────────────────────────────────

def _make_fake_loop(captured_messages: list):
    """Return a fake _loop that records messages and returns a fixed response."""
    async def fake_loop(client, messages, model, config):
        captured_messages.clear()
        captured_messages.extend(messages)
        # Simulate assistant reply being appended (as real _loop does)
        messages.append({"role": "assistant", "content": "Done"})
        return "Done"
    return fake_loop


def _minimal_plan():
    from deuscode.action_plan import ActionPlan
    return ActionPlan(
        agent_instructions="Do something",
        reasoning="test",
        files_to_read=[],
        search_queries=[],
        files_to_create=[],
        validation_steps=[],
    )


@pytest.mark.asyncio
async def test_run_agent_with_history(monkeypatch):
    """Prior conversation turns must be injected between system and new user message."""
    captured = []
    monkeypatch.setattr("deuscode.agent._loop", _make_fake_loop(captured))
    monkeypatch.setattr("deuscode.agent._warn_if_cold", AsyncMock())
    monkeypatch.setattr("deuscode.agent.generate_repo_map", lambda *a: "")
    monkeypatch.setattr("deuscode.agent.ui.thinking", lambda *a: None)

    config = MagicMock()
    config.endpoint_type = "pod"
    prior_history = [
        {"role": "user", "content": "first question"},
        {"role": "assistant", "content": "first answer"},
    ]
    plan = _minimal_plan()
    result, updated = await run_agent(
        plan, {"files": {}, "searches": {}}, "", config, "/tmp",
        conversation_history=prior_history,
    )
    # system, prior user, prior assistant, new user prompt
    assert captured[0]["role"] == "system"
    assert captured[1] == prior_history[0]
    assert captured[2] == prior_history[1]
    assert captured[3]["role"] == "user"
    assert captured[3]["content"] == "Do something"
    assert result == "Done"
    assert len(updated) > len(prior_history)


@pytest.mark.asyncio
async def test_run_agent_caps_history(monkeypatch):
    """updated_history must never exceed _MAX_HISTORY_TURNS and must start with user."""
    captured = []
    monkeypatch.setattr("deuscode.agent._loop", _make_fake_loop(captured))
    monkeypatch.setattr("deuscode.agent._warn_if_cold", AsyncMock())
    monkeypatch.setattr("deuscode.agent.generate_repo_map", lambda *a: "")
    monkeypatch.setattr("deuscode.agent.ui.thinking", lambda *a: None)

    config = MagicMock()
    config.endpoint_type = "pod"
    # 25 prior turns alternating user/assistant — cap will slice mid-pair
    big_history = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"msg {i}"}
        for i in range(25)
    ]
    plan = _minimal_plan()
    _, updated = await run_agent(
        plan, {"files": {}, "searches": {}}, "", config, "/tmp",
        conversation_history=big_history,
    )
    assert len(updated) <= _MAX_HISTORY_TURNS
    # After capping, history must start with a user message
    assert updated[0]["role"] == "user"


@pytest.mark.asyncio
async def test_run_agent_empty_history(monkeypatch):
    """None history must work identically to no-history behaviour."""
    captured = []
    monkeypatch.setattr("deuscode.agent._loop", _make_fake_loop(captured))
    monkeypatch.setattr("deuscode.agent._warn_if_cold", AsyncMock())
    monkeypatch.setattr("deuscode.agent.generate_repo_map", lambda *a: "")
    monkeypatch.setattr("deuscode.agent.ui.thinking", lambda *a: None)

    config = MagicMock()
    config.endpoint_type = "pod"
    plan = _minimal_plan()
    result, updated = await run_agent(
        plan, {"files": {}, "searches": {}}, "", config, "/tmp",
        conversation_history=None,
    )
    assert captured[0]["role"] == "system"
    assert captured[1]["role"] == "user"
    assert len(captured) == 2  # only system + user, no injected history
    assert result == "Done"
    assert isinstance(updated, list)
