from unittest.mock import AsyncMock, patch

import httpx
import pytest

from deuscode.search.fetcher import _strip_html, fetch_content


def test_strip_html_removes_tags():
    assert _strip_html("<b>hello</b>") == "hello"


def test_strip_html_removes_scripts():
    result = _strip_html("<script>javascript</script>text")
    assert "javascript" not in result
    assert "text" in result


def test_strip_html_decodes_entities():
    assert "&" in _strip_html("&amp;")
    assert "<" in _strip_html("&lt;")
    assert ">" in _strip_html("&gt;")


@pytest.mark.asyncio
async def test_fetch_content_returns_empty_on_error():
    with patch("deuscode.search.fetcher.httpx.AsyncClient") as mock_client:
        instance = AsyncMock()
        instance.__aenter__.return_value = instance
        instance.get.side_effect = httpx.ConnectError("fail")
        mock_client.return_value = instance
        result = await fetch_content("https://example.com")
    assert result == ""
