import asyncio
import json
import re as _re
from pathlib import Path

import httpx
import yaml

from deuscode.config import Config, CONFIG_PATH
from deuscode.repomap import generate_repo_map
from deuscode import tools, ui, runpod

_xml_fallback_warned = False
_cold_warned_this_session = False

_SYSTEM_BASE = """\
You are Deus, an AI coding assistant running in a terminal.

RULES — follow strictly:
- To create or modify a file you MUST call the write_file tool. Never print file contents as a code block instead of writing them.
- To read a file you MUST call the read_file tool.
- To run a command you MUST call the bash tool.
- Do NOT describe what you would do — just do it by calling the tool.
- After calling a tool, briefly explain what you did and ask if anything else is needed.
- If you cannot complete a task without tools, say so clearly.\
"""

_XML_TOOL_ADDON = """

## Tool Protocol (use these XML tags to perform actions)

List files in current directory:
<bash>
<command>ls -la</command>
</bash>

Read a file:
<read_file>
<path>filename.txt</path>
</read_file>

Write/create a file:
<write_file>
<path>filename.txt</path>
<content>
file content here
</content>
</write_file>

Run any shell command:
<bash>
<command>any shell command here</command>
</bash>

IMPORTANT: Use these XML tags to actually perform actions. Never just describe what you would do.\
"""



async def call_llm(system: str, messages: list, config: Config) -> str:
    """Single-shot LLM call with no tool loop. Used by the planner."""
    full = [{"role": "system", "content": system}] + messages
    async with httpx.AsyncClient(timeout=httpx.Timeout(connect=30.0, read=600.0, write=30.0, pool=30.0)) as client:
        data, _ = await _chat(client, full, config.model, config, use_tools=False)
    msg = data["choices"][0]["message"]
    return _strip_thinking(msg.get("content") or "")


_MAX_HISTORY_TURNS = 20
_SUMMARIZE_PROMPT = "Summarize what you just did in one or two sentences, no XML tags."


def _keep_for_history(msg: dict) -> bool:
    """True if the message belongs in the next prompt's conversation context.

    Strips tool-execution noise (tool results, intermediate tool-call steps,
    summarize prompts) that bloats context without adding conversational value.
    """
    role = msg.get("role")
    content = msg.get("content") or ""
    if role == "tool":
        return False
    if role == "user" and content.startswith("<tool_result>"):
        return False
    if role == "user" and content == _SUMMARIZE_PROMPT:
        return False
    if role == "assistant" and msg.get("tool_calls"):
        return False  # intermediate step; final summary is kept
    return True


async def run_agent(
    plan: "ActionPlan",
    preloaded_context: dict,
    repo_map: str,
    config: Config,
    path: str = ".",
    conversation_history: list[dict] | None = None,
) -> tuple[str, list[dict]]:
    """Run the agent with a pre-built plan and preloaded context.

    Returns (response_text, updated_history). updated_history is capped at
    _MAX_HISTORY_TURNS messages to avoid unbounded context growth.
    """
    await _warn_if_cold(config)
    system = _build_agent_system(plan, preloaded_context, repo_map, path)
    messages = [{"role": "system", "content": system}]
    if conversation_history:
        messages.extend(conversation_history)
    messages.append({"role": "user", "content": plan.agent_instructions})
    history_start = 1 + len(conversation_history or [])
    ui.thinking(config.model)
    async with httpx.AsyncClient(timeout=httpx.Timeout(connect=30.0, read=600.0, write=30.0, pool=30.0)) as client:
        response_text = await _loop(client, messages, config.model, config)
    new_turns = [m for m in messages[history_start:] if _keep_for_history(m)]
    updated = list(conversation_history or []) + new_turns
    if len(updated) > _MAX_HISTORY_TURNS:
        updated = updated[-_MAX_HISTORY_TURNS:]
        # Ensure history never starts with an assistant turn (some models reject this)
        while updated and updated[0].get("role") != "user":
            updated = updated[1:]
    return response_text, updated


async def _warn_if_cold(config: Config) -> None:
    """Warn user if serverless endpoint is cold. Shows at most once per session."""
    global _cold_warned_this_session
    if _cold_warned_this_session or config.endpoint_type != "serverless" or not config.endpoint_id:
        return
    try:
        from deuscode.endpoints import get_endpoint_provider, EndpointStatus
        provider = get_endpoint_provider(config.endpoint_type)
        status = await provider.get_status(config.api_key, config.endpoint_id)
        if status == EndpointStatus.COLD:
            ui.print_cold_start_warning(config.model)
            _cold_warned_this_session = True
    except Exception:
        pass


def _build_agent_system(plan: "ActionPlan", preloaded_context: dict, repo_map: str, path: str) -> str:
    from deuscode.context_loader import format_preloaded_context
    cwd = str(Path(path).resolve())
    parts = [_SYSTEM_BASE, f"\n\nWorking directory: {cwd}"]
    if repo_map:
        parts.append(f"\n\n## Files in working directory\n{repo_map}")
    preloaded_str = format_preloaded_context(preloaded_context)
    if preloaded_str:
        parts.append(f"\n\n## Pre-loaded Context\n{preloaded_str}")
    if plan.validation_steps:
        steps = "\n".join(f"- {s}" for s in plan.validation_steps)
        parts.append(f"\n\n## Validation Checklist\n{steps}")
    return "".join(parts)


async def run(
    prompt: str,
    config: Config,
    path: str = ".",
    model_override: str | None = None,
    no_map: bool = False,
) -> str:
    model = model_override or config.model
    system_prompt = _build_system_prompt(path, no_map)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]
    ui.thinking(model)
    async with httpx.AsyncClient(timeout=httpx.Timeout(connect=30.0, read=600.0, write=30.0, pool=30.0)) as client:
        result = await _loop(client, messages, model, config)
    await _maybe_auto_stop(config)
    return result


def _build_system_prompt(path: str, no_map: bool) -> str:
    cwd = str(Path(path).resolve())
    base = _SYSTEM_BASE + f"\n\nWorking directory: {cwd}"
    if no_map:
        return base
    repo_map = generate_repo_map(path)
    return f"{base}\n\n## Files in working directory\n{repo_map}"


_MAX_TURNS = 25


async def _call_serverless(messages: list, config: Config, use_tools: bool) -> tuple[dict, bool]:
    """Use RunPod native job API — no HTTP timeout issues during CUDA compilation.

    Native tool calling requires ENABLE_AUTO_TOOL_CHOICE on the endpoint; use XML fallback.
    """
    from deuscode.endpoints.job_client import submit_job, poll_job
    _inject_xml_system(messages)  # XML fallback — job API doesn't support native tools
    ui.console.print("[dim]◆ Submitting job...[/dim]")
    job_id = await submit_job(
        config.api_key, config.endpoint_id,
        messages, config.model, config.max_tokens,
    )
    ui.console.print(f"[dim]  Job ID: {job_id}[/dim]")
    _STATUS_DISPLAY = {"IN_QUEUE": "⏳ In queue...", "IN_PROGRESS": "⚡ Running..."}

    def on_status(status: str, elapsed: int) -> None:
        msg = _STATUS_DISPLAY.get(status)
        if msg and elapsed % 10 == 0:
            ui.console.print(f"[dim]  {elapsed}s — {msg}[/dim]")

    max_wait = _cold_start_timeout(config.model)
    output = await poll_job(
        config.api_key, config.endpoint_id, job_id,
        on_status_update=on_status, max_wait=max_wait,
    )
    return output, False  # always XML path for serverless job API


async def _loop(client: httpx.AsyncClient, messages: list, model: str, config: Config) -> str:
    use_tools = True  # starts True; flipped to False on first 400 and stays False
    for _ in range(_MAX_TURNS):
        if config.endpoint_type == "serverless":
            data, use_tools = await _call_serverless(messages, config, use_tools)
        else:
            data, use_tools = await _chat(client, messages, model, config, use_tools)
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError(f"Empty response from model: {data!r:.200}")
        msg = choices[0]["message"]
        content = _strip_thinking(msg.get("content") or "")
        messages.append(msg)

        if use_tools:
            tool_calls = msg.get("tool_calls") or []
            if not tool_calls:
                return _clean_response(content) or "(empty response)"
            for tc in tool_calls:
                result = await _execute_tool(tc)
                messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})
        else:
            xml_calls = _parse_xml_tools(content)
            if not xml_calls:
                await _offer_code_blocks(content)
                return _clean_response(content) or "(model produced no output — try a larger model)"
            for name, args in xml_calls:
                ui.tool_call(name, args)
                result = await tools.dispatch(name, json.dumps(args))
                if name != "read_file":
                    ui.tool_result(result[:500])
                messages.append({"role": "user", "content": f"<tool_result>{result}</tool_result>"})
            # Ask the model for a clean summary after tool execution
            messages.append({"role": "user", "content": "Summarize what you just did in one or two sentences, no XML tags."})
    ui.warning(f"Agent reached {_MAX_TURNS}-turn limit")
    return _clean_response(content) or "(reached turn limit)"


# ── thinking-tag stripping ────────────────────────────────────────────────────

_THINK_RE = _re.compile(r"<think>.*?</think>", _re.DOTALL)
_TOOL_RESULT_RE = _re.compile(r"<tool_result>.*?</tool_result>", _re.DOTALL)
_TOOL_CALL_RE = _re.compile(r"<tool_call>.*?</tool_call>", _re.DOTALL)
_XML_TAG_STRIP_RE = _re.compile(r"<[^>]+>")


def _strip_thinking(text: str) -> str:
    return _THINK_RE.sub("", text).strip()


def _clean_response(text: str) -> str:
    text = _TOOL_RESULT_RE.sub("", text)
    text = _TOOL_CALL_RE.sub("", text)
    text = _XML_TAG_STRIP_RE.sub("", text)
    return text.strip()


# ── XML tool protocol ─────────────────────────────────────────────────────────

_XML_TOOL_RE = _re.compile(
    r"<(write_file|read_file|bash)>(.*?)</\1>", _re.DOTALL
)
_XML_TAG_RE = _re.compile(r"<(\w+)>(.*?)</\1>", _re.DOTALL)


def _parse_xml_tools(text: str) -> list[tuple[str, dict]]:
    calls = []
    for m in _XML_TOOL_RE.finditer(text):
        name = m.group(1)
        body = m.group(2)
        raw = {t.group(1): t.group(2).strip() for t in _XML_TAG_RE.finditer(body)}
        args = _normalize_args(name, raw, body)
        calls.append((name, args))
    return calls


def _normalize_args(name: str, raw: dict, body: str) -> dict:
    """Map whatever tags the model used to the expected argument names."""
    if name == "write_file":
        path = raw.get("path", "")
        # accept 'content' or any other non-path tag as the file content
        content = raw.get("content") or next(
            (v for k, v in raw.items() if k != "path"), ""
        )
        return {"path": path, "content": content}
    if name == "read_file":
        return {"path": raw.get("path", "")}
    if name == "bash":
        return {"command": raw.get("command", raw.get("cmd", ""))}
    return raw


# ── code-block save fallback ──────────────────────────────────────────────────

_CODE_BLOCK_RE = _re.compile(r"```(\w*)\n(.*?)```", _re.DOTALL)
_FILENAME_RE = _re.compile(
    r"\b([\w.-]+\.(?:html?|css|js|ts|py|sh|json|yaml|yml|xml|txt|md|rs|go|java|c|cpp|h))\b"
)
_LANG_EXT = {
    "html": "html", "css": "css", "javascript": "js", "js": "js",
    "typescript": "ts", "python": "py", "bash": "sh", "sh": "sh",
    "json": "json", "yaml": "yaml", "yml": "yaml", "xml": "xml",
}


def _suggest_filename(text: str, lang: str) -> str:
    m = _FILENAME_RE.search(text)
    if m:
        return m.group(1)
    ext = _LANG_EXT.get(lang.lower(), lang.lower() or "txt")
    return f"output.{ext}"


async def _offer_code_blocks(text: str) -> None:
    from rich.prompt import Prompt
    blocks = _CODE_BLOCK_RE.findall(text)
    if not blocks:
        return
    for i, (lang, code) in enumerate(blocks, 1):
        suggestion = _suggest_filename(text, lang)
        label = f"code block {i}" if len(blocks) > 1 else "code"
        try:
            path = Prompt.ask(f"[bold cyan]save {label} to[/bold cyan]", default=suggestion)
        except (EOFError, KeyboardInterrupt):
            return
        if not path.strip():
            continue
        target = Path(path).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(code, encoding="utf-8")
        ui.console.print(f"[green]✓ Saved {target}[/green]")


# ── HTTP chat ─────────────────────────────────────────────────────────────────

COLD_START_STATUS_CODES = {500, 502, 503}
COLD_START_POLL_INTERVAL = 10  # check every 10 seconds


def _cold_start_timeout(model_id: str) -> int:
    """Max cold start wait in seconds — CUDA graph compilation dominates first boot."""
    from deuscode.models import MODELS
    model = next((m for m in MODELS if m["id"] == model_id), None)
    params = model["param_count_b"] if model else 0
    if params <= 7:   return 900   # 15 min
    if params <= 14:  return 1200  # 20 min
    if params <= 32:  return 1800  # 30 min
    return 2400                    # 40 min


async def _request_with_cold_start_handling(
    client: httpx.AsyncClient,
    url: str,
    headers: dict,
    payload: dict,
    config: "Config | None" = None,
) -> httpx.Response:
    """Send immediately; retry on 500/502/503 or ReadTimeout with health status display."""
    import time
    from deuscode.endpoints.serverless import get_health
    api_key = config.api_key if config else ""
    endpoint_id = config.endpoint_id if config else ""
    max_wait = _cold_start_timeout(config.model if config else "")
    start = time.monotonic()
    while True:
        elapsed = int(time.monotonic() - start)
        if elapsed > max_wait:
            raise RuntimeError(
                f"Endpoint did not become ready after {max_wait}s. "
                "Check RunPod console for errors."
            )
        try:
            response = await client.post(url, headers=headers, json=payload)
        except httpx.ReadTimeout:
            elapsed = int(time.monotonic() - start)
            health = await get_health(api_key, endpoint_id)
            ui.print_worker_status(health, elapsed)
            continue  # retry immediately — no sleep on timeout
        if response.status_code not in COLD_START_STATUS_CODES:
            return response
        elapsed = int(time.monotonic() - start)
        health = await get_health(api_key, endpoint_id)
        ui.print_worker_status(health, elapsed)
        await asyncio.sleep(COLD_START_POLL_INTERVAL)


async def _chat(
    client: httpx.AsyncClient,
    messages: list,
    model: str,
    config: Config,
    use_tools: bool = True,
) -> tuple[dict, bool]:
    """Returns (response_data, tools_were_used)."""
    # Serverless: base_url = https://api.runpod.ai/v2/{endpoint_id}/openai/v1
    url = f"{config.base_url.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {config.api_key}", "Content-Type": "application/json"}

    payload: dict = {"model": model, "messages": messages, "max_tokens": config.max_tokens}
    if use_tools:
        payload["tools"] = tools.TOOL_SCHEMAS

    response = await _request_with_cold_start_handling(client, url, headers, payload, config)

    if response.status_code == 400 and use_tools and "tool" in response.text.lower():
        global _xml_fallback_warned
        if not _xml_fallback_warned:
            ui.warning("Function calling unavailable — using XML tool protocol")
            _xml_fallback_warned = True
        _inject_xml_system(messages)
        return await _chat(client, messages, model, config, use_tools=False)

    if not response.is_success:
        body = response.text[:300].strip()
        hint = ""
        if response.status_code == 404:
            hint = "\n\nHint: vLLM started without a model. Stop this pod and run: deus setup --runpod"
        raise RuntimeError(f"HTTP {response.status_code} from {url}\n{body}{hint}")

    return response.json(), use_tools


def _inject_xml_system(messages: list) -> None:
    """Append XML tool instructions to the existing system message (once)."""
    if messages and messages[0]["role"] == "system":
        if "<write_file>" not in messages[0]["content"]:
            messages[0] = {
                "role": "system",
                "content": messages[0]["content"] + _XML_TOOL_ADDON,
            }


async def _execute_tool(tc: dict) -> str:
    fn = tc["function"]
    name = fn["name"]
    ui.tool_call(name, json.loads(fn.get("arguments", "{}")))
    result = await tools.dispatch(name, fn.get("arguments", "{}"))
    # read_file already rendered the content via print_file_content — skip duplicate
    if name != "read_file":
        ui.tool_result(result[:500])
    return result


async def _maybe_auto_stop(config: Config) -> None:
    if not config.auto_stop_runpod:
        return
    raw = yaml.safe_load(CONFIG_PATH.read_text()) if CONFIG_PATH.exists() else {}
    pod_id = raw.get("runpod_pod_id")
    api_key = raw.get("runpod_api_key", "")
    if not pod_id:
        return
    ui.console.print(f"[bold yellow]⚡ Auto-stopping RunPod pod {pod_id}...[/bold yellow]")
    try:
        await runpod.stop_pod(api_key, pod_id)
        ui.console.print("[green]✓ Pod stopped. No more charges.[/green]")
    except Exception as e:
        ui.console.print(f"[red]Warning: could not stop pod {pod_id}: {e}[/red]")
