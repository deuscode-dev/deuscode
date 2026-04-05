"""Tests for resource_selector."""

from deuscode.resource_selector import _pick_endpoint_type, _pick_quantization, _get_hf_token, _pick_serverless_gpu, _SERVERLESS_GPUS


def test_pick_endpoint_type_serverless(monkeypatch):
    monkeypatch.setattr(
        "deuscode.resource_selector.IntPrompt.ask", lambda *a, **kw: 1,
    )
    monkeypatch.setattr(
        "deuscode.resource_selector.ui.console.print", lambda *a, **kw: None,
    )
    assert _pick_endpoint_type() == "serverless"


def test_pick_endpoint_type_pod(monkeypatch):
    monkeypatch.setattr(
        "deuscode.resource_selector.IntPrompt.ask", lambda *a, **kw: 2,
    )
    monkeypatch.setattr(
        "deuscode.resource_selector.ui.console.print", lambda *a, **kw: None,
    )
    assert _pick_endpoint_type() == "pod"


def test_pick_quantization_skips_small_models():
    # 7B model — no AWQ prompt expected
    assert _pick_quantization("Qwen/Qwen2.5-Coder-7B-Instruct") is None


def test_pick_quantization_skips_unknown_model():
    # Custom model not in MODELS list — no AWQ prompt
    assert _pick_quantization("unknown/custom-model") is None


def test_pick_quantization_returns_awq_when_confirmed(monkeypatch):
    monkeypatch.setattr("rich.prompt.Confirm.ask", lambda *a, **kw: True)
    result = _pick_quantization("Qwen/Qwen2.5-Coder-32B-Instruct")
    assert result == "awq"


def test_pick_quantization_returns_none_when_declined(monkeypatch):
    monkeypatch.setattr("rich.prompt.Confirm.ask", lambda *a, **kw: False)
    result = _pick_quantization("Qwen/Qwen2.5-Coder-32B-Instruct")
    assert result is None


def test_get_hf_token_returns_empty_on_missing_config(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "deuscode.config.CONFIG_PATH", tmp_path / "nonexistent.yaml",
    )
    assert _get_hf_token() == ""


def test_pick_serverless_gpu_returns_class_id(monkeypatch):
    monkeypatch.setattr("deuscode.resource_selector.IntPrompt.ask", lambda *a, **kw: 2)
    monkeypatch.setattr("deuscode.resource_selector.ui.console.print", lambda *a, **kw: None)
    result = _pick_serverless_gpu()
    assert result == "AMPERE_80"


def test_pick_serverless_gpu_class_ids_are_valid():
    # All class IDs should be uppercase identifiers, not hardware names
    for g in _SERVERLESS_GPUS:
        cid = g["class_id"]
        assert cid == cid.upper(), f"Class ID should be uppercase: {cid}"
        assert " " not in cid, f"Class ID must not contain spaces: {cid}"


def test_get_hf_token_returns_token_from_config(tmp_path, monkeypatch):
    import yaml
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml.dump({
        "base_url": "http://x", "api_key": "k", "model": "m",
        "hf_token": "hf_abc123",
    }))
    monkeypatch.setattr("deuscode.config.CONFIG_PATH", cfg_path)
    assert _get_hf_token() == "hf_abc123"
