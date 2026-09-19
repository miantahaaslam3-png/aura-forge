import pathlib

count = 0
for p in sorted(pathlib.Path("tools").glob("*.py")):
    s = p.read_text(encoding="utf-8", errors="replace")
    if "HERMES_HOME = " in s and "AURA_FORGE_HOME" not in s:
        s = s.replace(
            "HERMES_HOME = get_hermes_home()",
            "HERMES_HOME = get_hermes_home()\nAURA_FORGE_HOME = HERMES_HOME",
            1,
        )
        p.write_text(s, encoding="utf-8")
        count += 1
        print("patched", p)
print("total", count)