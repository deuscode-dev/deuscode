from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm

console = Console()


def thinking(model: str) -> None:
    console.print(f"[dim]Deus is thinking... ({model})[/dim]")


def tool_call(name: str, args: dict) -> None:
    args_str = ", ".join(f"{k}={v!r}" for k, v in args.items())
    console.print(f"[yellow]⚡ Calling: {name}({args_str})[/yellow]")


def tool_result(text: str) -> None:
    console.print(f"[dim grey]{text}[/dim grey]")


def final_answer(text: str) -> None:
    console.print(Panel(text, title="[bold cyan]Deus[/bold cyan]", border_style="cyan"))


def error(text: str) -> None:
    console.print(Panel(text, title="[bold red]Error[/bold red]", border_style="red"))


def warning(text: str) -> None:
    console.print(f"[bold yellow]⚠ {text}[/bold yellow]")


def confirm(prompt: str) -> bool:
    return Confirm.ask(prompt)
