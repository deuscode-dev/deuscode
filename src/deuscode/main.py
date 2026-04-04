import asyncio
from typing import Optional

import typer

from deuscode import ui
from deuscode.config import load_config
from deuscode import agent
from deuscode.setup import run_setup_runpod

app = typer.Typer(invoke_without_command=True, help="Deus - AI-powered CLI coding assistant")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    prompt: Optional[str] = typer.Argument(None, help="What to ask Deus"),
    path: str = typer.Option(".", "--path", help="Repo path to map"),
    model: Optional[str] = typer.Option(None, "--model", help="Override config model"),
    no_map: bool = typer.Option(False, "--no-map", help="Skip repo-map generation"),
) -> None:
    if ctx.invoked_subcommand is not None:
        return
    if not prompt:
        ui.error("Provide a prompt or use a subcommand (e.g. deus setup --runpod)")
        raise typer.Exit(1)
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


@app.command()
def setup(
    runpod: bool = typer.Option(False, "--runpod", help="Configure a RunPod GPU endpoint"),
) -> None:
    """Configure Deus endpoints and models."""
    if not runpod:
        ui.error("Specify --runpod to configure a RunPod endpoint")
        raise typer.Exit(1)
    asyncio.run(run_setup_runpod())


if __name__ == "__main__":
    app()
