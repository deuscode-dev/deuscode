import json
import subprocess
from pathlib import Path

from deuscode import ui

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "File path to read"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file after user confirmation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to write"},
                    "content": {"type": "string", "description": "Content to write"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Run a shell command after user confirmation.",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string", "description": "Shell command to run"}},
                "required": ["command"],
            },
        },
    },
]


async def read_file(path: str) -> str:
    target = Path(path).expanduser().resolve()
    if not target.exists():
        return f"Error: '{path}' does not exist."
    content = target.read_text(encoding="utf-8", errors="replace")
    ui.print_file_content(path, content)
    return content


async def write_file(path: str, content: str) -> str:
    target = Path(path).expanduser().resolve()
    if target.exists():
        existing = target.read_text(encoding="utf-8", errors="replace")
        ui.print_diff(existing, content, path)
        confirmed = ui.confirm(f"[yellow]Write changes to {path}?[/yellow]")
    else:
        ui.print_panel(f"New file: {path} ({len(content.splitlines())} lines)")
        confirmed = ui.confirm(f"[yellow]Create {path}?[/yellow]")
    if not confirmed:
        return "Cancelled by user."
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"Written: {path}"


async def bash(command: str) -> str:
    ui.console.print(f"[bold yellow]Command:[/bold yellow] {command}")
    if not ui.confirm("Run this command?"):
        return "Cancelled by user."
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    output = result.stdout + result.stderr
    return output.strip() or "(no output)"


async def search_web(query: str, config: dict | None = None) -> str:
    """
    Search the web and return formatted results string.
    Used by context_loader and available as agent tool.
    Returns empty string on any failure — never raises.
    """
    from deuscode.search import get_search_backend
    from deuscode.config import load_config

    try:
        cfg = config or vars(load_config())
        backend = get_search_backend(cfg)
        results = await backend.search(query, max_results=3)
    except Exception:
        return f"[No results found for: {query}]"

    if not results:
        return f"[No results found for: {query}]"

    return _format_results(results)


def _format_results(results: list) -> str:
    """Format SearchResult list into agent-readable string."""
    parts = []
    for i, r in enumerate(results, 1):
        content = r.full_content or r.snippet
        parts.append(
            f"[{i}] {r.title}\n"
            f"URL: {r.url}\n"
            f"{content[:1500]}"
        )
    return "\n\n---\n\n".join(parts)


TOOL_FUNCTIONS = {
    "read_file": read_file,
    "write_file": write_file,
    "bash": bash,
    "search_web": search_web,
}


async def dispatch(name: str, args_json: str) -> str:
    fn = TOOL_FUNCTIONS.get(name)
    if fn is None:
        return f"Error: unknown tool '{name}'"
    args = json.loads(args_json)
    return await fn(**args)
