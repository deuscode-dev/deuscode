import dataclasses
import json

from deuscode.action_plan import ActionPlan, fallback_plan
from deuscode.agent import call_llm

PLANNER_MAX_TOKENS = 512

PLANNER_SYSTEM_PROMPT = """\
You are a task planner for an AI coding assistant. Analyse the user request and repository map, then produce a JSON action plan.

Respond ONLY with a valid JSON object — no markdown fences, no extra text.

Schema:
{
  "agent_instructions": "precise instructions for the coding agent",
  "files_to_read": ["paths to read before starting"],
  "search_queries": ["web search queries needed"],
  "files_to_create": ["files likely to be created or modified"],
  "expected_tools": ["read_file", "write_file", "bash"],
  "validation_steps": ["how to verify the work is correct"],
  "reasoning": "one-sentence explanation of the plan"
}
"""

_DEFAULTS: dict = {
    "agent_instructions": "",
    "files_to_read": [],
    "search_queries": [],
    "files_to_create": [],
    "expected_tools": [],
    "validation_steps": [],
    "reasoning": "",
}


async def create_action_plan(prompt: str, repo_map: str, config) -> ActionPlan:
    try:
        raw = await _call_planner_llm(prompt, repo_map, config)
        return _parse_plan(prompt, raw)
    except Exception:
        return fallback_plan(prompt)


async def _call_planner_llm(prompt: str, repo_map: str, config) -> str:
    small_config = dataclasses.replace(config, max_tokens=PLANNER_MAX_TOKENS)
    user_msg = f"Repository:\n{repo_map}\n\nTask: {prompt}"
    messages = [{"role": "user", "content": user_msg}]
    return await call_llm(PLANNER_SYSTEM_PROMPT, messages, small_config)


def _parse_plan(prompt: str, raw: str) -> ActionPlan:
    raw = raw.strip()
    # Strip accidental markdown fences
    if raw.startswith("```"):
        lines = raw.splitlines()
        end = -1 if lines[-1].strip() == "```" else len(lines)
        raw = "\n".join(lines[1:end])
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return fallback_plan(prompt)

    merged = {**_DEFAULTS, **{k: v for k, v in data.items() if k in _DEFAULTS}}
    if not merged["agent_instructions"]:
        merged["agent_instructions"] = prompt
    return ActionPlan(**merged)
