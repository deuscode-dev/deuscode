import asyncio

from deuscode.search.base import SearchResult
from deuscode.search.fetcher import fetch_content

FETCH_FULL_CONTENT_THRESHOLD = 200


class DuckDuckGoBackend:
    """
    DuckDuckGo search backend.
    Falls back to empty list on rate limiting or any error.
    """

    async def search(self, query: str, max_results: int = 3) -> list[SearchResult]:
        try:
            raw = await self._ddg_search(query, max_results)
            return await self._enrich_results(raw)
        except Exception:
            return []

    async def _ddg_search(self, query: str, max_results: int) -> list[dict]:
        """Run DDG search in thread pool to avoid blocking event loop."""
        from duckduckgo_search import DDGS

        def _sync_search() -> list[dict]:
            with DDGS() as ddgs:
                return list(ddgs.text(query, max_results=max_results))

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _sync_search)

    async def _enrich_results(self, raw: list[dict]) -> list[SearchResult]:
        """Convert raw DDG dicts to SearchResult, fetch content if needed."""
        results = [
            SearchResult(
                title=r.get("title", ""),
                url=r.get("href", ""),
                snippet=r.get("body", ""),
            )
            for r in raw
        ]
        tasks = [self._maybe_fetch(r) for r in results]
        return list(await asyncio.gather(*tasks))

    async def _maybe_fetch(self, result: SearchResult) -> SearchResult:
        """Fetch full content only if snippet is too short to be useful."""
        if len(result.snippet) < FETCH_FULL_CONTENT_THRESHOLD and result.url:
            result.full_content = await fetch_content(result.url)
        return result
