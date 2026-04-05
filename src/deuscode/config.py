from dataclasses import dataclass
from pathlib import Path

import yaml

CONFIG_PATH = Path.home() / ".deus" / "config.yaml"

_DEFAULTS = {
    "base_url": "https://your-runpod-endpoint/v1",
    "api_key": "your-key",
    "model": "your-model-name",
    "max_tokens": 8192,
    "auto_stop_runpod": False,
    "search_backend": "duckduckgo",
    "brave_api_key": "",
    "endpoint_type": "pod",
    "endpoint_id": "",
    "hf_token": "",
}


@dataclass
class Config:
    base_url: str
    api_key: str
    model: str
    max_tokens: int
    auto_stop_runpod: bool = False
    search_backend: str = "duckduckgo"
    brave_api_key: str = ""
    endpoint_type: str = "pod"
    endpoint_id: str = ""
    hf_token: str = ""


def load_config() -> Config:
    if not CONFIG_PATH.exists():
        _create_default_config()
        raise FileNotFoundError(
            f"Config created at {CONFIG_PATH} — please fill in your endpoint details."
        )
    data = yaml.safe_load(CONFIG_PATH.read_text()) or {}
    merged = {**_DEFAULTS, **data}
    return Config(
        base_url=merged["base_url"],
        api_key=merged["api_key"],
        model=merged["model"],
        max_tokens=int(merged["max_tokens"]),
        auto_stop_runpod=bool(merged.get("auto_stop_runpod", False)),
        search_backend=merged.get("search_backend", "duckduckgo"),
        brave_api_key=merged.get("brave_api_key", ""),
        endpoint_type=merged.get("endpoint_type", "pod"),
        endpoint_id=merged.get("endpoint_id", ""),
        hf_token=merged.get("hf_token", ""),
    )


def save_endpoint(info, api_key: str = "") -> None:
    """Save endpoint info to config. Preserves existing fields."""
    existing = {}
    if CONFIG_PATH.exists():
        existing = yaml.safe_load(CONFIG_PATH.read_text()) or {}
    existing.update({
        "endpoint_type": info.endpoint_type.value,
        "endpoint_id": info.endpoint_id,
        "base_url": info.base_url,
        "model": info.model_id,
    })
    if api_key:
        existing["api_key"] = api_key
        existing["runpod_api_key"] = api_key
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(yaml.dump(existing, default_flow_style=False))


def _create_default_config() -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(yaml.dump(_DEFAULTS, default_flow_style=False))
