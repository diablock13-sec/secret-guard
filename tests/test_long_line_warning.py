import io

from secret_guard import cli
from secret_guard.history import find_leaks
from secret_guard.scanner import MAX_LINE_CHARS

LONG = "a" * (MAX_LINE_CHARS + 1)


def make(path: str, text: str) -> str:
    return (
        f"diff --git a/{path} b/{path}\n--- /dev/null\n+++ b/{path}\n"
        f"@@ -0,0 +1 @@\n+{text}\n"
    )


def run_scan(monkeypatch, tmp_path, diff):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO(diff.encode())))
    return cli.main(["scan", "--stdin"])


def test_history_reports_long_line_once_per_path():
    commits = [(f"c{i}", "d", make("big.js", LONG)) for i in range(3)]
    result = find_leaks(commits, lambda p: False)
    assert result.long_lines == [("big.js", 1, MAX_LINE_CHARS + 1)]


def test_history_skips_ignored_long_line():
    result = find_leaks([("c1", "d", make("big.js", LONG))], lambda p: True)
    assert result.long_lines == []


def test_scan_warns_on_long_line_but_does_not_block(monkeypatch, tmp_path, capsys):
    code = run_scan(monkeypatch, tmp_path, make("big.js", LONG))
    err = capsys.readouterr().err
    assert code == 0
    assert "peringatan" in err
    assert "big.js:1" in err


def test_scan_no_warning_for_short_line(monkeypatch, tmp_path, capsys):
    code = run_scan(monkeypatch, tmp_path, make("a.js", "x = 1"))
    assert code == 0
    assert "peringatan" not in capsys.readouterr().err
