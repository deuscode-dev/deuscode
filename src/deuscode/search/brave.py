from deuscode.search.base import SearchResult


class BraveSearchBackend:
    """
    Brave Search API backend.
    Requires brave_api_key in config.
    Not yet implemented — raises NotImplementedError.
    """

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def search(self, query: str, max_results: int = 3) -> list[SearchResult]:
        raise NotImplementedError(
            "Brave Search not yet implemented. "
            "Use search_backend: duckduckgo in config."
        )
