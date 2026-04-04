import yaml
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.table import Table

from deuscode import ui
from deuscode.config import CONFIG_PATH
from deuscode.models import MODELS, CUSTOM_MODEL_OPTION
from deuscode import runpod

_CLOUD_TYPES = [
    ("COMMUNITY", "Cheaper, less reliable availability"),
    ("SECURE", "More expensive, better availability"),
]


async def run_setup_runpod() -> None:
    api_key = Prompt.ask("[bold]RunPod API key[/bold]", password=True)
    model_entry = _pick_model()
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


def _pick_model() -> dict | None:
    table = Table(title="Available Models")
    for col in ("#", "Model", "Category", "VRAM", "Description"):
        table.add_column(col)
    ordered = sorted(MODELS, key=lambda m: (0 if m["category"] == "Coding" else 1, m["label"]))
    for i, m in enumerate(ordered, 1):
        table.add_row(str(i), m["label"], m["category"], f"{m['vram_gb']} GB", m["description"])
    table.add_row(str(len(ordered) + 1), CUSTOM_MODEL_OPTION, "", "", "")
    ui.console.print(table)
    idx = int(Prompt.ask("Pick a model", default="1")) - 1
    return ordered[idx] if idx < len(ordered) else None


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
    _show_gpu_table(filtered)
    choice = IntPrompt.ask("Pick a GPU", default=1)
    return filtered[choice - 1]["id"]


def _show_gpu_table(gpus: list[dict]) -> None:
    table = Table(title="Available GPUs")
    for col in ("#", "GPU Name", "VRAM", "Community/hr", "Secure/hr"):
        table.add_column(col)
    for i, g in enumerate(gpus, 1):
        table.add_row(
            str(i),
            g.get("displayName", ""),
            f"{g.get('memoryInGb', '?')} GB",
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
    ui.console.print("[dim]Waiting for vLLM to be ready (this takes 2-3 min)...[/dim]")
    return await runpod.wait_for_ready(api_key, pod_id)


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
