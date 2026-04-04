import ast
import re
from pathlib import Path

MAX_CHARS = 4000
SKIP_DIRS = {".git", "node_modules", "vendor", "__pycache__", ".venv", "dist", "build"}
SKIP_FILES = {".env"}


def generate_repo_map(path: str) -> str:
    root = Path(path).resolve()
    lines: list[str] = []
    _walk(root, root, lines)
    output = "\n".join(lines)
    _SUFFIX = "\n... [truncated]"
    if len(output) > MAX_CHARS:
        output = output[: MAX_CHARS - len(_SUFFIX)] + _SUFFIX
    return output


def _walk(root: Path, current: Path, lines: list[str], depth: int = 0) -> None:
    indent = "  " * depth
    for item in sorted(current.iterdir()):
        if item.name in SKIP_DIRS or item.name in SKIP_FILES:
            continue
        if item.name.startswith("."):
            continue
        if item.is_dir():
            lines.append(f"{indent}{item.name}/")
            _walk(root, item, lines, depth + 1)
        elif item.is_file():
            _append_file_entry(item, indent, lines)


def _append_file_entry(path: Path, indent: str, lines: list[str]) -> None:
    if path.suffix == ".py":
        sigs = _extract_python_signatures(path)
        lines.append(f"{indent}{path.name}")
        lines.extend(f"{indent}  {s}" for s in sigs)
    elif path.suffix == ".php":
        sigs = _extract_php_signatures(path)
        lines.append(f"{indent}{path.name}")
        lines.extend(f"{indent}  {s}" for s in sigs)
    else:
        lines.append(f"{indent}{path.name}")


def _extract_python_signatures(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except SyntaxError:
        return []
    sigs: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            sigs.append(f"class {node.name}")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = [a.arg for a in node.args.args]
            sigs.append(f"def {node.name}({', '.join(args)})")
    return sigs


def _extract_php_signatures(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    classes = re.findall(r"class\s+(\w+)", text)
    functions = re.findall(r"function\s+(\w+)\s*\(([^)]*)\)", text)
    sigs: list[str] = [f"class {c}" for c in classes]
    sigs += [f"function {n}({a.strip()})" for n, a in functions]
    return sigs
