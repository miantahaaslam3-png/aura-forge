#!/usr/bin/env python3
"""Rename the Hermes-branded Python packages/modules to Aura Forge names.

Renames both the on-disk files (via git mv) and every reference in tracked
text files, longest-name-first so hermes_state_common isn't clobbered by
hermes_state. Preserves: HERMES_* env vars (upper-case, untouched by the
word patterns below), hermes:// deeplink, hermes: IPC channels, the
X-Hermes-Session-Token header name (reverted separately), and the rebrand
engine itself (rules updated separately).
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# order matters: longest first
PAIRS = [
    ("hermes_state_portability", "auraforge_state_portability"),
    ("hermes_state_schema", "auraforge_state_schema"),
    ("hermes_state_search", "auraforge_state_search"),
    ("hermes_state_common", "auraforge_state_common"),
    ("hermes_cli", "auraforge_cli"),
    ("hermes_constants", "auraforge_constants"),
    ("hermes_logging", "auraforge_logging"),
    ("hermes_bootstrap", "auraforge_bootstrap"),
    ("hermes_state", "auraforge_state"),
    ("hermes_time", "auraforge_time"),
]

EXTS = {".py", ".ts", ".tsx", ".js", ".cjs", ".mjs", ".rs", ".ps1", ".sh",
        ".json", ".toml", ".md", ".mdx", ".txt", ".html", ".css", ".yml",
        ".yaml"}
SKIP_FILES = {"apply_aura_branding.py", "fix_hermes_module_names.py"}
SKIP_DIRS = {"venv", ".venv", "node_modules", ".git", "dist", "build",
             "release", "web_dist", "target", "tmp_extract", "__pycache__",
             ".pytest_cache", ".next", "hermes_agent.egg-info"}


def tracked_text_files():
    out = subprocess.run(["git", "-C", str(ROOT), "ls-files"],
                         capture_output=True, text=True, check=True).stdout
    for rel in out.splitlines():
        p = ROOT / rel
        if any(part in SKIP_DIRS for part in Path(rel).parts):
            continue
        if p.suffix.lower() not in EXTS:
            continue
        yield p, rel


def main():
    if "--apply" not in sys.argv:
        print("dry run — pass --apply")
        apply = False
    else:
        apply = True

    # 1. git mv the on-disk python packages/modules
    moves = [
        ("hermes_cli", "auraforge_cli"),
        ("hermes_constants.py", "auraforge_constants.py"),
        ("hermes_logging.py", "auraforge_logging.py"),
        ("hermes_bootstrap.py", "auraforge_bootstrap.py"),
        ("hermes_time.py", "auraforge_time.py"),
        ("hermes_state.py", "auraforge_state.py"),
        ("hermes_state_common.py", "auraforge_state_common.py"),
        ("hermes_state_schema.py", "auraforge_state_schema.py"),
        ("hermes_state_search.py", "auraforge_state_search.py"),
        ("hermes_state_portability.py", "auraforge_state_portability.py"),
    ]
    for src, dst in moves:
        s, d = ROOT / src, ROOT / dst
        if not s.exists():
            print(f"  skip move (missing): {src}")
            continue
        if d.exists():
            print(f"  skip move (target exists): {dst}")
            continue
        if apply:
            r = subprocess.run(["git", "-C", str(ROOT), "mv", src, dst],
                               capture_output=True, text=True)
            print(f"  git mv {src} -> {dst}: {r.returncode} {r.stderr[:80]}")
        else:
            print(f"  would mv {src} -> {dst}")

    # 2. content replacements in all tracked text files
    pats = [(re.compile(rf"(?<![A-Za-z0-9_]){a}(?![A-Za-z0-9_])"), a, b)
            for a, b in PAIRS]
    total_files = 0
    total_hits = 0
    for p, rel in tracked_text_files():
        try:
            txt = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        new = txt
        n = 0
        for pat, a, b in pats:
            new, k = pat.subn(b, new)
            n += k
        if n:
            total_files += 1
            total_hits += n
            if apply:
                p.write_text(new, encoding="utf-8", newline="")
    print(f"content: {total_files} files, {total_hits} replacements")

    # 3. pyproject/uv.lock dist name
    for f in ("pyproject.toml", "uv.lock"):
        p = ROOT / f
        txt = p.read_text(encoding="utf-8")
        new, k = re.subn(r"(?<![\w-])hermes-agent(?![\w-])", "aura-forge-agent", txt)
        # package file refs inside lock (hermes_agent wheel names)
        new = new.replace("hermes_agent", "auraforge_agent")
        print(f"{f}: {k} dist-name replacements")
        if apply and new != txt:
            p.write_text(new, encoding="utf-8", newline="")

    if not apply:
        print("(no changes written)")


if __name__ == "__main__":
    main()
