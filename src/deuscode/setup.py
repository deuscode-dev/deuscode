import httpx
import yaml
import typer
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from deuscode import ui
from deuscode.config import CONFIG_PATH
from deuscode.models import MODELS, CUSTOM_MODEL_OPTION, _SIZE_OPTIONS, filter_by_size
from deuscode import runpod

_CLOUD_TYPES = [
    ("ALL", "Search both Community and Secure (recommended)"),
    ("COMMUNITY", "Community Cloud only — cheaper"),
    ("SECURE", "Secure Cloud only — more reliable"),
]


async def run_setup_runpod() -> None:
    api_key = _load_saved_api_key()
    if api_key:
        ui.console.print(f"[dim]Using saved RunPod API key (••••{api_key[-4:]})[/dim]")
    else:
        api_key = Prompt.ask("[bold]RunPod API key[/bold]", password=True)
    model_entry = _pick_model(_pick_size())
    model_id = model_entry["id"] if model_entry else Prompt.ask("Enter model ID")
    vram_needed = model_entry["vram_gb"] if model_entry else 0
    cloud_type = _pick_cloud_type()

    if not Confirm.ask("Start a RunPod pod? This will incur costs. Continue?", default=False):
        ui.console.print("[dim]Aborted.[/dim]")
        return

    auto_stop = Confirm.ask("Auto-stop RunPod pod after each prompt completes?", default=False)
    gpu_id = await _pick_gpu(api_key, vram_needed, cloud_type)

    while True:
        try:
            pod_id = await _start_with_spinner(api_key, gpu_id, model_id, cloud_type)
            break
        except RuntimeError as e:
            if "no longer any instances available" in str(e).lower() or \
               "supply" in str(e).lower():
                ui.warning("GPU unavailable. Please pick a different one.")
                if cloud_type != "SECURE" and Confirm.ask(
                    "Switch to Secure Cloud for better availability?", default=False
                ):
                    cloud_type = "SECURE"
                gpu_id = await _pick_gpu(api_key, vram_needed, cloud_type)
            else:
                raise

    endpoint = await _wait_with_spinner(api_key, pod_id)
    _save_config(endpoint, api_key, model_id, pod_id, auto_stop, cloud_type)
    ui.final_answer(
        f"✓ Deus is ready. Run: deus 'your prompt'\n\n"
        f"⚠ Stop your pod manually anytime: deus setup --stop\n"
        f"Current pod: {pod_id}"
    )


async def run_connect_runpod() -> None:
    api_key = _load_saved_api_key()
    if api_key:
        ui.console.print(f"[dim]Using saved RunPod API key (••••{api_key[-4:]})[/dim]")
    else:
        api_key = Prompt.ask("[bold]RunPod API key[/bold]", password=True)

    pod_id = Prompt.ask("[bold]Pod ID[/bold]")

    ui.console.print(f"[dim]Looking up pod {pod_id}...[/dim]")
    try:
        pod = await runpod.get_pod(api_key, pod_id)
    except Exception as e:
        ui.error(str(e))
        return

    status = pod.get("desiredStatus", "unknown")
    has_runtime = bool(pod.get("runtime"))
    ui.console.print(f"[dim]Pod status: {status}, runtime: {'yes' if has_runtime else 'no'}[/dim]")

    if not has_runtime:
        ui.warning("Pod has no active runtime — it may still be starting or is stopped.")
        if not Confirm.ask("Continue anyway?", default=False):
            return

    endpoint = runpod._extract_endpoint(pod) if has_runtime else ""
    if not endpoint:
        endpoint = f"https://{pod_id}-8000.proxy.runpod.net"
        ui.console.print(f"[dim]Using proxy endpoint: {endpoint}[/dim]")

    installed = await _fetch_installed_models(endpoint)
    if installed:
        ui.console.print(f"[dim]Found {len(installed)} model(s) already on this pod.[/dim]")
    else:
        ui.console.print("[dim]Could not reach vLLM — showing full catalogue.[/dim]")
    model_id = _pick_model_connect(installed, _pick_size())
    auto_stop = Confirm.ask("Auto-stop pod after each prompt completes?", default=False)

    _save_config(endpoint, api_key, model_id, pod_id, auto_stop, "ALL")
    ui.final_answer(
        f"✓ Connected to pod {pod_id}\n\n"
        f"Run: deus 'your prompt'\n"
        f"Stop anytime: deus setup --stop"
    )


async def run_stop_runpod() -> None:
    if not CONFIG_PATH.exists():
        ui.error("No active RunPod pod found in ~/.deus/config.yaml")
        return
    config_data = yaml.safe_load(CONFIG_PATH.read_text()) or {}
    pod_id = config_data.get("runpod_pod_id")
    if not pod_id:
        ui.error("No active RunPod pod found in ~/.deus/config.yaml")
        return
    api_key = config_data.get("runpod_api_key", "")
    ui.console.print(f"[dim]Stopping pod {pod_id}...[/dim]")
    try:
        success = await runpod.stop_pod(api_key, pod_id)
    except Exception as e:
        ui.error(f"Failed to stop pod {pod_id}: {e}\nStop manually at runpod.io/console")
        return
    if success:
        config_data.pop("runpod_pod_id", None)
        CONFIG_PATH.write_text(yaml.dump(config_data, default_flow_style=False))
        ui.final_answer("✓ Pod stopped. No more charges.")
    else:
        ui.error(f"Failed to stop pod {pod_id}.\nStop manually at runpod.io/console")


def _pick_size() -> str:
    table = Table(title="Model Size")
    for col in ("#", "Size", "Description"):
        table.add_column(col)
    for i, (key, desc) in enumerate(_SIZE_OPTIONS, 1):
        table.add_row(str(i), key, desc)
    ui.console.print(table)
    idx = IntPrompt.ask("Pick a size filter", default=1) - 1
    return _SIZE_OPTIONS[idx][0]


def _pick_model(size_filter: str = "ALL") -> dict | None:
    pool = filter_by_size(MODELS, size_filter)
    table = Table(title="Available Models" + (f" ({size_filter})" if size_filter != "ALL" else ""))
    for col in ("#", "Model", "Category", "VRAM", "Description"):
        table.add_column(col)
    ordered = sorted(pool, key=lambda m: (0 if m["category"] == "Coding" else 1, m["label"]))
    for i, m in enumerate(ordered, 1):
        table.add_row(str(i), m["label"], m["category"], f"{m['vram_gb']} GB", m["description"])
    table.add_row(str(len(ordered) + 1), CUSTOM_MODEL_OPTION, "", "", "")
    ui.console.print(table)
    idx = int(Prompt.ask("Pick a model", default="1")) - 1
    return ordered[idx] if idx < len(ordered) else None


async def _fetch_installed_models(endpoint: str) -> list[str]:
    """Return model IDs currently served by the vLLM instance, or [] on any error."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{endpoint.rstrip('/')}/v1/models")
            if r.status_code == 200:
                return [m["id"] for m in r.json().get("data", [])]
    except Exception:
        pass
    return []


def _pick_model_connect(installed: list[str], size_filter: str = "ALL") -> str:
    """Model picker for connect flow: installed models first, then the catalogue."""
    known = {m["id"]: m for m in MODELS}
    pool = filter_by_size(MODELS, size_filter)
    pool_ids = {m["id"] for m in pool}

    table = Table(title="Select Model")
    for col in ("#", "Model", "Category", "VRAM", "Status"):
        table.add_column(col)

    rows: list[str] = []  # model IDs in display order

    # ── installed first ───────────────────────────────────────────────────
    for mid in installed:
        m = known.get(mid)
        label = m["label"] if m else mid
        category = m["category"] if m else "?"
        vram = f"{m['vram_gb']} GB" if m else "?"
        table.add_row(str(len(rows) + 1), label, category, vram, "[green]installed[/green]")
        rows.append(mid)

    # ── catalogue (skip already listed) ──────────────────────────────────
    ordered = sorted(pool, key=lambda m: (0 if m["category"] == "Coding" else 1, m["label"]))
    for m in ordered:
        if m["id"] in rows:
            continue
        table.add_row(str(len(rows) + 1), m["label"], m["category"], f"{m['vram_gb']} GB", "[dim]download[/dim]")
        rows.append(m["id"])

    # ── custom entry ──────────────────────────────────────────────────────
    custom_idx = len(rows) + 1
    table.add_row(str(custom_idx), CUSTOM_MODEL_OPTION, "", "", "")

    ui.console.print(table)
    default = "1"
    idx = int(Prompt.ask("Pick a model", default=default)) - 1
    if idx >= len(rows):
        return Prompt.ask("Enter model ID")
    return rows[idx]


def _load_saved_api_key() -> str:
    if not CONFIG_PATH.exists():
        return ""
    return (yaml.safe_load(CONFIG_PATH.read_text()) or {}).get("runpod_api_key", "")


def _pick_cloud_type() -> str:
    table = Table(title="Cloud Type")
    for col in ("#", "Type", "Description"):
        table.add_column(col)
    for i, (name, desc) in enumerate(_CLOUD_TYPES, 1):
        table.add_row(str(i), name, desc)
    ui.console.print(table)
    idx = IntPrompt.ask("Pick a cloud type", default=1) - 1
    return _CLOUD_TYPES[idx][0]


async def _pick_gpu(api_key: str, min_vram: int, cloud_type: str) -> str:
    gpus = await runpod.get_gpu_types(api_key)
    filtered = [g for g in gpus if (g.get("memoryInGb") or 0) >= min_vram]
    if not filtered:
        ui.error("No GPUs currently available on RunPod. Try again later.")
        raise typer.Exit(1)
    _show_gpu_table(filtered)
    choice = IntPrompt.ask("Pick a GPU", default=1)
    return filtered[choice - 1]["id"]


def _show_gpu_table(gpus: list[dict]) -> None:
    table = Table(title="Available GPUs")
    for col in ("#", "GPU Name", "VRAM", "Live Price/hr", "Community/hr", "Secure/hr"):
        table.add_column(col)
    for i, g in enumerate(gpus, 1):
        live = (g.get("lowestPrice") or {}).get("uninterruptablePrice")
        table.add_row(
            str(i),
            g.get("displayName", ""),
            f"{g.get('memoryInGb', '?')} GB",
            f"${live}" if live is not None else "N/A",
            f"${g.get('communityPrice', '?')}",
            f"${g.get('securePrice', '?')}",
        )
    ui.console.print(table)


async def _start_with_spinner(api_key: str, gpu_id: str, model_id: str, cloud_type: str) -> str:
    ui.console.print("[dim]Starting pod...[/dim]")
    pod = await runpod.start_pod(api_key, gpu_id, model_id, cloud_type)
    if not pod or "id" not in pod:
        raise RuntimeError(f"Pod start failed: {pod}")
    return pod["id"]


async def _wait_with_spinner(api_key: str, pod_id: str) -> str:
    state = {"renderable": _status_panel(pod_id, "init", 0), "elapsed": 0}
    with Live(state["renderable"], console=ui.console, refresh_per_second=1) as live:
        def on_pod_poll(pod, elapsed):
            state["elapsed"] = elapsed
            state["renderable"] = _status_panel(pod_id, "port", elapsed)
            live.update(state["renderable"])

        endpoint = await runpod.wait_for_ready(api_key, pod_id, on_poll=on_pod_poll)

        def on_health_poll(elapsed):
            state["elapsed"] += 10
            state["renderable"] = _status_panel(pod_id, "health", state["elapsed"])
            live.update(state["renderable"])

        await runpod.wait_for_health(endpoint, on_poll=on_health_poll)
        state["renderable"] = _status_panel(pod_id, "ready", state["elapsed"])
        live.update(state["renderable"])
    return endpoint


def _status_panel(pod_id: str, phase: str, elapsed: int) -> Panel:
    mins, secs = divmod(elapsed, 60)
    status_map = {
        "init":   ("initializing",       "yellow"),
        "port":   ("port open",          "yellow"),
        "health": ("loading model...",   "yellow"),
        "ready":  ("vLLM ready",         "green"),
    }
    display_status, color = status_map.get(phase, ("initializing", "yellow"))
    phase_msg = _start_phase(phase, elapsed)
    text = Text()
    text.append("Pod:     ", style="dim")
    text.append(f"{pod_id}\n", style="cyan")
    text.append("Status:  ", style="dim")
    text.append(f"{display_status}\n", style=color)
    text.append("Elapsed: ", style="dim")
    text.append(f"{mins:02d}:{secs:02d}\n", style="white")
    text.append(f"\n{phase_msg}", style="dim")
    return Panel(text, title="[bold]Starting vLLM on RunPod[/bold]", border_style="yellow")


def _start_phase(phase: str, elapsed: int) -> str:
    if phase == "ready":
        return "✓ vLLM is up and responding."
    if phase == "health":
        return "⏳ Loading model weights into GPU memory..."
    if elapsed < 30:
        return "⏳ Pulling Docker image..."
    if elapsed < 90:
        return "⏳ Starting vLLM process..."
    return "⏳ Loading model weights into GPU memory (large models take 3-5 min)..."


def _save_config(endpoint: str, api_key: str, model_id: str, pod_id: str, auto_stop: bool, cloud_type: str) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing = yaml.safe_load(CONFIG_PATH.read_text()) if CONFIG_PATH.exists() else {}
    existing.update({
        "base_url": f"{endpoint}/v1",
        "api_key": api_key,
        "model": model_id,
        "runpod_pod_id": pod_id,
        "runpod_api_key": api_key,
        "runpod_cloud_type": cloud_type,
        "auto_stop_runpod": auto_stop,
    })
    CONFIG_PATH.write_text(yaml.dump(existing, default_flow_style=False))
