"""Tests for resource_selector."""

from deuscode.resource_selector import _pick_endpoint_type


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
