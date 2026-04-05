import pytest

from deuscode.search.factory import get_search_backend
from deuscode.search.brave import BraveSearchBackend
from deuscode.search.duckduckgo import DuckDuckGoBackend


def test_default_backend_is_duckduckgo():
    backend = get_search_backend({})
    assert isinstance(backend, DuckDuckGoBackend)


def test_brave_backend_requires_api_key():
    with pytest.raises(ValueError, match="brave_api_key required"):
        get_search_backend({"search_backend": "brave"})


def test_brave_backend_with_key():
    backend = get_search_backend({
        "search_backend": "brave",
        "brave_api_key": "test-key-123",
    })
    assert isinstance(backend, BraveSearchBackend)
    assert backend.api_key == "test-key-123"
