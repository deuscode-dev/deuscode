"""Unified interactive resource selection for setup and --resource."""

from rich.prompt import IntPrompt, Prompt
from rich.table import Table

from deuscode import ui
from deuscode.endpoints import EndpointInfo, EndpointStatus, get_endpoint_provider
from deuscode.models import MODELS, CUSTOM_MODEL_OPTION

_STATUS_ICONS = {
    EndpointStatus.READY: "[green]● Ready[/green]",
    EndpointStatus.COLD: "[yellow]○ Cold[/yellow]",
    EndpointStatus.STARTING: "[blue]◌ Starting[/blue]",
    EndpointStatus.ERROR: "[red]✗ Error[/red]",
}


async def select_resource(api_key: str) -> EndpointInfo:
    """Full interactive flow: pick type → list/create → return info."""
    endpoint_type = _pick_endpoint_type()
    provider = get_endpoint_provider(endpoint_type)
    existing = await provider.list_endpoints(api_key)
    if existing:
        return await _pick_or_create(provider, api_key, existing)
    return await _create_new(provider, api_key, endpoint_type)


def _pick_endpoint_type() -> str:
    table = Table(title="Resource type")
    table.add_column("#", style="cyan", width=3)
    table.add_column("Type", width=15)
    table.add_column("Description")
    table.add_row(
        "1", "Serverless ★",
        "Pay per query, auto-scales, no idle cost",
    )
    table.add_row(
        "2", "Pod",
        "Hourly rate, instant response, manual stop",
    )
    ui.console.print(table)
    return "serverless" if IntPrompt.ask("Pick type", default=1) == 1 else "pod"


async def _pick_or_create(
    provider, api_key: str, existing: list[EndpointInfo],
) -> EndpointInfo:
    table = Table(title="Available endpoints")
    table.add_column("#", style="cyan", width=3)
    table.add_column("ID", width=14)
    table.add_column("Name")
    table.add_column("Status", width=12)
    for i, ep in enumerate(existing, 1):
        status = await provider.get_status(api_key, ep.endpoint_id)
        table.add_row(
            str(i), ep.endpoint_id[:14],
            ep.display_name, _STATUS_ICONS.get(status, "?"),
        )
    table.add_row(str(len(existing) + 1), "[dim]New endpoint[/dim]", "", "")
    ui.console.print(table)
    choice = IntPrompt.ask("Pick endpoint", default=1)
    if choice <= len(existing):
        return existing[choice - 1]
    ep_type = existing[0].endpoint_type.value
    return await _create_new(provider, api_key, ep_type)


async def _create_new(
    provider, api_key: str, endpoint_type: str,
) -> EndpointInfo:
    model_id = _pick_model()
    kwargs: dict = {}
    if endpoint_type == "serverless":
        kwargs["gpu_ids"] = _pick_serverless_gpu(api_key)
        kwargs["quantization"] = _pick_quantization(model_id)
        kwargs["hf_token"] = _get_hf_token()
    ui.console.print(f"[dim]Creating {endpoint_type} endpoint...[/dim]")
    endpoint = await provider.create_endpoint(api_key, model_id, **kwargs)
    if endpoint.status == EndpointStatus.COLD:
        ui.warning("First query may take 30-60s (cold start).")
    return endpoint


def _pick_quantization(model_id: str) -> str | None:
    """Ask about AWQ quantization for large models (32B+)."""
    from rich.prompt import Confirm
    model = next((m for m in MODELS if m["id"] == model_id), None)
    if not model or model.get("param_count_b", 0) < 32:
        return None
    label = model.get("label", model_id.split("/")[-1])
    if Confirm.ask(
        f"Enable AWQ quantization for {label}? "
        f"(reduces VRAM ~50%, slight quality loss)",
        default=False,
    ):
        return "awq"
    return None


def _get_hf_token() -> str:
    from deuscode.config import load_config
    try:
        return load_config().hf_token
    except Exception:
        return ""


# Serverless GPU class IDs — these are NOT the same as gpuTypes.id (hardware names).
# RunPod serverless uses class identifiers; discovered from real endpoint introspection.
_SERVERLESS_GPUS = [
    {"class_id": "ADA_80_PRO",  "label": "H100 SXM / A100 Ada Pro", "vram": "80GB", "note": "★ Best"},
    {"class_id": "AMPERE_80",   "label": "A100 80GB PCIe",           "vram": "80GB", "note": "★ Recommended"},
    {"class_id": "ADA_48",      "label": "RTX A6000 Ada 48GB",       "vram": "48GB", "note": "Good"},
    {"class_id": "AMPERE_48",   "label": "A40 / A6000 48GB",         "vram": "48GB", "note": "Good"},
    {"class_id": "ADA_24",      "label": "RTX 4090 24GB",            "vram": "24GB", "note": "Small models"},
]


def _pick_serverless_gpu(_api_key: str = "") -> str:
    """Return a serverless GPU class ID string (comma-separated for multi-GPU)."""
    table = Table(title="Select GPU class for serverless workers")
    table.add_column("#", style="cyan", width=3)
    table.add_column("GPU class", width=26)
    table.add_column("VRAM", width=6)
    table.add_column("Tier", width=16)
    for i, g in enumerate(_SERVERLESS_GPUS, 1):
        table.add_row(str(i), g["label"], g["vram"], g["note"])
    ui.console.print(table)
    choice = IntPrompt.ask("Pick a GPU class", default=2)
    idx = max(0, min(choice - 1, len(_SERVERLESS_GPUS) - 1))
    return _SERVERLESS_GPUS[idx]["class_id"]


def _pick_model() -> str:
    table = Table(title="Select model")
    table.add_column("#", style="cyan", width=3)
    table.add_column("Model", width=28)
    table.add_column("VRAM", width=6)
    table.add_column("Tier")
    for i, m in enumerate(MODELS, 1):
        table.add_row(
            str(i), m["label"],
            f"{m['vram_gb']}GB", m.get("tier_label", ""),
        )
    table.add_row(str(len(MODELS) + 1), CUSTOM_MODEL_OPTION, "", "")
    ui.console.print(table)
    choice = IntPrompt.ask("Pick a model", default=3)
    if choice > len(MODELS):
        return Prompt.ask("Enter model ID")
    return MODELS[choice - 1]["id"]
