from unittest.mock import AsyncMock, patch

import pytest

from deuscode.search.base import SearchResult
from deuscode.search.duckduckgo import DuckDuckGoBackend


@pytest.mark.asyncio
async def test_search_returns_empty_on_ddg_error():
    backend = DuckDuckGoBackend()
    with patch.object(backend, "_ddg_search", side_effect=Exception("fail")):
        results = await backend.search("test query")
    assert results == []


@pytest.mark.asyncio
async def test_enrich_skips_fetch_for_long_snippets():
    backend = DuckDuckGoBackend()
    long_snippet = "x" * 300
    raw = [{"title": "Test", "href": "https://example.com", "body": long_snippet}]
    with patch("deuscode.search.duckduckgo.fetch_content", new_callable=AsyncMock) as mock_fetch:
        results = await backend._enrich_results(raw)
    mock_fetch.assert_not_called()
    assert results[0].full_content == ""


def test_search_result_dataclass():
    r = SearchResult(title="T", url="U", snippet="S")
    assert r.title == "T"
    assert r.url == "U"
    assert r.snippet == "S"
    assert r.full_content == ""
