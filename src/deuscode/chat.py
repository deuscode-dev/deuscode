from pathlib import Path

from rich.prompt import Prompt

from deuscode import ui
from deuscode.agent import _maybe_auto_stop
from deuscode.model_manager import list_downloaded_models, set_active_model


def parse_special_command(user_input: str) -> tuple[str, dict] | None:
    """Return (command, args) for special in-chat commands, else None."""
    stripped = user_input.strip()
    if stripped.startswith("--model"):
        parts = stripped.split()
        model_id = parts[1] if len(parts) > 1 else None
        return ("model", {"model_id": model_id})
    if stripped == "--resource":
        return ("resource", {})
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


async def handle_resource_command(config) -> "Config":
    """Show current resource status, optionally switch."""
    from deuscode.endpoints import get_endpoint_provider, EndpointStatus
    provider = get_endpoint_provider(config.endpoint_type)
    status = await provider.get_status(config.api_key, config.endpoint_id)
    icons = {
        EndpointStatus.READY: "[green]● Ready[/green]",
        EndpointStatus.COLD: "[yellow]○ Cold[/yellow]",
        EndpointStatus.ERROR: "[red]✗ Error[/red]",
    }
    ui.print_panel(
        f"Type:   {config.endpoint_type}\n"
        f"ID:     {config.endpoint_id or 'not set'}\n"
        f"Model:  {config.model.split('/')[-1]}\n"
        f"Status: {icons.get(status, '?')}",
        title="Current resource",
    )
    from rich.prompt import Confirm
    if not Confirm.ask("Switch resource?", default=False):
        return config
    try:
        from deuscode.resource_selector import select_resource
        from deuscode.config import save_endpoint, load_config
        endpoint = await select_resource(config.api_key)
        save_endpoint(endpoint, config.api_key)
        return load_config()
    except NotImplementedError:
        ui.warning("New pod creation requires: deus setup --runpod")
        return config


async def _process_prompt(user_input: str, path: str, no_map: bool, config) -> str:
    """Full planning pipeline: detect → plan → preload → execute."""
    from deuscode.complexity import detect_complexity, Complexity
    from deuscode.action_plan import simple_plan
    from deuscode.planner import create_action_plan
    from deuscode.context_loader import preload_context
    from deuscode.agent import run_agent
    from deuscode.repomap import generate_repo_map

    repo_map = "" if no_map else generate_repo_map(path)
    complexity = detect_complexity(user_input)

    if complexity == Complexity.SIMPLE:
        plan = simple_plan(user_input)
    else:
        ui.print_planning()
        plan = await create_action_plan(user_input, repo_map, config)
        ui.print_action_plan(plan)

    if plan.files_to_read or plan.search_queries:
        ui.print_preloading(plan)
        preloaded = await preload_context(plan)
    else:
        preloaded = {"files": {}, "searches": {}}

    return await run_agent(plan, preloaded, repo_map, config, path)


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

    if model_override:
        import dataclasses
        config = dataclasses.replace(config, model=model_override)

    dir_name = Path(path).resolve().name
    ui.console.print(
        f"[bold green]Deus[/bold green] [dim]{config.model}[/dim]  (Ctrl+C or empty line to exit)"
    )
    ui.print_dim("Type --model to switch models, --resource to switch endpoints\n")

    prompt_label = f"[bold cyan][{dir_name}] you[/bold cyan]"
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
            elif cmd == "resource":
                config = await handle_resource_command(config)
            continue

        result = await _process_prompt(user_input, path, no_map, config)
        ui.final_answer(result)

    await _maybe_auto_stop(config)
