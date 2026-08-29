#!/usr/bin/env python3
"""Final pass: catch ALL remaining aura-forge references."""
import os, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SKIP = {'venv','.git','__pycache__','node_modules','.aura-forge','.aura-forge','website','scripts','docs','optional-skills'}

REPLACEMENTS = [
    # ContextVar names
    ('aura_gateway_transport', 'aura_gateway_transport'),
    # Attribute names
    ('_aura_noise_filter_installed', '_aura_noise_filter_installed'),
    # Function/import names
    ('aura_subprocess_env', 'aura_subprocess_env'),
    # Module name prefixes
    ('_aura_user_provider_', '_aura_user_provider_'),
    # Comments
    ('Aura-specific', 'Aura-specific'),
    ('Aura-managed', 'Aura-managed'),
    ('aura_specific', 'aura_specific'),
    # Remaining aura-forge in specific contexts
    ('"aura"', '"aura"'),
    ("'aura'", "'aura'"),
    # File paths in skills
    ('_aura_home.py', '_aura_home.py'),
    ('.aura-forge"', '.aura-forge"'),
    ('Path.home() / ".aura-forge"', 'Path.home() / ".aura-forge"'),
    # Remaining HERMES env vars
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

print(f"\nFinal pass: {changed} files, {total} changes")
