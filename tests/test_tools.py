from pathlib import Path
from unittest.mock import patch

import pytest

from deuscode.tools import read_file, write_file


@pytest.mark.asyncio
async def test_read_file_success(tmp_path):
    f = tmp_path / "hello.txt"
    f.write_text("hello world")
    result = await read_file(str(f))
    assert result == "hello world"


@pytest.mark.asyncio
async def test_read_file_missing():
    result = await read_file("/nonexistent/path/file.txt")
    assert "Error" in result


@pytest.mark.asyncio
async def test_write_file_creates_file(tmp_path):
    target = tmp_path / "output.txt"
    with patch("deuscode.ui.confirm", return_value=True):
        result = await write_file(str(target), "new content")
    assert "Written" in result
    assert target.read_text() == "new content"


@pytest.mark.asyncio
async def test_write_file_cancelled(tmp_path):
    target = tmp_path / "output.txt"
    with patch("deuscode.ui.confirm", return_value=False):
        result = await write_file(str(target), "content")
    assert "Cancelled" in result
    assert not target.exists()
