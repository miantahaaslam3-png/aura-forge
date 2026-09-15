#!/usr/bin/env python3
"""Fix keyword-argument mismatches left by the rebrand sweep.

The sweep renamed function PARAMETERS (hermes_home -> aura_forge_home) but
left many CALL SITES using the old keyword, which crashes at runtime with
`TypeError: got an unexpected keyword argument 'hermes_home'`.

This uses the same resolution logic as check_call_kwargs.py: it resolves
each flagged direct call and rewrites ONLY the offending `hermes_home=`
keyword token to `aura_forge_home=` at its exact position.
"""
import ast
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {"venv", ".venv", "node_modules", ".git", "dist", "build",
             "release", "web_dist", "target", "tmp_extract", "__pycache__",
             ".pytest_cache", ".next"}


def repo_py_files():
    for py in ROOT.rglob("*.py"):
        if any(part in SKIP_DIRS for part in py.parts):
            continue
        yield py


def modname_of(py: Path) -> str:
    parts = list(py.relative_to(ROOT).parts)
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1][:-3]
    return ".".join(parts)


class Sig:
    __slots__ = ("params", "var_kw")

    def __init__(self, node):
        a = node.args
        self.params = {p.arg for p in [*a.posonlyargs, *a.args, *a.kwonlyargs]}
        self.var_kw = a.kwarg is not None


def main() -> int:
    sigs = {}
    parsed = {}
    for py in repo_py_files():
        try:
            tree = ast.parse(py.read_text(encoding="utf-8", errors="replace"))
        except (SyntaxError, OSError):
            continue
        parsed[py] = tree
        mod = modname_of(py)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                sigs[f"{mod}.{node.name}"] = Sig(node)

    # collect per-file edits: {(line0,col0), ...}
    file_edits: dict[Path, list[tuple[int, int]]] = defaultdict(list)
    for py, tree in parsed.items():
        mod = modname_of(py)
        from_map = {}
        local_defs = set()
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                local_defs.add(node.name)
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ""
                for a in node.names:
                    alias = a.asname or a.name.split(".")[0]
                    from_map[alias] = (base, a.name, a.asname is not None or "." in a.name)
            elif isinstance(node, ast.Import):
                for a in node.names:
                    alias = a.asname or a.name.split(".")[0]
                    from_map[alias] = (a.name, None, False)

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.keywords:
                continue
            callee = None
            f = node.func
            if isinstance(f, ast.Name):
                if f.id in local_defs:
                    callee = f"{mod}.{f.id}"
                elif f.id in from_map:
                    base, attr, _ = from_map[f.id]
                    if attr:
                        callee = f"{base}.{attr}"
            elif isinstance(f, ast.Attribute):
                h = f.value
                if isinstance(h, ast.Name) and h.id in from_map:
                    base, attr, _ = from_map[h.id]
                    callee = f"{base}.{f.attr}" if attr is None else f"{base}.{attr}.{f.attr}"
            if callee is None:
                continue
            sig = sigs.get(callee)
            if sig is None or sig.var_kw:
                continue
            for kw in node.keywords:
                if kw.arg == "hermes_home" and "hermes_home" not in sig.params:
                    if "aura_forge_home" in sig.params:
                        file_edits[py].append((kw.lineno - 1, kw.col_offset))

    total = 0
    for py, spots in file_edits.items():
        lines = py.read_text(encoding="utf-8").splitlines(keepends=True)
        # dedupe, apply right-to-left per line
        per_line = defaultdict(list)
        for (li, col) in spots:
            per_line[li].append(col)
        for li, cols in per_line.items():
            ln = lines[li]
            for col in sorted(set(cols), reverse=True):
                seg = ln[col:col + len("hermes_home")]
                if seg == "hermes_home":
                    ln = ln[:col] + "aura_forge_home" + ln[col + len("hermes_home"):]
                    total += 1
            lines[li] = ln
        py.write_text("".join(lines), encoding="utf-8", newline="")
        print(f"rewrote {py.relative_to(ROOT)} ({len(spots)} call-site(s))")
    print(f"total: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
