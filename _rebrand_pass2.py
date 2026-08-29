#!/usr/bin/env python3
"""Second pass: catch remaining aura-forge references."""
import os, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SKIP = {'venv','.git','__pycache__','node_modules','.aura's,'.aura-forge','website','scripts','docs'}

REPLACEMENTS = [
    ('load_aura_dotenv', 'load_aura_dotenv'),
    ('is_nous_aura_non_agentic', 'is_nous_aura_non_agentic'),
    ('_aura_light_mode_hook_installed', '_aura_light_mode_hook_installed'),
    ('_aura_bp_timeout_patched', '_aura_bp_timeout_patched'),
    ('_aura_bp_start', '_aura_bp_start'),
    ('.aura_history', '.aura_history'),
    ('aura_conversation_', 'aura_conversation_'),
    ('AuraCLI', 'AuraCLI'),
    ('aura chat', 'aura chat'),
    ('aura dashboard', 'aura dashboard'),
    ('aura model', 'aura model'),
    ('aura fallback', 'aura fallback'),
    ('aura pets', 'aura pets'),
    ('aura migrate', 'aura migrate'),
    ('aura --resume', 'aura --resume'),
    ('aura --ignore', 'aura --ignore'),
    ('aura --tui', 'aura --tui'),
    ('aura --cli', 'aura --cli'),
    ('aura -c', 'aura -c'),
    ('aura -s', 'aura -s'),
    ('aura -w', 'aura -w'),
    ('aura -v', 'aura -v'),
    ('aura pid', 'aura pid'),
    ('aura/aura-', 'aura/aura-'),
    ('"aura/', '"aura/'),
    ("'aura/", "'aura/"),
    ('⚕ Aura Forge', '⚕ Aura Forge'),
    ('⚕ AURA FORGE', '⚕ AURA FORGE'),
    ('NOUS AURA FORGE', 'NOUS AURA FORGE'),
    ('aura history', 'aura history'),
    ('prog="aura"', 'prog="aura"'),
    ('prog=\'aura-forge\'', 'prog="aura"'),
]

def skip_dir(d):
    return d in SKIP or d.startswith('.')

def process(path):
    try: c = path.read_text('utf-8')
    except: return 0
    n = 0
    for o,r in REPLACEMENTS:
        if o in c: n += c.count(o); c = c.replace(o,r)
    def repl(m):
        nonlocal n; n += 1; return 'AURA_'+m.group(1)
    c = re.sub(r'AURA_([A-Z][A-Z_0-9]+)', repl, c)
    if n: path.write_text(c, 'utf-8')
    return n

total = 0
changed = 0
for dp, dns, fns in os.walk(ROOT):
    dns[:] = [d for d in dns if not skip_dir(d)]
    for fn in fns:
        p = Path(dp)/fn
        if p.suffix in ('.py', '.md', '.yaml', '.yml', '.toml', '.json', '.sh', '.ps1', '.cfg'):
            n = process(p)
            if n: total += n; changed += 1; print(f"  +{n} {p.relative_to(ROOT)}")

print(f"\nSecond pass: {changed} files, {total} changes")
