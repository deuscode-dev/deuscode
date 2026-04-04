import json

import httpx

from deuscode.config import Config
from deuscode.repomap import generate_repo_map
from deuscode import tools, ui

_SYSTEM_BASE = (
    "You are Deus, an AI coding assistant. "
    "You have access to tools to read/write files and run shell commands. "
    "Always explain what you are doing before calling a tool."
)


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
        return await _loop(client, messages, model, config)


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


async def _chat(client: httpx.AsyncClient, messages: list, model: str, config: Config) -> dict:
    response = await client.post(
        f"{config.base_url.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {config.api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": messages,
            "tools": tools.TOOL_SCHEMAS,
            "max_tokens": config.max_tokens,
        },
    )
    response.raise_for_status()
    return response.json()


async def _execute_tool(tc: dict) -> str:
    fn = tc["function"]
    ui.tool_call(fn["name"], json.loads(fn.get("arguments", "{}")))
    result = await tools.dispatch(fn["name"], fn.get("arguments", "{}"))
    ui.tool_result(result[:500])
    return result
