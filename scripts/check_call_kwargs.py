#!/usr/bin/env python3
"""Static check: keyword args at call sites must exist in the callee signature.

The rebrand renamed some function PARAMETERS (e.g. load_hermes_dotenv's
hermes_home -> aura_forge_home) without updating every call site, causing
runtime TypeError: got an unexpected keyword argument. This walks the repo,
resolves direct function calls (local defs + from-imports + module.attr),
and flags keywords that the resolved callee cannot accept (when the callee
has no **kwargs). Only flags when resolution is unambiguous.
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
    rel = py.relative_to(ROOT)
    parts = list(rel.parts)
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1][:-3]
    return ".".join(parts)


class Sig:
    __slots__ = ("params", "var_kw")
    def __init__(self, node: ast.FunctionDef):
        a = node.args
        self.params = {p.arg for p in
                       [*a.posonlyargs, *a.args, *a.kwonlyargs]}
        self.var_kw = a.kwarg is not None


def main() -> int:
    # index: qualname -> Sig ; also name -> set(qualnames)
    sigs: dict[str, Sig] = {}
    by_bare: dict[str, set[str]] = defaultdict(set)

    parsed = {}
    for py in repo_py_files():
        try:
            tree = ast.parse(py.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        parsed[py] = tree
        mod = modname_of(py)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                q = f"{mod}.{node.name}"
                s = Sig(node)
                sigs[q] = s
                by_bare[node.name].add(q)

    errors = []
    for py, tree in parsed.items():
        mod = modname_of(py)
        # import maps for this file
        from_map = {}   # alias -> qualname (function or module)
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
                    if attr is None:  # module import
                        callee = f"{base}.{f.attr}"
                    else:
                        callee = f"{base}.{attr}.{f.attr}"
            if callee is None:
                continue
            sig = sigs.get(callee)
            if sig is None:
                continue  # not a top-level repo function
            if sig.var_kw:
                continue
            for kw in node.keywords:
                if kw.arg is None:
                    continue
                if kw.arg not in sig.params:
                    errors.append(
                        f"KWARG {py.relative_to(ROOT)}:{node.lineno}: "
                        f"{callee}() has no param '{kw.arg}'")

    out = sorted(set(errors))
    print(f"{len(out)} kwarg issue(s)")
    for e in out:
        print(e)
    return 1 if out else 0


if __name__ == "__main__":
    sys.exit(main())
