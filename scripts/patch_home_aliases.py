import pathlib

for pth in ["tools/skill_manager_tool.py", "tools/skills_sync.py"]:
    p = pathlib.Path(pth)
    s = p.read_text(encoding="utf-8", errors="replace")
    if "AURA_FORGE_HOME = HERMES_HOME" not in s:
        s = s.replace(
            "HERMES_HOME = get_hermes_home()",
            "HERMES_HOME = get_hermes_home()\nAURA_FORGE_HOME = HERMES_HOME",
            1,
        )
        p.write_text(s, encoding="utf-8")
        print(pth, "patched")
    else:
        print(pth, "already has alias")