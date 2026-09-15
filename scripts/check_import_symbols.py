#!/usr/bin/env python3
"""Static check: every `from X import a, b, c` must bind a, b, c in target X.

The rebrand sweep renamed single-line imports in some modules while leaving
multi-line `from X import (...)` call sites untouched, so target modules no
longer export names their importers ask for. This walks the whole repo with
ast and reports each missing symbol so we can fix the DEFINING side with
aliases (not chase hundreds of call sites).
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {"venv", ".venv", "node_modules", ".git", "dist", "build",
             "release", "web_dist", "target", "tmp_extract", "__pycache__",
             ".pytest_cache", ".next", "site-packages"}

# modules that are third-party / dynamic; we cannot resolve them statically
def is_local_module(mod: str) -> bool:
    top = mod.split(".")[0]
    if top in SKIP_DIRS:
        return False
    # top-level packages/dirs in repo
    candidate = ROOT / (mod.replace(".", "/"))
    if candidate.with_suffix(".py").exists() or candidate.is_dir():
        return True
    # also bare top-level modules like hermes_constants
    return (ROOT / (top + ".py")).exists() or (ROOT / top).is_dir()


def module_path(mod: str) -> Path | None:
    p = ROOT / (mod.replace(".", "/"))
    if p.with_suffix(".py").exists():
        return p.with_suffix(".py")
    if p.is_dir() and (p / "__init__.py").exists():
        return p / "__init__.py"
    top = mod.split(".")[0]
    q = ROOT / (top + ".py")
    if q.exists():
        return q
    return None


def collect_bindings(path: Path) -> tuple[set[str], bool]:
    """Return (bound names, has_star_import_from_unknown)."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return set(), True
    names: set[str] = set()
    star = False
    has_module_getattr = False
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "__getattr__":
            has_module_getattr = True
    if has_module_getattr:
        # Dynamic module attribute resolution: statically un-analyseable.
        names.add("__DYNAMIC__")
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    names.add(t.id)
                elif isinstance(t, (ast.Tuple, ast.List)):
                    for e in t.elts:
                        if isinstance(e, ast.Name):
                            names.add(e.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.ImportFrom):
                for a in node.names:
                    if a.name == "*":
                        star = True
                    else:
                        names.add(a.asname or a.name.split(".")[0])
            else:
                for a in node.names:
                    names.add(a.asname or a.name.split(".")[0])
        elif isinstance(node, (ast.For,)) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, ast.With):
            for item in node.items:
                if item.optional_vars is not None:
                    if isinstance(item.optional_vars, ast.Name):
                        names.add(item.optional_vars.id)
                    elif isinstance(item.optional_vars, (ast.Tuple, ast.List)):
                        for e in item.optional_vars.elts:
                            if isinstance(e, ast.Name):
                                names.add(e.id)
        elif isinstance(node, ast.Try):
            for handler in node.handlers:
                if handler.name:
                    names.add(handler.name)
    return names, star


def resolve_star_names(mod: str) -> set[str]:
    """For `from X import *`, approximate X's bindings transitively."""
    p = module_path(mod)
    if p is None:
        return set()
    names, star = collect_bindings(p)
    if not star:
        return names
    # follow star sources
    extra: set[str] = set()
    try:
        tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return names
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for a in node.names:
                if a.name == "*":
                    src = resolve_star_names(f"{mod}.{node.module}" if node.module else mod)
                    extra |= src
    return names | extra


def main() -> int:
    files = []
    for py in ROOT.rglob("*.py"):
        if any(part in SKIP_DIRS for part in py.parts):
            continue
        files.append(py)

    # precompute target bindings with cache
    bind_cache: dict[str, set[str]] = {}

    def bindings_for(mod: str) -> set[str] | None:
        p = module_path(mod)
        if p is None:
            return None
        if mod in bind_cache:
            return bind_cache[mod]
        names, star = collect_bindings(p)
        if star:
            names |= resolve_star_names(mod)
        bind_cache[mod] = names
        return names

    errors = []
    for py in files:
        try:
            tree = ast.parse(py.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError as e:
            errors.append(f"SYNTAX {py.relative_to(ROOT)}: {e.lineno}: {e.msg}")
            continue
        rel = py.relative_to(ROOT)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.level:
                continue
            mod = node.module or ""
            if not is_local_module(mod):
                continue
            for a in node.names:
                if a.name == "*":
                    continue
                w = a.name
                # submodule import: `from pkg import mod` is fine if pkg/mod.py exists
                sub = ROOT / (mod.replace(".", "/")) / (w.replace(".", "/"))
                if sub.with_suffix(".py").exists() or (sub / "__init__.py").exists():
                    continue
                have = bindings_for(mod)
                if have is None or "__DYNAMIC__" in have or w in have:
                    continue
                errors.append(
                    f"MISSING {rel}:{node.lineno}: from {mod} import {w}")
    # de-dup & sort
    seen = set()
    out = []
    for e in sorted(errors):
        if e not in seen:
            seen.add(e)
            out.append(e)
    print(f"{len(out)} issue(s)")
    for e in out:
        print(e)
    return 1 if out else 0


if __name__ == "__main__":
    sys.exit(main())
