import asyncio
import json

import httpx
import yaml

from deuscode.config import Config, CONFIG_PATH
from deuscode.repomap import generate_repo_map
from deuscode import tools, ui, runpod

_SYSTEM_BASE = (
    "You are Deus, an AI coding assistant. "
    "You have access to tools to read/write files and run shell commands. "
    "Always explain what you are doing before calling a tool."
)


async def run_agent(
    prompt: str,
    path: str = ".",
    model_override: str | None = None,
    no_map: bool = False,
) -> None:
    from deuscode.config import load_config
    try:
        config = load_config()
    except FileNotFoundError as e:
        ui.error(str(e))
        return
    result = await run(prompt, config, path=path, model_override=model_override, no_map=no_map)
    ui.final_answer(result)


async def chat_loop(
    path: str = ".",
    model_override: str | None = None,
    no_map: bool = False,
) -> None:
    from deuscode.config import load_config
    from rich.prompt import Prompt
    try:
        config = load_config()
    except FileNotFoundError as e:
        ui.error(str(e))
        return
    model = model_override or config.model
    system_prompt = _build_system_prompt(path, no_map)
    messages: list = [{"role": "system", "content": system_prompt}]
    ui.console.print(f"[bold green]Deus[/bold green] [dim]{model}[/dim]  (Ctrl+C or empty line to exit)\n")
    async with httpx.AsyncClient(timeout=120.0) as client:
        while True:
            try:
                prompt = Prompt.ask("[bold cyan]you[/bold cyan]")
            except (EOFError, KeyboardInterrupt):
                ui.console.print("\n[dim]Goodbye.[/dim]")
                break
            if not prompt.strip():
                ui.console.print("[dim]Goodbye.[/dim]")
                break
            messages.append({"role": "user", "content": prompt})
            ui.thinking(model)
            result = await _loop(client, messages, model, config)
            ui.final_answer(result)
    await _maybe_auto_stop(config)


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
    if no_map:
        return _SYSTEM_BASE
    repo_map = generate_repo_map(path)
    return f"{_SYSTEM_BASE}\n\n## Repo Map\n{repo_map}"


async def _loop(client: httpx.AsyncClient, messages: list, model: str, config: Config) -> str:
    while True:
        data = await _chat(client, messages, model, config)
        choice = data["choices"][0]
        msg = choice["message"]
        messages.append(msg)

        tool_calls = msg.get("tool_calls") or []
        if not tool_calls:
            return msg.get("content") or ""

        for tc in tool_calls:
            result = await _execute_tool(tc)
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": result,
            })


_RETRY_STATUSES = {502, 503, 504}
_RETRY_DELAYS = [5, 10, 20, 30, 60]


async def _chat(client: httpx.AsyncClient, messages: list, model: str, config: Config) -> dict:
    url = f"{config.base_url.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {config.api_key}", "Content-Type": "application/json"}
    return await _post_with_retry(client, url, headers, messages, model, config, use_tools=True)


async def _post_with_retry(
    client: httpx.AsyncClient,
    url: str,
    headers: dict,
    messages: list,
    model: str,
    config: Config,
    use_tools: bool,
) -> dict:
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

    if response.status_code == 400 and use_tools:
        body = response.text
        if "tool" in body.lower():
            ui.console.print("[dim]Tools not supported by this vLLM instance, retrying without tools...[/dim]")
            return await _post_with_retry(client, url, headers, messages, model, config, use_tools=False)

    if not response.is_success:
        body = response.text[:300].strip()
        hint = ""
        if response.status_code == 404:
            hint = "\n\nHint: vLLM started without a model. Stop this pod and run: deus setup --runpod"
        raise RuntimeError(f"HTTP {response.status_code} from {url}\n{body}{hint}")
    return response.json()


async def _execute_tool(tc: dict) -> str:
    fn = tc["function"]
    ui.tool_call(fn["name"], json.loads(fn.get("arguments", "{}")))
    result = await tools.dispatch(fn["name"], fn.get("arguments", "{}"))
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
