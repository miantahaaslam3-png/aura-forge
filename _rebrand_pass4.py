#!/usr/bin/env python3
"""Fourth pass: catch ALL remaining aura-forge references in critical files."""
import os, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SKIP = {'venv','.git','__pycache__','node_modules','.aura's,'.aura-forge','website','scripts','docs','optional-skills'}

REPLACEMENTS = [
    # HTTP headers
    ('X-Aura-Session-Token', 'X-Aura-Session-Token'),
    # Function/method names
    ('_spawn_aura_action', '_spawn_aura_action'),
    ('_default_aura_root_is_opt_data', '_default_aura_root_is_opt_data'),
    ('can_update_aura', 'can_update_aura'),
    ('aura_version', 'aura_version'),
    ('update_aura', 'update_aura'),
    ('check_aura_update', 'check_aura_update'),
    ('read_aura_oauth_credentials', 'read_aura_oauth_credentials'),
    ('aura_creds', 'aura_creds'),
    ('aura_pkce', 'aura_pkce'),
    ('_aura_osd_patched', '_aura_osd_patched'),
    ('aura_voice', 'aura_voice'),
    # User-agent strings
    ('AuraForgeDashboard', 'AuraForgeDashboard'),
    ('Aura-Forge', 'Aura-Forge'),
    ('Aura Forge', 'Aura Forge'),
    ('aura forge', 'aura forge'),
    ('aura-forge', 'aura-forge'),
    # Temp file prefixes
    ('.aura-tmp-', '.aura-tmp-'),
    # Comment references
    ('Captain Aura', 'Captain Aura'),
    ('chat with Aura Forge', 'chat with Aura Forge'),
    ('chat with Aura Forge', 'chat with Aura Forge'),
    # Logger names
    ('aura.mcp_serve', 'aura.mcp_serve'),
    # MCP config references
    ('"aura":', '"aura":'),
    ('"command": "aura"', '"command": "aura"'),
    # Remaining .aura-forge path references (fallback)
    ('Path.home() / ".aura-forge"', 'Path.home() / ".aura-forge"'),
    # Plugin/platform naming
    ('aura-achievements', 'aura-achievements'),
    # Toolset comment
    ('aura-<name>', 'aura-<name>'),
    # Remaining in commands.py
    ('/aura ', '/aura '),
    ('via /aura', 'via /aura'),
    ('of /aura', 'of /aura'),
    ('through /aura', 'through /aura'),
    ('on Slack', 'on Slack'),
    # History file
    ('.aura_history', '.aura_history'),
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
    # Catch remaining AURA_* env vars
    def repl(m):
        nonlocal n
        n += 1
        return 'AURA_' + m.group(1)
    c = re.sub(r'AURA_([A-Z][A-Z_0-9]+)', repl, c)
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

print(f"\nFourth pass: {changed} files, {total} changes")
