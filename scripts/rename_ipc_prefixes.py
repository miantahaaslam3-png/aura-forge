#!/usr/bin/env python3
"""Rename Hermes IPC channel prefixes and deeplinks to Aura Forge.

The desktop's IPC channel names (hermes:connection, hermes:api, hermes:composer-…)
leak into error messages ("No handler registered for 'hermes:readFileText'"),
the hermes:// deep-link protocol is registered under the old name, and the
plugin SDK is imported as @hermes/plugin-sdk. All three surface "Hermes" in
the running app. This rewrites them in place (main.ts, preload.ts, renderer
sources, plugin SDK loader, branding engine) so the next build is clean.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Directories to rewrite (skip node_modules, dist, build artifacts)
TARGET_DIRS = [
    ROOT / "apps/desktop/electron",
    ROOT / "apps/desktop/src",
    ROOT / "scripts",
]
EXTS = {".ts", ".tsx", ".js", ".json", ".md", ".rs", ".sh", ".ps1"}

# Order matters: the long prefixes first so we don't half-match.
REPLACEMENTS = [
    # Deeplink protocol: hermes:// -> auraforge://  (both in code and comments)
    (re.compile(r"\bhermes://"), "auraforge://"),
    # IPC channel names: hermes: -> auraforge:  (channel names, error strings)
    (re.compile(r"\bhermes:"), "auraforge:"),
    # Plugin SDK import: @hermes/plugin-sdk -> @auraforge/plugin-sdk
    (re.compile(r"@hermes/plugin-sdk"), "@auraforge/plugin-sdk"),
    # Plugin SDK type: HermesPlugin -> AuraForgePlugin
    (re.compile(r"\bHermesPlugin\b"), "AuraForgePlugin"),
    # Plugin SDK type: HermesApiRequest -> AuraForgeApiRequest
    (re.compile(r"\bHermesApiRequest\b"), "AuraForgeApiRequest"),
    # Plugin SDK type: HermesDesktop -> AuraForgeDesktop
    (re.compile(r"\bHermesDesktop\b"), "AuraForgeDesktop"),
    # Window global: window.hermesDesktop -> window.auraForgeDesktop
    (re.compile(r"\bwindow\.hermesDesktop\b"), "window.auraForgeDesktop"),
    # Function: hermesApi -> auraForgeApi
    (re.compile(r"\bhermesApi\b"), "auraForgeApi"),
    # Event constants: hermes:composer-* already covered above
    # Branding engine: keep the rename map in sync
    (re.compile(r"'hermes:\\|\"hermes:"), "'auraforge:\\|\"auraforge:"),
    (re.compile(r"hermes://"), "auraforge://"),
]


def should_skip(path: Path) -> bool:
    if any(part in path.parts for part in ("node_modules", "dist", "build", ".git")):
        return True
    if path.suffix not in EXTS:
        return True
    return False


def rewrite_file(path: Path) -> int:
    text = path.read_text(encoding="utf-8", errors="replace")
    new_text = text
    n = 0
    for pattern, repl in REPLACEMENTS:
        new_text, count = pattern.subn(repl, new_text)
        n += count
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
    return n


def main() -> int:
    total = 0
    files_changed = 0
    for d in TARGET_DIRS:
        if not d.exists():
            continue
        for path in d.rglob("*"):
            if should_skip(path):
                continue
            n = rewrite_file(path)
            if n:
                total += n
                files_changed += 1
                print(f"  {path.relative_to(ROOT)}: {n} replacements")
    print(f"\nTotal: {total} replacements across {files_changed} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())