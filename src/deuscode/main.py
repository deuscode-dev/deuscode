import typer
from rich.console import Console

app = typer.Typer()
console = Console()


@app.command()
def main():
    """Deus - AI-powered multi-agent CLI coding assistant."""
    console.print("[bold cyan]Deus v0.1.0[/bold cyan] [dim]- Coming soon[/dim]")


if __name__ == "__main__":
    app()
