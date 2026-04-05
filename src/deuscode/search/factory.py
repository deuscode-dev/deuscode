from deuscode.search.base import SearchBackend


def get_search_backend(config: dict) -> SearchBackend:
    """
    Returns configured search backend.
    Defaults to DuckDuckGo if not specified.
    """
    backend = config.get("search_backend", "duckduckgo")

    if backend == "brave":
        from deuscode.search.brave import BraveSearchBackend

        api_key = config.get("brave_api_key", "")
        if not api_key:
            raise ValueError(
                "brave_api_key required in ~/.deus/config.yaml "
                "when search_backend: brave"
            )
        return BraveSearchBackend(api_key)

    from deuscode.search.duckduckgo import DuckDuckGoBackend

    return DuckDuckGoBackend()
