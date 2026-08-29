#!/usr/bin/env python3
"""Sixth pass: fix remaining variable names and JSON keys."""
import os, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SKIP = {'venv','.git','__pycache__','node_modules','.aura-forge','.aura-forge','website','scripts','docs','optional-skills'}

REPLACEMENTS = [
    # backup.py variable names
    ('aura_root', 'aura_root'),
    # Command text
    ('aura import', 'aura import'),
    ('aura -p', 'aura -p'),
    ('aura gateway', 'aura gateway'),
    ('installing aura-forge', 'installing aura-forge'),
    # ACP provenance parameter names
    ('current_aura_session_id', 'current_aura_session_id'),
    ('previous_aura_session_id', 'previous_aura_session_id'),
    # JSON keys (camelCase)
    ('currentAuraSessionId', 'currentAuraSessionId'),
    ('rootAuraSessionId', 'rootAuraSessionId'),
    ('parentAuraSessionId', 'parentAuraSessionId'),
    ('previousAuraSessionId', 'previousAuraSessionId'),
    # Comments
    ('aura root', 'aura root'),
    ('aura dir', 'aura dir'),
    ('aura home', 'aura home'),
    ('aura root)', 'aura root)'),
    # Remaining AURA_ env vars
    ('AURA_', 'AURA_'),
]

def skip_dir(d):
    return d in SKIP or d.startswith('.')

def process(path):
    try:
        c = path.read_text('utf-8')
    except:
        return 0
    n = 0
    for o, r in REPLACEMENTS:
        cnt = c.count(o)
        if cnt:
            n += cnt
            c = c.replace(o, r)
    if n:
        path.write_text(c, 'utf-8')
    return n

total = 0
changed = 0
for dp, dns, fns in os.walk(ROOT):
    dns[:] = [d for d in dns if not skip_dir(d)]
    for fn in fns:
        p = Path(dp) / fn
        if p.suffix in ('.py', '.md', '.yaml', '.yml', '.toml', '.json', '.sh', '.ps1', '.cfg'):
            n = process(p)
            if n:
                total += n
                changed += 1
                print(f"  +{n} {p.relative_to(ROOT)}")

print(f"\nSixth pass: {changed} files, {total} changes")
