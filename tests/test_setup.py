from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
import yaml

import deuscode.setup as deus_setup
from deuscode.setup import run_stop_runpod


def _write_config(tmp_path: Path, data: dict) -> Path:
    cfg = tmp_path / "config.yaml"
    cfg.write_text(yaml.dump(data))
    return cfg


@pytest.mark.asyncio
async def test_run_stop_no_pod_id(tmp_path):
    cfg = _write_config(tmp_path, {"runpod_api_key": "key"})
    errors = []
    with patch.object(deus_setup, "CONFIG_PATH", cfg), \
         patch("deuscode.setup.ui.error", side_effect=lambda m: errors.append(m)), \
         patch("deuscode.runpod.stop_pod", new_callable=AsyncMock) as mock_stop:
        await run_stop_runpod()
    assert any("No active RunPod pod" in e for e in errors)
    mock_stop.assert_not_called()


@pytest.mark.asyncio
async def test_run_stop_success(tmp_path):
    cfg = _write_config(tmp_path, {"runpod_pod_id": "pod-123", "runpod_api_key": "key"})
    with patch.object(deus_setup, "CONFIG_PATH", cfg), \
         patch("deuscode.setup.runpod.stop_pod", new_callable=AsyncMock, return_value=True), \
         patch("deuscode.setup.ui.final_answer"), \
         patch("deuscode.setup.ui.console"):
        await run_stop_runpod()
    saved = yaml.safe_load(cfg.read_text()) or {}
    assert "runpod_pod_id" not in saved


@pytest.mark.asyncio
async def test_run_stop_failure(tmp_path):
    cfg = _write_config(tmp_path, {"runpod_pod_id": "pod-456", "runpod_api_key": "key"})
    errors = []
    with patch.object(deus_setup, "CONFIG_PATH", cfg), \
         patch("deuscode.setup.runpod.stop_pod", new_callable=AsyncMock, return_value=False), \
         patch("deuscode.setup.ui.error", side_effect=lambda m: errors.append(m)), \
         patch("deuscode.setup.ui.console"):
        await run_stop_runpod()
    saved = yaml.safe_load(cfg.read_text()) or {}
    assert saved.get("runpod_pod_id") == "pod-456"
    assert any("pod-456" in e for e in errors)
