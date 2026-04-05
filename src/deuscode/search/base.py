from typing import Protocol, runtime_checkable
from dataclasses import dataclass


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    full_content: str = ""


@runtime_checkable
class SearchBackend(Protocol):
    async def search(self, query: str, max_results: int = 3) -> list[SearchResult]:
        """Search and return results. Never raises — returns [] on error."""
        ...
