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


def print_panel(text: str, title: str = "", border_style: str = "dim") -> None:
    kwargs = {"border_style": border_style}
    if title:
        kwargs["title"] = title
    console.print(Panel(text, **kwargs))


def print_planning() -> None:
    console.print("[dim cyan]⟳ Planning...[/dim cyan]")


def print_action_plan(plan) -> None:
    lines = [f"[dim]{plan.reasoning}[/dim]"]
    if plan.files_to_read:
        lines.append("[bold]Read:[/bold] " + ", ".join(plan.files_to_read))
    if plan.search_queries:
        lines.append("[bold]Search:[/bold] " + ", ".join(plan.search_queries))
    if plan.files_to_create:
        lines.append("[bold]Create:[/bold] " + ", ".join(plan.files_to_create))
    if plan.validation_steps:
        checks = "  ".join(f"• {s}" for s in plan.validation_steps)
        lines.append(f"[bold]Validate:[/bold] {checks}")
    console.print(Panel("\n".join(lines), title="[bold cyan]Plan[/bold cyan]", border_style="cyan"))


def print_preloading(plan) -> None:
    items = plan.files_to_read + plan.search_queries
    if items:
        console.print(f"[dim]Preloading: {', '.join(items)}[/dim]")


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
