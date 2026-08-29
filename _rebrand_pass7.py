#!/usr/bin/env python3
"""Seventh pass: fix aura_cmd variable and remaining patterns."""
import os, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SKIP = {'venv','.git','__pycache__','node_modules','.aura-forge','.aura-forge','website','scripts','docs','optional-skills'}

REPLACEMENTS = [
    # Variable names
    ('aura_cmd', 'aura_cmd'),
    ('aura_command', 'aura_command'),
    # Attribute names
    ('_aura_startup_restore_replay', '_aura_startup_restore_replay'),
    # Translation keys
    ('aura_cmd_not_found', 'aura_cmd_not_found'),
    # Comments
    ('the right Aura', 'the right Aura'),
    ('Aura session', 'Aura session'),
    ('aura-*', 'aura-*'),
    # More variable names
    ('aura_binary', 'aura_binary'),
    ('aura_bin', 'aura_bin'),
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

print(f"\nSeventh pass: {changed} files, {total} changes")
