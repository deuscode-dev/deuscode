import sys
import asyncio
from typing import Optional

import typer

from deuscode import ui
from deuscode.agent import chat_loop
from deuscode.setup import run_setup_runpod, run_stop_runpod, run_connect_runpod

app = typer.Typer(
    name="deus",
    help="Deus - AI-powered CLI coding assistant",
    add_completion=False,
    no_args_is_help=False,
)

setup_app = typer.Typer(help="Configure Deus endpoints and models.")
app.add_typer(setup_app, name="setup")

connect_app = typer.Typer(help="Connect to an existing endpoint.")
app.add_typer(connect_app, name="connect")


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


@connect_app.callback(invoke_without_command=True)
def connect_callback(
    ctx: typer.Context,
    runpod: bool = typer.Option(False, "--runpod", help="Connect to an existing RunPod pod by ID"),
) -> None:
    if ctx.invoked_subcommand is not None:
        return
    if runpod:
        _run(run_connect_runpod())
    else:
        ui.error("Use --runpod to connect to an existing RunPod pod")


@app.command(name="ask", hidden=True)
def ask(
    prompt: str = typer.Argument(..., help="Initial prompt"),
    path: str = typer.Option(".", "--path", help="Repo path to map"),
    model: Optional[str] = typer.Option(None, "--model", help="Override config model"),
    no_map: bool = typer.Option(False, "--no-map", help="Skip repo-map"),
) -> None:
    _run(chat_loop(initial_prompt=prompt, path=path, model_override=model, no_map=no_map))


def main() -> None:
    if len(sys.argv) == 1:
        _run(chat_loop())
        return
    known_subcommands = {"setup", "connect", "ask", "--help", "-h", "--version"}
    if sys.argv[1] not in known_subcommands:
        prompt = " ".join(sys.argv[1:])
        sys.argv[1:] = ["ask", prompt]
    app()


if __name__ == "__main__":
    main()
