from pathlib import Path
from dataclasses import dataclass

import yaml

CONFIG_PATH = Path.home() / ".deus" / "config.yaml"

_DEFAULTS = {
    "base_url": "https://your-runpod-endpoint/v1",
    "api_key": "your-key",
    "model": "your-model-name",
    "max_tokens": 8192,
}


@dataclass
class Config:
    base_url: str
    api_key: str
    model: str
    max_tokens: int


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
    )


def _create_default_config() -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(yaml.dump(_DEFAULTS, default_flow_style=False))
