#!/usr/bin/env python3
"""Fifth pass: catch remaining aura-forge references in gateway, acp_adapter, etc."""
import os, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SKIP = {'venv','.git','__pycache__','node_modules','.aura's,'.aura-forge','website','scripts','docs','optional-skills'}

REPLACEMENTS = [
    # gateway/run.py
    ('shutil.which("aura")', 'shutil.which("aura")'),
    ('shutil.which(\'aura-forge\')', "shutil.which('aura')"),
    ('aura_bin', 'aura_bin'),
    ('aura.service', 'aura.service'),
    ('aura.service +', 'aura.service +'),
    ('X-Aura-Session-Id', 'X-Aura-Session-Id'),
    ('aura.tool_calls', 'aura.tool_calls'),
    ('aura binary', 'aura binary'),
    ('Aura-created', 'Aura-created'),
    ('aura process', 'aura process'),
    
    # gateway/status.py
    ('/ "aura"', '/ "aura"'),
    ('"aura"', '"aura"'),
    ('"aura.exe"', '"aura.exe"'),
    ('aura.exe', 'aura.exe'),
    ('Aura-owned', 'Aura-owned'),
    ('Aura Forge\'s', 'Aura\'s'),
    ('Aura Forge\'', 'Aura\'s'),
    
    # gateway/platforms/qqbot
    ('Aura/{aura_version}', 'Aura/{aura_version}'),
    
    # gateway/platforms/bluebubbles.py
    ('@?aura-forge\\s+agent', '@?aura\\s+forge'),
    
    # acp_adapter
    ('_meta.aura', '_meta.aura'),
    ('aura tool', 'aura tool'),
    ('Aura tool', 'Aura tool'),
    ('aura tool', 'aura tool'),
    ('Aura/OpenAI', 'Aura/OpenAI'),
    ('Aura Forge\' local', 'Aura\'s local'),
    ('Aura Forge\'s own', 'Aura\'s own'),
    ('Aura Forge\' threat', 'Aura\'s threat'),
    ('Aura-compatible', 'Aura-compatible'),
    ('Open Aura Forge\'', 'Open Aura\'s'),
    ('Aura Forge\' interactive', 'Aura\'s interactive'),
    ('Aura Forge\' todo', 'Aura\'s todo'),
    ('Aura Forge.', 'Aura Forge.'),
    
    # gateway/slash_commands
    ('/aura', '/aura'),
    
    # gateway/whatsapp_identity / drain_control / shutdown_forensics
    ('for Aura Forge', 'for Aura Forge'),
    ('for Aura's, 'for Aura Forge'),
    
    # gateway/relay
    ('aura-forge\'', 'aura\'s'),
    
    # More gateway patterns
    ('the Aura's, 'the Aura Forge'),
    ('the aura's, 'the aura'),
    
    # Remaining HERMES env vars
    ('AURA_', 'AURA_'),
    
    # Model tools / mini_swe_runner
    ('aura model', 'aura model'),
    
    # mcp_serve remaining
    ('"aura"', '"aura"'),
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

print(f"\nFifth pass: {changed} files, {total} changes")
