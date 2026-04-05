from deuscode.action_plan import ActionPlan, simple_plan, fallback_plan


def test_simple_plan_contains_prompt():
    plan = simple_plan("write a function")
    assert plan.agent_instructions == "write a function"


def test_simple_plan_empty_lists():
    plan = simple_plan("write a function")
    assert plan.files_to_read == []
    assert plan.search_queries == []
    assert plan.files_to_create == []


def test_fallback_plan_contains_prompt():
    plan = fallback_plan("do something complex")
    assert plan.agent_instructions == "do something complex"


def test_fallback_plan_has_reasoning():
    plan = fallback_plan("do something complex")
    assert plan.reasoning != ""
    assert "directly" in plan.reasoning.lower() or "fallback" in plan.reasoning.lower()
