import pytest

from secret_guard.ignore import IgnoreError, is_ignored, parse_ignore


@pytest.mark.parametrize(
    ("pattern", "path", "expected"),
    [
        ("*.md", "readme.md", True),
        ("*.md", "docs/readme.md", True),
        ("*.md", "a.py", False),
        (".env.example", "app/.env.example", True),
        ("fixtures/", "fixtures/a.txt", True),
        ("fixtures/", "tests/fixtures/a.txt", True),
        ("fixtures/", "myfixtures/a.txt", False),
        ("tests/fixtures/", "tests/fixtures/a.txt", True),
        ("tests/fixtures/", "src/tests/fixtures/a.txt", False),
        ("/fixtures/", "fixtures/a.txt", True),
        ("/fixtures/", "tests/fixtures/a.txt", False),
        ("docs/*.md", "docs/a.md", True),
        ("docs/*.md", "other/docs/a.md", False),
        ("docs/*.md", "docs/sub/a.md", True),  # '*' boleh melewati '/'
        ("/config.py", "config.py", True),
        ("/config.py", "src/config.py", False),
        ("Config.py", "config.py", False),  # huruf besar kecil dibedakan
    ],
)
def test_pattern_matching(pattern, path, expected):
    assert is_ignored(path, [pattern]) is expected


def test_no_patterns_ignores_nothing():
    assert is_ignored("a.py", []) is False


def test_backslash_paths_are_normalised():
    assert is_ignored("tests\\fixtures\\a.txt", ["tests/fixtures/"]) is True


def test_parse_skips_comments_and_blank_lines():
    text = "# komentar\n\n  *.md  \nfixtures/\n"
    assert parse_ignore(text) == ["*.md", "fixtures/"]


@pytest.mark.parametrize("line", ["*", "**", "/", "*/", "**/"])
def test_too_broad_pattern_rejected(line):
    with pytest.raises(IgnoreError, match="terlalu luas"):
        parse_ignore(line)


def test_negation_rejected_with_line_number():
    with pytest.raises(IgnoreError, match=r"\.secretguardignore:3:.*negasi"):
        parse_ignore("a\nb\n!c\n")
