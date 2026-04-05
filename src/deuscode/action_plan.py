from dataclasses import dataclass, field


@dataclass
class ActionPlan:
    agent_instructions: str
    files_to_read: list[str] = field(default_factory=list)
    search_queries: list[str] = field(default_factory=list)
    files_to_create: list[str] = field(default_factory=list)
    expected_tools: list[str] = field(default_factory=list)
    validation_steps: list[str] = field(default_factory=list)
    reasoning: str = ""


def simple_plan(prompt: str) -> ActionPlan:
    return ActionPlan(
        agent_instructions=prompt,
        reasoning="Simple prompt — executing directly",
    )


def fallback_plan(prompt: str) -> ActionPlan:
    return ActionPlan(
        agent_instructions=prompt,
        reasoning="Planner unavailable — executing directly",
    )
