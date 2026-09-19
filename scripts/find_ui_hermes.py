"""Find user-visible "hermes" strings in the desktop source (not comments, not identifiers)."""
import pathlib, re

root = pathlib.Path('apps/desktop/src')
patterns = [
    re.compile(r"'[^']*\bhermes\b[^']*'", re.I),
    re.compile(r'"[^"]*\bhermes\b[^"]*"', re.I),
    re.compile(r'`[^`]*\bhermes\b[^`]*`', re.I),
    re.compile(r'>\s*hermes\b', re.I),
    re.compile(r'\bhermes\b\s*[<"]', re.I),
]
skip = re.compile(r'hermes:emojibase|hermes-agent@1\.0\.0|@hermes/plugin-sdk|hermesDirectiveFormatter|hermes:|hermes\.\b|hermes_|hermes-|//.*hermes|/\*.*hermes|hermes-cli|hermes\.exe|hermes\.cmd|hermes-acp|hermes-agent|hermes-state|hermes-time|hermes-logging|hermes-bootstrap|hermes-cli|hermes-achievements|hermes-bots|hermes-connection|hermes:api|hermes:connection')

hits = []
for p in root.rglob('*'):
    if p.suffix not in {'.ts', '.tsx'}:
        continue
    if any(part in p.parts for part in ('node_modules', 'dist', 'build')):
        continue
    text = p.read_text(encoding='utf-8', errors='replace')
    for i, line in enumerate(text.splitlines(), 1):
        if skip.search(line):
            continue
        for pat in patterns:
            m = pat.search(line)
            if m:
                hits.append(f"{p}:{i}: {line.strip()[:120]}")
                break

for h in hits[:40]:
    print(h)
print(f"\nTotal: {len(hits)}")