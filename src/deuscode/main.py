import sys
import asyncio
from typing import Optional

import typer

from deuscode import ui
from deuscode.agent import run_agent, chat_loop
from deuscode.setup import run_setup_runpod, run_stop_runpod

app = typer.Typer(
    name="deus",
    help="Deus - AI-powered CLI coding assistant",
    add_completion=False,
    no_args_is_help=False,
)

setup_app = typer.Typer(help="Configure Deus endpoints and models.")
app.add_typer(setup_app, name="setup")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@setup_app.callback(invoke_without_command=True)
def setup_callback(
    ctx: typer.Context,
    runpod: bool = typer.Option(False, "--runpod", help="Configure RunPod GPU endpoint"),
    stop: bool = typer.Option(False, "--stop", help="Stop the current RunPod pod"),
) -> None:
    if ctx.invoked_subcommand is not None:
        return
    if stop:
        _run(run_stop_runpod())
    elif runpod:
        _run(run_setup_runpod())
    else:
        ui.error("Use --runpod to configure or --stop to stop pod")


@app.command(name="ask", hidden=True)
def ask(
    prompt: str = typer.Argument(..., help="What to ask Deus"),
    path: str = typer.Option(".", "--path", help="Repo path to map"),
    model: Optional[str] = typer.Option(None, "--model", help="Override config model"),
    no_map: bool = typer.Option(False, "--no-map", help="Skip repo-map"),
) -> None:
    _run(run_agent(prompt, path, model, no_map))


def main() -> None:
    if len(sys.argv) == 1:
        _run(chat_loop())
        return
    known_subcommands = {"setup", "ask", "--help", "-h", "--version"}
    if sys.argv[1] not in known_subcommands:
        prompt = " ".join(sys.argv[1:])
        sys.argv[1:] = ["ask", prompt]
    app()


if __name__ == "__main__":
    main()
