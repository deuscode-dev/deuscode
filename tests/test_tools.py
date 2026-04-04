import os
from pathlib import Path
from unittest.mock import patch

import pytest

import deuscode.tools as tool_module
from deuscode.tools import read_file, write_file


@pytest.fixture(autouse=True)
def set_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(tool_module, "_CWD", tmp_path.resolve())


@pytest.mark.asyncio
async def test_read_file_success(tmp_path):
    f = tmp_path / "hello.txt"
    f.write_text("hello world")
    result = await read_file(str(f))
    assert result == "hello world"


@pytest.mark.asyncio
async def test_read_file_blocks_path_traversal(tmp_path):
    result = await read_file("../../etc/passwd")
    assert "Error" in result


@pytest.mark.asyncio
async def test_write_file_creates_file(tmp_path):
    target = tmp_path / "output.txt"
    with patch("deuscode.ui.confirm", return_value=True):
        result = await write_file(str(target), "new content")
    assert "Written" in result
    assert target.read_text() == "new content"


@pytest.mark.asyncio
async def test_write_file_rejects_outside_cwd(tmp_path):
    outside = tmp_path.parent / "evil.txt"
    result = await write_file(str(outside), "bad")
    assert "Error" in result
    assert not outside.exists()
