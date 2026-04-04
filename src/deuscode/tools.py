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
    return target.read_text(encoding="utf-8", errors="replace")


async def write_file(path: str, content: str) -> str:
    target = Path(path).expanduser().resolve()
    if target.exists():
        existing = target.read_text(encoding="utf-8", errors="replace")
        _show_diff(existing, content, path)
    if not ui.confirm(f"Write to [bold]{path}[/bold]?"):
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


def _show_diff(old: str, new: str, path: str) -> None:
    old_lines = old.splitlines()
    new_lines = new.splitlines()
    ui.console.print(f"[dim]Diff for {path}:[/dim]")
    for line in old_lines:
        if line not in new_lines:
            ui.console.print(f"[red]- {line}[/red]")
    for line in new_lines:
        if line not in old_lines:
            ui.console.print(f"[green]+ {line}[/green]")


TOOL_FUNCTIONS = {
    "read_file": read_file,
    "write_file": write_file,
    "bash": bash,
}


async def dispatch(name: str, args_json: str) -> str:
    fn = TOOL_FUNCTIONS.get(name)
    if fn is None:
        return f"Error: unknown tool '{name}'"
    args = json.loads(args_json)
    return await fn(**args)
