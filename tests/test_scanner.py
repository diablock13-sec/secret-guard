import pytest

from secret_guard.scanner import scan_diff, scan_line

# Rahasia PALSU, dirakit saat runtime supaya teks utuhnya tidak ada di berkas ini.
AWS = "AKIA" + "ABCDEFGHIJKLMNOP"
GITHUB = "ghp" + "_" + "aB3dE5gH7jK9mN1pQ3sT5vX7zA9cE1gI3kM5"
SLACK = "xoxb" + "-1234567890-abcdefghij"
TELEGRAM = "1234567890" + ":" + "AAE1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q"
PRIVATE_KEY = "-----BEGIN " + "RSA PRIVATE KEY-----"
RANDOM = "Zx9Qm4Vb7Lk2Rt8Wp3Ns6Yh1Dc5Fg0J"


@pytest.mark.parametrize(
    ("line", "rule"),
    [
        (f'aws_access_key_id = "{AWS}"', "aws-access-key-id"),
        (f"GITHUB_TOKEN={GITHUB}", "github-token"),
        (f'SLACK_TOKEN = "{SLACK}"', "slack-token"),
        (f"TELEGRAM_BOT_TOKEN={TELEGRAM}", "telegram-bot-token"),
        (PRIVATE_KEY, "private-key"),
    ],
)
def test_known_secret_detected(line, rule):
    assert [f.rule for f in scan_line("x.py", 1, line)] == [rule]


@pytest.mark.parametrize(
    "line",
    [f'api_key = "{RANDOM}"', f'MY_API_KEY: "{RANDOM}"'],
)
def test_generic_high_entropy_detected(line):
    assert [f.rule for f in scan_line("x.py", 1, line)] == ["generic-secret"]


@pytest.mark.parametrize(
    "line",
    [
        'password = input("Password: ")',
        'secret_key = os.environ["SECRET_KEY"]',
        "# AKIA adalah awalan kunci AWS",
        "token_count = 12345",
        'tokenizer_name = "bert-base-uncased-model"',
        'api_key = "your_api_key_here_please"',
        'password = "aaaaaaaaaaaaaaaaaaaa"',
        'request_id = "123e4567-e89b-12d3-a456-426614174000"',
        'commit = "9fceb02d0ae598e95dc970b74767f19372d61af8"',
        'author = "john.doe@example.com"',
        'auth_header = "Bearer " + token',
    ],
)
def test_benign_lines_no_finding(line):
    assert scan_line("x.py", 1, line) == []


def test_specific_rule_and_generic_do_not_double_report():
    found = scan_line("x.py", 1, f'token = "{GITHUB}"')
    assert [f.rule for f in found] == ["github-token"]


def test_ignore_marker_skips_line():
    assert scan_line("x.py", 1, f'k = "{AWS}"  # secret-guard:ignore') == []


def test_preview_is_masked():
    found = scan_line("x.py", 3, f'k = "{AWS}"')
    assert found[0].preview == "AKIA****"
    assert AWS not in repr(found)


def make_diff(path, lines):
    body = "\n".join("+" + line for line in lines)
    header = f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n"
    return f"{header}@@ -1,0 +1,{len(lines)} @@\n{body}\n"


def test_scan_diff_reports_path_and_line():
    diff = make_diff("config.py", ["import os", f'KEY = "{AWS}"'])
    found = scan_diff(diff)
    assert [(f.rule, f.path, f.line) for f in found] == [("aws-access-key-id", "config.py", 2)]


def test_removed_lines_are_not_scanned():
    diff = (
        "diff --git a/c.py b/c.py\n--- a/c.py\n+++ b/c.py\n@@ -1 +1 @@\n"
        f'-KEY = "{AWS}"\n+KEY = os.environ["KEY"]\n'
    )
    assert scan_diff(diff) == []
