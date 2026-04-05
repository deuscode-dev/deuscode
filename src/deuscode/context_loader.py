import asyncio
from pathlib import Path

from deuscode import tools


async def preload_context(plan) -> dict:
    """Parallel-fetch files and web searches declared in an ActionPlan."""
    files, searches = await asyncio.gather(
        _read_files_parallel(plan.files_to_read),
        _search_parallel(plan.search_queries),
    )
    return {"files": files, "searches": searches}


async def _read_files_parallel(paths: list[str]) -> dict[str, str]:
    if not paths:
        return {}
    results = await asyncio.gather(
        *[asyncio.to_thread(Path(p).read_text, encoding="utf-8", errors="replace") for p in paths],
        return_exceptions=True,
    )
    return {
        p: (r if isinstance(r, str) else f"Error reading {p}: {r}")
        for p, r in zip(paths, results)
    }


async def _search_parallel(queries: list[str]) -> dict[str, str]:
    if not queries:
        return {}
    results = await asyncio.gather(
        *[tools.search_web(q) for q in queries],
        return_exceptions=True,
    )
    return {
        q: (r if isinstance(r, str) else f"Error searching '{q}': {r}")
        for q, r in zip(queries, results)
    }


def format_preloaded_context(preloaded: dict) -> str:
    parts = []
    for path, content in preloaded.get("files", {}).items():
        parts.append(f"## File: {path}\n```\n{content}\n```")
    for query, result in preloaded.get("searches", {}).items():
        parts.append(f"## Search: {query}\n{result}")
    return "\n\n".join(parts)
