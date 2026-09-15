#!/usr/bin/env python3
"""
apply_aura_branding.py — Aura Forge rebrand engine.

Replaces all user-visible "Aura Forge" references with "Aura Forge" in the
codebase while preserving internal identifiers (hermes_cli, HERMES_HOME,
HermesGateway, etc.). Safe to run multiple times (idempotent).

Usage:
    python scripts/apply_aura_branding.py --apply   # rebrand the tree
    python scripts/apply_aura_branding.py --check   # verify no leaks (exit 1 if found)
"""

import argparse
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# ── Ordered replacement rules ──────────────────────────────────────────────
# Most-specific patterns FIRST to avoid double-replacement.

# (search_regex, replacement, file_globs, description)
RULES = [
    # 1. Repo URLs (all files)
    (r"NousResearch/auraforge-agent", "miantahaaslam3-png/aura-forge", None,
     "repo URL"),
     "repo URL"),
    (r"NousResearch/hermes_agent", "miantahaaslam3-png/aura-forge", None,
     "repo URL (underscore variant)"),
    (r"NousResearch/auraforge\.agent", "miantahaaslam3-png/aura-forge", None,
     "repo URL (dot variant)"),
    (r"github\.com/NousResearch/auraforge-agent", "github.com/miantahaaslam3-png/aura-forge", None,
     "full GitHub URL"),

    # 2. App identity (electron main.cjs)
    (r"APP_NAME\s*=\s*(process\.env\.[A-Z_]+\s*\|\|\s*)?'Aura Forge'", "APP_NAME = \\1'Aura Forge'", ["*.cjs", "*.ts"],
     "APP_NAME"),
    (r"setAppUserModelId\('com\.nousresearch\.auraforge'\)",
     "setAppUserModelId('com.auraforge.desktop')", ["*.cjs"],
     "AppUserModelId"),

    (r"WORDMARK\s*=\s*'AURA_FORGE AGENT'", "WORDMARK = 'AURA FORGE'", ["*.ts", "*.tsx"],
     "wordmark"),
    (r'''(?s)HERMES_AGENT_LOGO = """.*?"""''', '''HERMES_AGENT_LOGO = """[bold #C084FC] █████╗ ██╗   ██╗██████╗  █████╗    ███████╗ ██████╗ ██████╗  ██████╗ ███████╗[/]
[bold #B47CFF]██╔══██╗██║   ██║██╔══██╗██╔══██╗   ██╔════╝██╔═══██╗██╔══██╗██╔════╝ ██╔════╝[/]
[#9D74FF]███████║██║   ██║██████╔╝███████║   █████╗  ██║   ██║██████╔╝██║  ███╗█████╗  [/]
[#8B6BFF]██╔══██║██║   ██║██╔══██╗██╔══██║   ██╔══╝  ██║   ██║██╔══██╗██║   ██║██╔══╝  [/]
[#6F5BFF]██║  ██║╚██████╔╝██║  ██║██║  ██║   ██║     ╚██████╔╝██║  ██║╚██████╔╝███████╗[/]
[#5B4BFF]╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝      ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝[/]"""''',
     ["banner.py", "cli.py"],
     "cli logo art"),
    (r'''(?s)HERMES_CADUCEUS = """.*?"""''', '''HERMES_CADUCEUS = """[#C084FC]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣀⣤⣶⣶⣶⣤⣀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]
[#B47CFF]⠀⠀⠀⠀⠀⠀⢀⣠⣴⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⣦⣄⡀⠀⠀⠀⠀⠀⠀[/]
[#9D74FF]⠀⢀⣠⣴⣶⠿⠋⣩⡿⣿⡿⠻⣿⡇⢠⡄⢸⣿⠟⢿⣿⢿⣍⠙⠿⣶⣦⣄⡀⠀[/]
[#8B6BFF]⠀⠀⣾⣿⣿⣿⣿⣿⣿⣿⣿⠿⠿⠿⠿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⠀⠀[/]
[#FFD700]⠀⠀⣿⣿⣿⣿⣿⣿⠿⠋⠉⠀⠀⠀⠀⠀⠉⠙⠿⣿⣿⣿⣿⣿⣿⣿⠀⠀[/]
[#FFD700]⠀⠀⣿⣿⣿⠿⠋⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠙⠿⣿⣿⣿⣿⠀⠀[/]
[#FFBF00]⠀⠀⣿⣿⠋⠀⠀⠀⠀⠀⠀✦⠀⠀⠀⠀⠀⠀⠀⠀⠀⠙⣿⣿⠀⠀[/]
[#FFBF00]⠀⠀⣿⣿⠋⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠙⣿⣿⠀⠀[/]
[#FFBF00]⠀⠀⣿⣿⠋⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠙⣿⣿⠀⠀[/]
[#FFBF00]⠀⠀⣿⣿⣷⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣀⣴⣿⣿⣿⠀⠀[/]
[#CD7F32]⠀⠀⣿⣿⣿⣿⣷⣄⡀⠀⠀⠀⠀⠀⢀⣠⣴⣿⣿⣿⣿⣿⠀⠀[/]
[#CD7F32]⠀⠀⣿⣿⣿⣿⣿⣿⣿⣿⠿⠿⠿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠀⠀[/]
[#B8860B]⠀⠀⠻⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠟⠀⠀[/]
[#B8860B]⠀⠀⠀⠀⠙⠻⠿⠿⣿⣿⣿⣿⣿⣿⠿⠿⠿⠟⠋⠀⠀[/]
[#B8860B]⠀⠀⠀⠀⠀⠀⠀⠀⠉⠉⠉⠉⠉⠀⠀⠀⠀⠀⠀⠀⠀[/]"""''',
     ["banner.py", "cli.py"],
     "cli hero art"),
    (r"const APP_NAME = 'Aura Forge'", "const APP_NAME = 'Aura Forge'", ["*.cjs", "*.ts"],
     "APP_NAME (simple)"),

    # 3. Log prefix
    (r"\[auraforge\]\s", "[aura-forge] ", ["*.ts", "*.tsx", "*.cjs", "*.rs", "*.ps1", "*.sh"],
     # Aura Forge: restricted to non-Python files to prevent breaking Python list literals like `cmd = [auraforge]`
     "log prefix"),

    # 4. AppUserModelId (all forms)
    (r"com\.nousresearch\.auraforge", "com.auraforge.desktop", None,
     "appId"),

    # 5. User-visible phrases in Electron main.cjs
    (r"Waiting to start Aura Forge backend", "Waiting to start Aura Forge backend", ["*.cjs"],
     "startup string"),
    (r"Aura Forge will start automatically when it completes", "Aura Forge will start automatically when it completes", ["*.cjs"],
     "update string"),
    (r"existing Aura Forge Python at", "existing Aura Forge Python at", ["*.cjs"],
     "python label"),
    (r"Updating Aura Forge — this window will close and the updater will open\. Don't reopen Aura Forge yourself",
     "Updating Aura Forge — this window will close and the updater will open. Don't reopen Aura Forge yourself", ["*.cjs"],
     "update dialog"),
    (r"another process is holding the Aura Forge install open",
     "another process is holding the Aura Forge install open", ["*.cjs"],
     "lock error"),
    (r"\(a second Aura Forge window or a terminal running auraforge\?\)",
     "(a second Aura Forge window or a terminal running auraforge?)", ["*.cjs"],
     "lock error hint"),
    (r"Updating Aura Forge \(git \+ dependencies\)",
     "Updating Aura Forge (git + dependencies)", ["*.cjs"],
     "update stage"),
    (r"'An update is finishing — Aura Forge will start automatically",
     "'An update is finishing — Aura Forge will start automatically", ["*.cjs"],
     "update finishing"),

    # 6. Desktop frontend user-visible strings
    (r"Starting Aura Forge\.\.\.", "Starting Aura Forge...", ["*.tsx", "*.ts"],
     "frontend placeholder"),
    (r"Aura Forge Agent", "Aura Forge Agent", None,
     "product name"),

    # 7. PowerShell identifiers (before prose "Aura Forge" rule)
    (r"\$Aura Forge([A-Z]\w+)", r"$AuraForge\1", ["*.ps1"],
     "PS identifier"),
    (r"HERMES_HOME", "HERMES_HOME", ["*.ps1", "*.sh"],
     "env var name in scripts"),

    # 8. Bootstrap exe/app names
    (r"\"Aura Forge\.exe\"", '"AuraForge.exe"', ["*.rs", "*.cjs"],
     "Windows exe name"),
    (r"Aura Forge\.app", "AuraForge.app", ["*.rs", "*.cjs"],
     "macOS app name"),
    (r"Aura Forge-Setup\.exe", "AuraForge-Setup.exe", ["*.rs", "*.cjs"],
     "setup exe name"),
    (r"Contents/MacOS\",\s*\"Aura Forge\"\)", 'Contents/MacOS", "AuraForge")', ["*.rs"],
     "macOS binary name"),

    # 9. Display name — standalone "Aura Forge" word (after all specific rules)
    #    Protects: HERMES_HOME, hermes_cli, HermesGateway, auraforge-. prefix
    #    Only matches "Aura Forge" as a standalone word (not part of identifier)
    (r"(?<![A-Za-z0-9_/\\])Aura Forge(?![A-Za-z0-9_-])", "Aura Forge", None,
     "standalone 'Aura Forge'"),
]

# ── Files/dirs to skip ─────────────────────────────────────────────────────
SKIP_DIRS = {
    ".git", "node_modules", "target", "release", "dist",
    "web_dist", "tmp_extract", "aura_cli",
    "__pycache__", ".venv", "venv",
    # Large directories that should never need rebranding
    "changelog", "CHANGELOG.d",
    "docs", "doc",
    # Upstream CI/build artifacts
    "build", ".next", "out",
    # Binary/bundled assets
    "fonts", "locales", "icons",
}

SKIP_FILES = {
    "apply_aura_branding.py",  # don't rebrand ourselves
}

# ── Protected tokens (must survive rebranding) ─────────────────────────────
PROTECTED = [
    "hermes_cli", "HERMES_HOME", "HERMES_WEB_DIST",
    "HERMES_DESKTOP", "auraforge-bootstrap", "hermes_constants",
    "auraforge-version", "hermes_version", "/api/auraforge/",
    "_skills_tool.HERMES_HOME",
    "HermesGateway", "HermesGitBranch",
]


def should_skip(relpath: str) -> bool:
    parts = Path(relpath).parts
    if any(p in SKIP_DIRS for p in parts):
        return True
    if Path(relpath).name in SKIP_FILES:
        return True
    return False


def is_text_file(path: Path) -> bool:
    ext = path.suffix.lower()
    return ext in {
        ".py", ".cjs", ".js", ".ts", ".tsx", ".rs",
        ".ps1", ".sh", ".json", ".toml", ".md", ".txt",
        ".html", ".css", ".yml", ".yaml",
    }


def check_protected(content_before: str, content_after: str) -> list[str]:
    """Verify protected tokens survived rebranding."""
    issues = []
    for token in PROTECTED:
        if token in content_before and token not in content_after:
            issues.append(f"PROTECTED TOKEN LOST: {token}")
    return issues


def apply_rules(content: str, fname: str = "") -> tuple[str, list[str]]:
    """Apply rebrand rules whose file_globs match fname (None/empty = all files)."""
    import fnmatch
    applied = []
    for pattern, replacement, file_globs, desc in RULES:
        if file_globs and fname:
            base = fname.replace('\\', '/')
            if not any(fnmatch.fnmatch(base, f"**/{g}") or fnmatch.fnmatch(base, g) for g in file_globs):
                continue
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            applied.append(desc)
            content = new_content
    return content, applied


def check_hermes_leaks(content: str, relpath: str) -> list[str]:
    """Find remaining standalone 'Aura Forge' references that should be rebranded."""
    leaks = []
    for i, line in enumerate(content.splitlines(), 1):
        # Skip comments that are internal (heuristic: lines starting with # or //)
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith("//") or stripped.startswith("*"):
            continue
        # Find standalone "Aura Forge" (not HERMES_, hermes_cli, etc.)
        for m in re.finditer(r"(?<![A-Za-z0-9_/\\])Aura Forge(?![A-Za-z0-9_-])", line):
            leaks.append(f"  {relpath}:{i}: {stripped[:120]}")
    return leaks


def process_file(path: Path, apply: bool, check: bool) -> tuple[list[str], list[str]]:
    """Process a single file. Returns (applied_rules, leaks)."""
    relpath = str(path.relative_to(REPO))
    if should_skip(relpath):
        return [], []
    if not is_text_file(path):
        return [], []

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return [], []

    original = content
    applied, leaks = [], []

    if apply:
        content, applied = apply_rules(content, str(path))
        issues = check_protected(original, content)
        if issues:
            applied.extend(issues)
        if content != original:
            path.write_text(content, encoding="utf-8")

    if check:
        leaks = check_hermes_leaks(content if apply else original, relpath)

    return applied, leaks


def main():
    parser = argparse.ArgumentParser(description="Aura Forge rebrand engine")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--apply", action="store_true", help="Apply rebrand rules")
    group.add_argument("--check", action="store_true", help="Check for Aura Forge leaks")
    args = parser.parse_args()

    applied_all = []
    leaks_all = []

    scanned = 0
    for path in REPO.rglob("*"):
        if not path.is_file():
            continue
        # Skip files > 500KB (binaries, bundles)
        try:
            if path.stat().st_size > 500_000:
                continue
        except OSError:
            continue
        applied, leaks = process_file(path, args.apply, args.check)
        scanned += 1
        if applied:
            relpath = str(path.relative_to(REPO))
            for rule in applied:
                applied_all.append(f"  {relpath}: {rule}")
        if leaks:
            leaks_all.extend(leaks)

    if args.apply:
        print(f"Scanned {scanned} files, applied {len(applied_all)} rules across files:")
        for line in applied_all[:50]:
            print(line)
        if len(applied_all) > 50:
            print(f"  ... and {len(applied_all) - 50} more")

    if args.check:
        if leaks_all:
            print(f"\n⚠ Found {len(leaks_all)} remaining Aura Forge references:")
            for line in leaks_all[:50]:
                print(line)
            if len(leaks_all) > 50:
                print(f"  ... and {len(leaks_all) - 50} more")
            sys.exit(1)
        else:
            print("✓ No Aura Forge leaks found in user-facing strings")

    return 0


if __name__ == "__main__":
    main()
