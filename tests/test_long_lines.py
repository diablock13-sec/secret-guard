from secret_guard import scanner
from secret_guard.scanner import scan_diff, scan_line

SECRET = "Zx7Qm4Lp9vRt" + "2WbNc8Kd"  # dirakit saat runtime


def make_diff(path, text):
    return (
        f"diff --git a/{path} b/{path}\n--- /dev/null\n+++ b/{path}\n"
        f"@@ -0,0 +1 @@\n+{text}\n"
    )


def test_secret_after_old_ten_thousand_limit_is_found():
    line = "x" * 12_000 + f' api_key = "{SECRET}"'
    assert [f.rule for f in scan_line("a.js", 1, line)] == ["generic-secret"]


def test_default_limit_is_at_least_one_megabyte():
    assert scanner.MAX_LINE_CHARS >= 1_000_000


def test_overlong_line_is_reported_and_secret_beyond_limit_is_missed(monkeypatch):
    monkeypatch.setattr(scanner, "MAX_LINE_CHARS", 1_000)
    text = "x" * 1_500 + f' api_key = "{SECRET}"'
    findings, long_lines = scanner.scan_diff_report(make_diff("bundle.js", text))
    assert long_lines == [("bundle.js", 1, len(text))]
    assert findings == []


def test_line_within_limit_is_scanned_and_not_reported(monkeypatch):
    monkeypatch.setattr(scanner, "MAX_LINE_CHARS", 1_000)
    text = "x" * 100 + f' api_key = "{SECRET}"'
    findings, long_lines = scanner.scan_diff_report(make_diff("a.js", text))
    assert long_lines == []
    assert [f.rule for f in findings] == ["generic-secret"]


def test_scan_diff_matches_report_findings():
    diff = make_diff("a.env", f'api_key = "{SECRET}"')
    assert scan_diff(diff) == scanner.scan_diff_report(diff)[0]
