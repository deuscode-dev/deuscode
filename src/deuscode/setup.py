import asyncio

import yaml
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.live import Live
from rich.spinner import Spinner
from rich.text import Text

from deuscode import ui
from deuscode.config import CONFIG_PATH
from deuscode.models import MODELS, CUSTOM_MODEL_OPTION
from deuscode import runpod


async def run_setup_runpod() -> None:
    api_key = Prompt.ask("[bold]RunPod API key[/bold]", password=True)
    model_entry = _pick_model()
    model_id = model_entry["id"] if model_entry else Prompt.ask("Enter model ID")
    vram_needed = model_entry["vram_gb"] if model_entry else 0

    ui.console.print(f"\n[dim]Fetching GPUs with ≥{vram_needed} GB VRAM...[/dim]")
    gpus = await runpod.get_gpu_types(api_key)
    filtered = [g for g in gpus if (g.get("memoryInGb") or 0) >= vram_needed]
    gpu = _pick_gpu(filtered)

    price = gpu.get("securePrice") or "?"
    if not Confirm.ask(f"This will cost ~${price}/hr. Continue?", default=False):
        ui.console.print("[dim]Aborted.[/dim]")
        return

    pod_id = await _start_with_spinner(api_key, gpu["id"], model_id)
    endpoint = await _wait_with_spinner(api_key, pod_id)
    _save_config(endpoint, api_key, model_id, pod_id)
    ui.final_answer(f"✓ Deus is ready. Run: deus 'your prompt'")


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


def _pick_gpu(gpus: list[dict]) -> dict:
    table = Table(title="Available GPUs")
    for col in ("#", "GPU Name", "VRAM", "Price/hr"):
        table.add_column(col)
    for i, g in enumerate(gpus, 1):
        table.add_row(str(i), g.get("displayName", ""), f"{g.get('memoryInGb', '?')} GB", f"${g.get('securePrice', '?')}")
    ui.console.print(table)
    idx = int(Prompt.ask("Pick a GPU", default="1")) - 1
    return gpus[idx]


async def _start_with_spinner(api_key: str, gpu_id: str, model_id: str) -> str:
    ui.console.print("[dim]Starting pod...[/dim]")
    pod = await runpod.start_pod(api_key, gpu_id, model_id)
    return pod["id"]


async def _wait_with_spinner(api_key: str, pod_id: str) -> str:
    ui.console.print("[dim]Waiting for vLLM to be ready (this takes 2-3 min)...[/dim]")
    return await runpod.wait_for_ready(api_key, pod_id)


def _save_config(endpoint: str, api_key: str, model_id: str, pod_id: str) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing = yaml.safe_load(CONFIG_PATH.read_text()) if CONFIG_PATH.exists() else {}
    existing.update({
        "base_url": f"{endpoint}/v1",
        "api_key": api_key,
        "model": model_id,
        "runpod_pod_id": pod_id,
        "runpod_api_key": api_key,
    })
    CONFIG_PATH.write_text(yaml.dump(existing, default_flow_style=False))
