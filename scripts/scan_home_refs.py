import re, pathlib

ws = pathlib.Path("auraforge_cli/web_server.py").read_text(encoding="utf-8", errors="replace")
for m in sorted(set(re.findall(r"tools\.(\w+)\.AURA_FORGE_HOME", ws))):
    p = pathlib.Path(f"tools/{m}.py")
    t = p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""
    print(f"{m:30s} defines HERMES_HOME={'HERMES_HOME = ' in t} AURA_FORGE_HOME={'AURA_FORGE_HOME' in t}")