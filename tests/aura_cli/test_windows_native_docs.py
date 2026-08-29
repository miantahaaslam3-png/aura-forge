from pathlib import Path


def test_windows_native_install_path_docs_match_installer() -> None:
    doc = Path("website/docs/user-guide/windows-native.md").read_text()
    install = Path("scripts/install.ps1").read_text()

    assert "%LOCALAPPDATA%\\aura-forge\\aura-forge\\venv\\Scripts" in doc
    assert "Get-Command aura-forge        # should print C:\\Users\\<you>\\AppData\\Local\\aura-forge\\aura-forge\\venv\\Scripts\\aura.exe" in doc
    assert '$aura-forgeBin = "$InstallDir\\venv\\Scripts"' in install
