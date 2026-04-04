from pathlib import Path

import httpx
from rich.prompt import Prompt

from deuscode import ui
from deuscode.agent import _loop, _build_system_prompt, _maybe_auto_stop
from deuscode.model_manager import list_downloaded_models, set_active_model


def parse_special_command(user_input: str) -> tuple[str, dict] | None:
    """Return (command, args) for special in-chat commands, else None."""
    stripped = user_input.strip()
    if stripped.startswith("--model"):
        parts = stripped.split()
        model_id = parts[1] if len(parts) > 1 else None
        return ("model", {"model_id": model_id})
    return None


async def handle_model_command(model_id: str | None, config) -> None:
    base_url = getattr(config, "base_url", "") or ""
    current = getattr(config, "model", "unknown")
    if not model_id:
        ui.print_panel(f"Active model: [bold]{current}[/bold]")
        try:
            downloaded = await list_downloaded_models(base_url)
            if downloaded:
                lines = "\n".join(f"{'★ ' if m == current else '  '}{m}" for m in downloaded)
                ui.print_panel(lines, title="Downloaded models")
        except Exception:
            ui.warning("Could not reach pod to list models")
        ui.print_dim("Usage: --model <model_id>  to switch active model")
        ui.print_dim("       deus model download  to download new models")
        return
    await set_active_model(model_id)
    ui.print_success(f"Switched to {model_id}")
    ui.warning("Note: vLLM needs restart to load new model")


async def run_chat_loop(
    initial_prompt: str | None = None,
    path: str = ".",
    model_override: str | None = None,
    no_map: bool = False,
) -> None:
    from deuscode.config import load_config
    try:
        config = load_config()
    except FileNotFoundError as e:
        ui.error(str(e))
        return

    model = model_override or config.model
    system_prompt = _build_system_prompt(path, no_map)
    messages: list = [{"role": "system", "content": system_prompt}]

    dir_name = Path(path).resolve().name
    if not no_map:
        ui.print_dim(f"📁 Mapped {system_prompt.count(chr(10))} files in {dir_name}")
    ui.console.print(f"[bold green]Deus[/bold green] [dim]{model}[/dim]  (Ctrl+C or empty line to exit)")
    ui.print_dim("Type --model to switch models mid-session\n")

    prompt_label = f"[bold cyan][{dir_name}] you[/bold cyan]"
    async with httpx.AsyncClient(timeout=120.0) as client:
        pending = initial_prompt
        while True:
            if pending is not None:
                user_input, pending = pending, None
                ui.console.print(f"{prompt_label}: {user_input}")
            else:
                try:
                    user_input = Prompt.ask(prompt_label)
                except (EOFError, KeyboardInterrupt):
                    ui.console.print("\n[dim]Goodbye.[/dim]")
                    break
                if not user_input.strip():
                    ui.console.print("[dim]Goodbye.[/dim]")
                    break

            special = parse_special_command(user_input)
            if special:
                cmd, args = special
                if cmd == "model":
                    await handle_model_command(args["model_id"], config)
                continue

            messages.append({"role": "user", "content": user_input})
            ui.thinking(model)
            result = await _loop(client, messages, model, config)
            ui.final_answer(result)

    await _maybe_auto_stop(config)
