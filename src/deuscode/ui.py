import difflib

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.syntax import Syntax
from rich.text import Text

console = Console()


def thinking(model: str) -> None:
    console.print(f"[dim]Deus is thinking... ({model})[/dim]")


def tool_call(name: str, args: dict) -> None:
    args_str = ", ".join(f"{k}={v!r}" for k, v in args.items())
    console.print(f"[yellow]⚡ Calling: {name}({args_str})[/yellow]")


def tool_result(text: str) -> None:
    console.print(f"[dim grey]{text}[/dim grey]")


def print_file_content(path: str, content: str) -> None:
    ext = path.rsplit(".", 1)[-1] if "." in path else "text"
    syntax = Syntax(content, ext, theme="monokai", line_numbers=True, word_wrap=True)
    console.print(Panel(syntax, title=f"📄 {path}", border_style="dim"))


def print_diff(old: str, new: str, path: str) -> None:
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    diff = list(difflib.unified_diff(old_lines, new_lines, fromfile=path, tofile=path, lineterm=""))
    if not diff:
        console.print(f"[dim]No changes in {path}[/dim]")
        return
    text = Text()
    for line in diff[2:]:  # skip the --- / +++ header lines
        if line.startswith("+"):
            text.append(line + "\n", style="green")
        elif line.startswith("-"):
            text.append(line + "\n", style="red")
        elif line.startswith("@@"):
            text.append(line + "\n", style="cyan")
        else:
            text.append(line + "\n", style="dim")
    console.print(Panel(text, title=f"Changes to {path}", border_style="yellow"))


def print_panel(text: str) -> None:
    console.print(Panel(text, border_style="dim"))


def print_dim(text: str) -> None:
    console.print(f"[dim]{text}[/dim]")


def final_answer(text: str) -> None:
    console.print(Panel(text, title="[bold cyan]Deus[/bold cyan]", border_style="cyan"))


def print_success(text: str) -> None:
    console.print(f"[bold green]✓ {text}[/bold green]")


def error(text: str) -> None:
    console.print(Panel(text, title="[bold red]Error[/bold red]", border_style="red"))


def warning(text: str) -> None:
    console.print(f"[bold yellow]⚠ {text}[/bold yellow]")


def confirm(prompt: str) -> bool:
    return Confirm.ask(prompt)
