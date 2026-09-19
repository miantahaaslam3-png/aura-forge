#!/usr/bin/env python3
"""Rename the @hermes/shared package and the desktop's hermes.ts client library.

Two things still leak "Hermes" in the running app:
  1. `@hermes/shared` — the workspace package imported by 53 sites across the
     desktop (apps/shared/package.json name + every import specifier).
  2. `apps/desktop/src/hermes.ts` — the desktop's typed wrapper around the
     backend API, imported as `@/hermes` by sdk/index.ts and others.

This rewrites the package name, every import specifier, the path alias in
tsconfig, and the file itself (git mv). The `apps/shared/` directory is renamed
to `apps/auraforge-shared/` so the source tree matches.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESKTOP = ROOT / "apps/desktop"
SHARED_OLD = ROOT / "apps/shared"
SHARED_NEW = ROOT / "apps/auraforge-shared"


def rewrite_package_json(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("name") == "@hermes/shared":
        data["name"] = "@auraforge/shared"
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print(f"  {path.relative_to(ROOT)}: name -> @auraforge/shared")


def rewrite_tsconfig() -> None:
    path = DESKTOP / "tsconfig.json"
    text = path.read_text(encoding="utf-8")
    new = text.replace("@/hermes", "@/auraforge").replace('"hermes"', '"auraforge"')
    if new != text:
        path.write_text(new, encoding="utf-8")
        print(f"  {path.relative_to(ROOT)}: tsconfig paths updated")


def rewrite_imports() -> int:
    """Rewrite every @hermes/shared and @/hermes import specifier in the desktop."""
    total = 0
    for d in (DESKTOP / "src", DESKTOP / "electron"):
        if not d.exists():
            continue
        for path in d.rglob("*"):
            if path.suffix not in {".ts", ".tsx", ".js", ".json", ".mjs", ".cjs"}:
                continue
            if any(p in path.parts for p in ("node_modules", "dist", "build")):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            new = text
            new = new.replace("@hermes/shared", "@auraforge/shared")
            new = new.replace("@/hermes", "@/auraforge")
            new = new.replace("from 'hermes'", "from 'auraforge'")
            new = new.replace('from "hermes"', 'from "auraforge"')
            new = new.replace("import 'hermes'", "import 'auraforge'")
            new = new.replace("import \"hermes\"", "import \"auraforge\"")
            if new != text:
                path.write_text(new, encoding="utf-8")
                total += 1
                print(f"  {path.relative_to(ROOT)}")
    return total


def rename_files() -> None:
    """git mv the hermes.ts client and its tests/types to auraforge names."""
    renames = [
        (DESKTOP / "src/hermes.ts", DESKTOP / "src/auraforge.ts"),
        (DESKTOP / "src/hermes.test.ts", DESKTOP / "src/auraforge.test.ts"),
        (DESKTOP / "src/types/hermes.ts", DESKTOP / "src/types/auraforge.ts"),
        (DESKTOP / "src/lib/hermes-open-target.ts",
         DESKTOP / "src/lib/auraforge-open-target.ts"),
        (DESKTOP / "src/lib/hermes-open-target.test.ts",
         DESKTOP / "src/lib/auraforge-open-target.test.ts"),
        (DESKTOP / "src/app/session/hooks/use-hermes-config.ts",
         DESKTOP / "src/app/session/hooks/use-auraforge-config.ts"),
        (DESKTOP / "src/app/session/hooks/use-hermes-config.test.ts",
         DESKTOP / "src/app/session/hooks/use-auraforge-config.test.ts"),
        (DESKTOP / "src/hermes-capability-scope.test.ts",
         DESKTOP / "src/auraforge-capability-scope.test.ts"),
        (DESKTOP / "src/hermes-cron-scope.test.ts",
         DESKTOP / "src/auraforge-cron-scope.test.ts"),
        (DESKTOP / "src/hermes-parity.test.ts",
         DESKTOP / "src/auraforge-parity.test.ts"),
        (DESKTOP / "src/hermes-profile-scope.test.ts",
         DESKTOP / "src/auraforge-profile-scope.test.ts"),
        (DESKTOP / "electron/windows-hermes-path.ts",
         DESKTOP / "electron/windows-auraforge-path.ts"),
        (DESKTOP / "electron/windows-hermes-path.test.ts",
         DESKTOP / "electron/windows-auraforge-path.test.ts"),
    ]
    for old, new in renames:
        if old.exists():
            subprocess.run(["git", "mv", str(old), str(new)],
                           cwd=ROOT, check=True, capture_output=True)
            print(f"  git mv {old.relative_to(ROOT)} -> {new.relative_to(ROOT)}")
        elif new.exists():
            print(f"  skip (already renamed): {new.relative_to(ROOT)}")


def main() -> int:
    print("Renaming @hermes/shared package...")
    rewrite_package_json(SHARED_NEW / "package.json")
    rewrite_tsconfig()
    n = rewrite_imports()
    rename_files()
    print(f"\nRewrote imports in {n} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())