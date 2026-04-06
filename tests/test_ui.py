"""Tests for ui.py display helpers."""

from deuscode.ui import print_worker_status, print_cold_start_warning


def test_print_worker_status_initializing(capsys):
    health = {
        "workers": {"initializing": 1, "ready": 0, "running": 0, "idle": 0},
        "jobs": {"inQueue": 0},
    }
    # Should not raise
    print_worker_status(health, elapsed=15)


def test_print_worker_status_empty(capsys):
    # Empty dict — should show "waiting..." without raising
    print_worker_status({}, elapsed=0)


def test_print_worker_status_all_fields(capsys):
    health = {
        "workers": {"initializing": 1, "ready": 2, "running": 1, "idle": 3},
        "jobs": {"inQueue": 5},
    }
    # Should not raise
    print_worker_status(health, elapsed=30)


def test_print_cold_start_warning_known_model(capsys):
    # Should not raise for a known model
    print_cold_start_warning("Qwen/Qwen2.5-Coder-7B-Instruct")


def test_print_cold_start_warning_unknown_model(capsys):
    # Should not raise for an unknown/custom model
    print_cold_start_warning("unknown/custom-model-100B")
