"""Tests for agent.py — pure helper functions."""

from deuscode.agent import (
    _strip_thinking,
    _clean_response,
    _parse_xml_tools,
    _normalize_args,
    _build_system_prompt,
)


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


# ── _build_system_prompt ────────────────────────────────────────────────────

def test_build_system_prompt_no_map():
    prompt = _build_system_prompt("/tmp", no_map=True)
    assert "Working directory:" in prompt
    assert "Files in working directory" not in prompt
