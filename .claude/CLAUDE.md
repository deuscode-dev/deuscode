# Deus CLI - Project Context

## What is this
AI-powered multi-agent CLI coding assistant for local/cloud LLMs.
PyPI: deuscode | Command: deus | License: AGPL-3.0

## Tech stack
- Python 3.12, Typer, Rich, httpx, asyncio
- PyPI package: pip install deuscode
- RunPod/vLLM for LLM backend

## Code standards
- SOLID, KISS, DRY, YAGNI strictly
- Max 30 lines per function, 150 lines per file
- All new code needs tests (pytest)
- No new dependencies without strong justification

## Project structure
src/deuscode/
├── agent.py        ← LLM loop
├── planner.py      ← task planning
├── complexity.py   ← simple/complex detection
├── action_plan.py  ← ActionPlan dataclass
├── context_loader.py ← parallel pre-loading
├── chat.py         ← interactive loop
├── config.py       ← config management
├── repomap.py      ← repo scanning
├── tools.py        ← agent tools
├── ui.py           ← all Rich output
├── main.py         ← CLI entry point
├── models.py       ← curated model list
├── runpod.py       ← RunPod API client
├── setup.py        ← setup wizard
├── model_manager.py ← model download/switch
└── search/         ← pluggable search backends

## Current version
Check pyproject.toml for current version.

## Run tests
pytest tests/ -v

## Release process
rm -rf dist/ && python -m build && python -m twine upload dist/*
