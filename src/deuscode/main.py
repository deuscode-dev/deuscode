import asyncio
from typing import Optional

import typer

from deuscode import ui
from deuscode.config import load_config
from deuscode import agent

app = typer.Typer(help="Deus - AI-powered CLI coding assistant")


@app.command()
def main(
    prompt: str = typer.Argument(..., help="What to ask Deus"),
    path: str = typer.Option(".", "--path", help="Repo path to map"),
    model: Optional[str] = typer.Option(None, "--model", help="Override config model"),
    no_map: bool = typer.Option(False, "--no-map", help="Skip repo-map generation"),
) -> None:
    try:
        config = load_config()
    except FileNotFoundError as e:
        ui.error(str(e))
        raise typer.Exit(1)

    try:
        result = asyncio.run(agent.run(prompt, config, path=path, model_override=model, no_map=no_map))
        ui.final_answer(result)
    except Exception as e:
        ui.error(str(e))
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
