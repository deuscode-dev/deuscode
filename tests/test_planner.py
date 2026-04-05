import json
from unittest.mock import AsyncMock, patch

import pytest

from deuscode.action_plan import ActionPlan
from deuscode.planner import _parse_plan, create_action_plan


def test_parse_plan_valid_json():
    data = {
        "agent_instructions": "Add a cache",
        "files_to_read": ["src/app.py"],
        "search_queries": [],
        "files_to_create": ["src/cache.py"],
        "expected_tools": ["write_file"],
        "validation_steps": ["run tests"],
        "reasoning": "Needs a new module",
    }
    plan = _parse_plan("original prompt", json.dumps(data))
    assert isinstance(plan, ActionPlan)
    assert plan.agent_instructions == "Add a cache"
    assert plan.files_to_read == ["src/app.py"]
    assert plan.reasoning == "Needs a new module"


def test_parse_plan_missing_fields_defaults():
    data = {"agent_instructions": "Do something"}
    plan = _parse_plan("original", json.dumps(data))
    assert plan.files_to_read == []
    assert plan.search_queries == []
    assert plan.validation_steps == []


def test_parse_plan_invalid_json_returns_fallback():
    plan = _parse_plan("original prompt", "not json at all")
    assert plan.agent_instructions == "original prompt"
    assert "directly" in plan.reasoning.lower() or "fallback" in plan.reasoning.lower()


@pytest.mark.asyncio
async def test_create_action_plan_calls_llm():
    from deuscode.config import Config
    config = Config(base_url="http://localhost", api_key="k", model="m", max_tokens=1024)
    response = json.dumps({
        "agent_instructions": "Build a thing",
        "files_to_read": [],
        "search_queries": [],
        "files_to_create": ["thing.py"],
        "expected_tools": ["write_file"],
        "validation_steps": [],
        "reasoning": "Need to build it",
    })
    with patch("deuscode.planner.call_llm", new=AsyncMock(return_value=response)):
        plan = await create_action_plan("Build a thing", "repo map here", config)
    assert plan.agent_instructions == "Build a thing"
    assert plan.files_to_create == ["thing.py"]
