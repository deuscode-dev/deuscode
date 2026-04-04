import textwrap
from pathlib import Path

import pytest

from deuscode.repomap import generate_repo_map


def _make_py(tmp_path: Path, name: str, src: str) -> Path:
    f = tmp_path / name
    f.write_text(textwrap.dedent(src))
    return f


def test_generates_tree(tmp_path):
    _make_py(tmp_path, "alpha.py", "x = 1")
    _make_py(tmp_path, "beta.py", "y = 2")
    result = generate_repo_map(str(tmp_path))
    assert "alpha.py" in result
    assert "beta.py" in result
    assert len(result) > 0


def test_extracts_python_signatures(tmp_path):
    _make_py(tmp_path, "module.py", """\
        class Foo:
            pass

        def bar(x, y):
            pass

        async def baz(z):
            pass
    """)
    result = generate_repo_map(str(tmp_path))
    assert "class Foo" in result
    assert "def bar" in result
    assert "def baz" in result


def test_skips_ignored_dirs(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("gitconfig")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "pkg.js").write_text("module.exports={}")
    _make_py(tmp_path, "app.py", "pass")
    result = generate_repo_map(str(tmp_path))
    assert ".git" not in result
    assert "node_modules" not in result
    assert "app.py" in result


def test_truncates_large_repos(tmp_path):
    for i in range(60):
        src = "\n".join(f"def func_{j}(x): pass" for j in range(20))
        (tmp_path / f"module_{i}.py").write_text(src)
    result = generate_repo_map(str(tmp_path))
    assert len(result) <= 4000
    assert "truncated" in result
