"""Tests for config.py."""

import pytest
import yaml

from deuscode.config import Config, load_config, CONFIG_PATH, _DEFAULTS


def test_config_dataclass_defaults():
    c = Config(base_url="http://x", api_key="k", model="m", max_tokens=100)
    assert c.auto_stop_runpod is False
    assert c.search_backend == "duckduckgo"
    assert c.brave_api_key == ""


def test_load_config_creates_default_when_missing(tmp_path, monkeypatch):
    fake_path = tmp_path / ".deus" / "config.yaml"
    monkeypatch.setattr("deuscode.config.CONFIG_PATH", fake_path)
    with pytest.raises(FileNotFoundError, match="please fill in"):
        load_config()
    assert fake_path.exists()
    data = yaml.safe_load(fake_path.read_text())
    assert data["base_url"] == _DEFAULTS["base_url"]


def test_load_config_loads_existing(tmp_path, monkeypatch):
    fake_path = tmp_path / "config.yaml"
    fake_path.write_text(yaml.dump({
        "base_url": "http://test:8000/v1",
        "api_key": "sk-test",
        "model": "test-model",
        "max_tokens": 4096,
    }))
    monkeypatch.setattr("deuscode.config.CONFIG_PATH", fake_path)
    cfg = load_config()
    assert cfg.base_url == "http://test:8000/v1"
    assert cfg.model == "test-model"
    assert cfg.max_tokens == 4096


def test_load_config_merges_defaults(tmp_path, monkeypatch):
    """Partial config gets missing keys from defaults."""
    fake_path = tmp_path / "config.yaml"
    fake_path.write_text(yaml.dump({
        "base_url": "http://x",
        "api_key": "k",
        "model": "m",
    }))
    monkeypatch.setattr("deuscode.config.CONFIG_PATH", fake_path)
    cfg = load_config()
    assert cfg.max_tokens == 8192  # from defaults
    assert cfg.search_backend == "duckduckgo"


def test_load_config_empty_yaml(tmp_path, monkeypatch):
    """Empty YAML file should use all defaults."""
    fake_path = tmp_path / "config.yaml"
    fake_path.write_text("")
    monkeypatch.setattr("deuscode.config.CONFIG_PATH", fake_path)
    cfg = load_config()
    assert cfg.base_url == _DEFAULTS["base_url"]
