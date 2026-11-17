import subprocess

from secret_guard import cli
from secret_guard.diff import added_lines

SECRET = "Zx7Qm4Lp9vRt" + "2WbNc8Kd"  # dirakit saat runtime


def diff_of(path: str, *added: str) -> str:
    body = "".join(f"+{a}\n" for a in added)
    return (
        f"diff --git a/{path} b/{path}\n--- /dev/null\n+++ b/{path}\n"
        f"@@ -0,0 +1,{len(added)} @@\n{body}"
    )


def as_stream(diff: str):
    return iter(diff.split("\n")[:-1])


def test_stream_matches_string_for_plain_diff():
    diff = diff_of("a.txt", "satu", "dua")
    assert list(added_lines(as_stream(diff))) == list(added_lines(diff))


def test_stream_matches_string_for_crlf_lines():
    diff = diff_of("a.env", "NAME=nilai\r", "LAIN=x\r")
    assert list(added_lines(as_stream(diff))) == list(added_lines(diff))
    assert next(iter(added_lines(as_stream(diff))))[2] == "NAME=nilai"


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def test_scan_streams_staged_diff_and_finds_secret(monkeypatch, tmp_path):
    git(tmp_path, "init", "-q")
    (tmp_path / "app.py").write_text(f'api_key = "{SECRET}"\n')
    git(tmp_path, "add", "app.py")
    monkeypatch.chdir(tmp_path)
    assert cli.main(["scan"]) == 1


def test_scan_streams_clean_staged_diff(monkeypatch, tmp_path):
    git(tmp_path, "init", "-q")
    (tmp_path / "a.txt").write_text("halo\n")
    git(tmp_path, "add", "a.txt")
    monkeypatch.chdir(tmp_path)
    assert cli.main(["scan"]) == 0


def test_scan_outside_repo_fails_closed(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    monkeypatch.chdir(tmp_path)
    assert cli.main(["scan"]) == 2
    assert "git diff gagal" in capsys.readouterr().err
