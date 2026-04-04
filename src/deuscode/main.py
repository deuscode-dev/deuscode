import sys
import asyncio
from typing import Optional

import typer
import yaml
from rich.prompt import Confirm
from rich.table import Table

from deuscode import ui
from deuscode.agent import chat_loop
from deuscode.setup import run_setup_runpod, run_stop_runpod, run_connect_runpod
from deuscode.config import CONFIG_PATH
from deuscode.models import MODELS, get_models_by_size, CUSTOM_MODEL_OPTION

app = typer.Typer(name="deus", help="Deus - AI-powered CLI coding assistant",
                  add_completion=False, no_args_is_help=False)
setup_app = typer.Typer(help="Configure Deus endpoints and models.")
connect_app = typer.Typer(help="Connect to an existing endpoint.")
model_app = typer.Typer(help="Manage models on your RunPod instance.")
app.add_typer(setup_app, name="setup")
app.add_typer(connect_app, name="connect")
app.add_typer(model_app, name="model")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _load_config_raw() -> dict:
    if CONFIG_PATH.exists():
        return yaml.safe_load(CONFIG_PATH.read_text()) or {}
    return {}


@setup_app.callback(invoke_without_command=True)
def setup_callback(ctx: typer.Context,
                   runpod: bool = typer.Option(False, "--runpod"),
                   stop: bool = typer.Option(False, "--stop")) -> None:
    if ctx.invoked_subcommand is not None:
        return
    if stop:
        _run(run_stop_runpod())
    elif runpod:
        _run(run_setup_runpod())
    else:
        ui.error("Use --runpod to configure or --stop to stop pod")


@connect_app.callback(invoke_without_command=True)
def connect_callback(ctx: typer.Context,
                     runpod: bool = typer.Option(False, "--runpod")) -> None:
    if ctx.invoked_subcommand is not None:
        return
    if runpod:
        _run(run_connect_runpod())
    else:
        ui.error("Use --runpod to connect to an existing RunPod pod")


@model_app.command(name="list")
def model_list() -> None:
    """List downloaded models on connected pod and available catalogue."""
    from deuscode.model_manager import list_downloaded_models
    cfg = _load_config_raw()
    base_url = cfg.get("base_url", "")
    active = cfg.get("model", "")
    downloaded = _run(list_downloaded_models(base_url)) if base_url else []

    t = Table(title="Downloaded on pod")
    t.add_column("Model"); t.add_column("Active")
    for m in downloaded:
        t.add_row(m, "[yellow]★[/yellow]" if m == active else "")
    if not downloaded:
        t.add_row("[dim]none[/dim]", "")
    ui.console.print(t)

    t2 = Table(title="Available to download")
    t2.add_column("Size"); t2.add_column("Model"); t2.add_column("VRAM"); t2.add_column("Description")
    for m in MODELS:
        size = "small" if m["vram_gb"] <= 16 else ("medium" if m["vram_gb"] <= 40 else "big")
        t2.add_row(size, m["label"], f"{m['vram_gb']} GB", m["description"])
    ui.console.print(t2)


@model_app.command(name="download")
def model_download(size: Optional[str] = typer.Option(None, "--size",
                   help="Filter by size: small/medium/big/all")) -> None:
    """Download a model to your connected RunPod pod."""
    from deuscode.model_manager import list_downloaded_models, download_model, set_active_model, get_pod_storage_info
    cfg = _load_config_raw()
    pod_id = cfg.get("runpod_pod_id")
    api_key = cfg.get("runpod_api_key", "")
    base_url = cfg.get("base_url", "")
    if not pod_id:
        ui.error("No active pod. Run: deus connect --runpod")
        return

    storage = _run(get_pod_storage_info(api_key, pod_id))
    ui.print_panel(f"Pod storage: {storage['used']} used / {storage['total']} total ({storage['free']} free)")

    pool = get_models_by_size(size or "all")
    downloaded = _run(list_downloaded_models(base_url))
    t = Table(title=f"Models ({size or 'all'})")
    t.add_column("#"); t.add_column("Model"); t.add_column("VRAM"); t.add_column("Status"); t.add_column("Description")
    for i, m in enumerate(pool, 1):
        status = "[green]downloaded[/green]" if m["id"] in downloaded else "[dim]available[/dim]"
        t.add_row(str(i), m["label"], f"{m['vram_gb']} GB", status, m["description"])
    t.add_row(str(len(pool) + 1), CUSTOM_MODEL_OPTION, "", "", "")
    ui.console.print(t)

    raw = typer.prompt("Pick a model", default="1")
    idx = int(raw) - 1
    model_id = pool[idx]["id"] if idx < len(pool) else typer.prompt("Enter model ID")

    if model_id in downloaded:
        if not Confirm.ask(f"{model_id} already downloaded. Set as active?", default=False):
            return
        _run(set_active_model(model_id))
        return

    vram = next((m["vram_gb"] for m in pool if m["id"] == model_id), 0)
    if not Confirm.ask(f"Download ~{vram}GB model to pod? Continue?", default=False):
        return

    ui.print_dim(f"Downloading {model_id} to pod...")
    _run(download_model(api_key, pod_id, model_id))

    if Confirm.ask("Set as active model?", default=True):
        _run(set_active_model(model_id))


@app.command(name="ask", hidden=True)
def ask(prompt: str = typer.Argument(...),
        path: str = typer.Option(".", "--path"),
        model: Optional[str] = typer.Option(None, "--model"),
        no_map: bool = typer.Option(False, "--no-map")) -> None:
    _run(chat_loop(initial_prompt=prompt, path=path, model_override=model, no_map=no_map))


def main() -> None:
    if len(sys.argv) == 1:
        _run(chat_loop())
        return
    known_subcommands = {"setup", "connect", "model", "ask", "--help", "-h", "--version"}
    if sys.argv[1] not in known_subcommands:
        prompt = " ".join(sys.argv[1:])
        sys.argv[1:] = ["ask", prompt]
    app()


if __name__ == "__main__":
    main()
