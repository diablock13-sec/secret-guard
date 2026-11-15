import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]


def test_changelog_top_release_matches_version():
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    first = re.search(r"^## \[(\d+\.\d+\.\d+)\]", text, re.MULTILINE)
    assert first is not None
    assert first.group(1) == VERSION


def test_readme_pre_commit_rev_matches_version():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert f"rev: v{VERSION}" in readme
