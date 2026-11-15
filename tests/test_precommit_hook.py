import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOK = (ROOT / ".pre-commit-hooks.yaml").read_text(encoding="utf-8")


def test_hook_does_not_receive_filenames():
    # scan membaca 'git diff --cached' sendiri; nama file dari pre-commit tidak dipakai
    assert "pass_filenames: false" in HOOK
    assert "always_run: true" in HOOK


def test_hook_entry_matches_installed_command():
    scripts = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["scripts"]
    entry = next(line for line in HOOK.splitlines() if line.strip().startswith("entry:"))
    command = entry.split(":", 1)[1].split()
    assert command[0] in scripts
    assert command[1:] == ["scan"]
