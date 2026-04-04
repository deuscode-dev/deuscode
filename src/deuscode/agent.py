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
    async with httpx.AsyncClient(timeout=120.0) as client:
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


async def _loop(client: httpx.AsyncClient, messages: list, model: str, config: Config) -> str:
    use_tools = True  # starts True; flipped to False on first 400 and stays False
    while True:
        data, use_tools = await _chat(client, messages, model, config, use_tools)
        msg = data["choices"][0]["message"]
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

_RETRY_STATUSES = {502, 503, 504}
_RETRY_DELAYS = [5, 10, 20, 30, 60]


async def _chat(
    client: httpx.AsyncClient,
    messages: list,
    model: str,
    config: Config,
    use_tools: bool = True,
) -> tuple[dict, bool]:
    """Returns (response_data, tools_were_used)."""
    url = f"{config.base_url.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {config.api_key}", "Content-Type": "application/json"}

    payload: dict = {"model": model, "messages": messages, "max_tokens": config.max_tokens}
    if use_tools:
        payload["tools"] = tools.TOOL_SCHEMAS

    for delay in _RETRY_DELAYS + [None]:
        response = await client.post(url, headers=headers, json=payload)
        if response.status_code not in _RETRY_STATUSES:
            break
        if delay is None:
            break
        ui.console.print(f"[dim]Server not ready ({response.status_code}), retrying in {delay}s...[/dim]")
        await asyncio.sleep(delay)

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
