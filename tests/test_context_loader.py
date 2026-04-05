from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from deuscode.action_plan import ActionPlan
from deuscode.context_loader import (
    _read_files_parallel,
    _search_parallel,
    format_preloaded_context,
    preload_context,
)


@pytest.mark.asyncio
async def test_read_files_parallel_reads_file(tmp_path):
    f = tmp_path / "hello.txt"
    f.write_text("hello world")
    result = await _read_files_parallel([str(f)])
    assert result[str(f)] == "hello world"


@pytest.mark.asyncio
async def test_read_files_parallel_handles_missing():
    result = await _read_files_parallel(["/does/not/exist.txt"])
    key = "/does/not/exist.txt"
    assert key in result
    assert "Error" in result[key]


@pytest.mark.asyncio
async def test_search_parallel_calls_search_web():
    with patch("deuscode.context_loader.tools.search_web", new=AsyncMock(return_value="results")):
        result = await _search_parallel(["python asyncio"])
    assert result["python asyncio"] == "results"


def test_format_preloaded_context_files():
    preloaded = {"files": {"foo.py": "print('hi')"}, "searches": {}}
    out = format_preloaded_context(preloaded)
    assert "## File: foo.py" in out
    assert "print('hi')" in out


def test_format_preloaded_context_searches():
    preloaded = {"files": {}, "searches": {"asyncio docs": "Event loop..."}}
    out = format_preloaded_context(preloaded)
    assert "## Search: asyncio docs" in out
    assert "Event loop" in out
