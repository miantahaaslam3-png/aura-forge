#!/usr/bin/env python3
"""Third pass: catch remaining word-boundary aura-forge references."""
import os, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SKIP = {'venv','.git','__pycache__','node_modules','.aura's,'.aura-forge','website','scripts','docs'}

REPLACEMENTS = [
    # Variable names
    ('aura_home', 'aura_home'),
    
    # Slash commands in Slack/Telegram context
    ('/aura', '/aura'),
    
    # Help text prog names
    ('aura                       Start', 'aura                       Start'),
    ('aura <command> --help', 'aura <command> --help'),
    ('aura chat', 'aura chat'),
    ('aura plugin', 'aura plugin'),
    ('aura dashboard', 'aura dashboard'),
    
    # Specific context strings
    ('aura.example.com', 'aura.example.com'),
    ('`aura', '`aura'),
    
    # Comments: "aura process" etc.
    ('aura process', 'aura process'),
    ('aura session', 'aura session'),
    ('aura lock', 'aura lock'),
    ('aura pid', 'aura pid'),
    
    # Banner / ASCII art header
    ('AURA-FORGE', 'AURA-FORGE'),
    ('AURA FORGE', 'AURA FORGE'),
    
    # Branding strings
    ('⚕ Aura Forge', '⚕ Aura Forge'),
    ('"Aura Forge"', '"Aura Forge"'),
    ("'Aura Forge'", "'Aura Forge'"),
    ('Aura CLI', 'Aura CLI'),
    
    # Module path strings
    ('aura_cli/', 'aura_cli/'),
    ('aura_cli.', 'aura_cli.'),
    ('aura_constants', 'aura_constants'),
    ('aura_state', 'aura_state'),
    ('aura_bootstrap', 'aura_bootstrap'),
    ('aura_logging', 'aura_logging'),
    ('aura_time', 'aura_time'),
    ('aura_plugins', 'aura_plugins'),
    
    # aura-forge-0day → keep as is (it's a proper noun / security advisory name)
    # aura.example.com → change to aura.example.com (already handled above)
    
    # Class references
    ('AuraCLI', 'AuraCLI'),
    ('Aura Forge', 'Aura Forge'),
    ('Aura Forge agent', 'Aura Forge agent'),
    
    # Branch/worktree patterns
    ('aura/', 'aura/'),
    
    # Docker/script paths
    ('aura-exec-shim', 'aura-exec-shim'),
    ('setup-aura', 'setup-aura'),
    
    # Remaining HERMES env vars
    ('AURA_HOME', 'AURA_HOME'),
    ('AURA_QUIET', 'AURA_QUIET'),
]

def skip_dir(d):
    return d in SKIP or d.startswith('.')

def process(path):
    try: c = path.read_text('utf-8')
    except: return 0
    n = 0
    for o, r in REPLACEMENTS:
        cnt = c.count(o)
        if cnt:
            n += cnt
            c = c.replace(o, r)
    # Catch remaining AURA_* env vars
    def repl(m):
        nonlocal n; n += 1; return 'AURA_' + m.group(1)
    c = re.sub(r'AURA_([A-Z][A-Z_0-9]+)', repl, c)
    # Catch remaining standalone "aura" in specific contexts
    # But NOT in strings like "aura-forge-0day" (security advisory)
    # NOT in domain names like example.com
    if n: path.write_text(c, 'utf-8')
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

print(f"\nThird pass: {changed} files, {total} changes")
