import io
import os
import subprocess
import sys

import pytest

from secret_guard import cli
from secret_guard.cli import main

# Dirakit saat dijalankan: sumber tes tidak memuat string kunci utuh.
SECRET = "AKIA" + "QWERTYUIOPASDFGH"


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    """Tiap tes jalan di folder sementara, tanpa konfigurasi Git global."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    os.chdir(root)
    git("init", "-q")
    return root


def git(*args):
    return subprocess.run(
        [
            "git",
            "-c", "user.name=tes",
            "-c", "user.email=tes@example.com",
            "-c", "commit.gpgsign=false",
            *args,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def diff_for(path, line):
    lines = [
        f"diff --git a/{path} b/{path}",
        "new file mode 100644",
        "--- /dev/null",
        f"+++ b/{path}",
        "@@ -0,0 +1 @@",
        f"+{line}",
    ]
    return "\n".join(lines) + "\n"


def feed_stdin(monkeypatch, text):
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(text.encode())))


# ---- scan --stdin ----


def test_stdin_finds_secret_and_never_prints_it(monkeypatch, capsys):
    feed_stdin(monkeypatch, diff_for("config.py", f'KEY = "{SECRET}"'))
    assert main(["scan", "--stdin"]) == 1
    err = capsys.readouterr().err
    assert "aws-access-key-id" in err
    assert "config.py" in err
    assert SECRET not in err


def test_stdin_clean(monkeypatch, capsys):
    feed_stdin(monkeypatch, diff_for("config.py", "x = 1"))
    assert main(["scan", "--stdin"]) == 0
    assert "tidak ada secret" in capsys.readouterr().out


def test_quiet_prints_nothing_when_clean(monkeypatch, capsys):
    feed_stdin(monkeypatch, diff_for("config.py", "x = 1"))
    assert main(["scan", "--stdin", "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""


def test_inline_marker_skips_line(monkeypatch):
    line = f'KEY = "{SECRET}"  # secret-guard:ignore'
    feed_stdin(monkeypatch, diff_for("config.py", line))
    assert main(["scan", "--stdin"]) == 0


def test_ignore_file_skips_path_and_reports_it(monkeypatch, tmp_path, capsys):
    ignore = tmp_path / "ign"
    ignore.write_text("config.py\n")
    feed_stdin(monkeypatch, diff_for("config.py", f'KEY = "{SECRET}"'))
    assert main(["scan", "--stdin", "--ignore-file", str(ignore)]) == 0
    assert "1 temuan diabaikan" in capsys.readouterr().err


def test_ignore_file_for_other_path_does_not_hide_finding(monkeypatch, tmp_path):
    ignore = tmp_path / "ign"
    ignore.write_text("other.py\n")
    feed_stdin(monkeypatch, diff_for("config.py", f'KEY = "{SECRET}"'))
    assert main(["scan", "--stdin", "--ignore-file", str(ignore)]) == 1


def test_missing_explicit_ignore_file_is_error(monkeypatch, tmp_path, capsys):
    feed_stdin(monkeypatch, diff_for("config.py", "x = 1"))
    missing = tmp_path / "tidak-ada"
    assert main(["scan", "--stdin", "--ignore-file", str(missing)]) == 2
    assert "tidak ditemukan" in capsys.readouterr().err


def test_invalid_ignore_file_is_error(monkeypatch, tmp_path, capsys):
    ignore = tmp_path / "ign"
    ignore.write_text("!config.py\n")
    feed_stdin(monkeypatch, diff_for("config.py", "x = 1"))
    assert main(["scan", "--stdin", "--ignore-file", str(ignore)]) == 2
    assert "negasi" in capsys.readouterr().err


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as info:
        main(["--version"])
    assert info.value.code == 0
    assert "secret-guard" in capsys.readouterr().out


def test_no_subcommand_is_usage_error():
    with pytest.raises(SystemExit) as info:
        main([])
    assert info.value.code == 2


# ---- scan (staged) ----


def test_staged_secret_found(repo, capsys):
    (repo / "config.py").write_text(f'KEY = "{SECRET}"\n')
    git("add", "config.py")
    assert main(["scan"]) == 1
    err = capsys.readouterr().err
    assert "config.py" in err
    assert "baris 1" in err
    assert SECRET not in err


def test_unstaged_secret_not_scanned(repo):
    (repo / "config.py").write_text(f'KEY = "{SECRET}"\n')
    assert main(["scan"]) == 0


def test_ignore_file_in_repo_root_is_used(repo):
    (repo / "config.py").write_text(f'KEY = "{SECRET}"\n')
    (repo / ".secretguardignore").write_text("config.py\n")
    git("add", "config.py")
    assert main(["scan"]) == 0


def test_scan_outside_repo_is_error(tmp_path, capsys):
    plain = tmp_path / "plain"
    plain.mkdir()
    os.chdir(plain)
    assert main(["scan"]) == 2
    assert "secret-guard:" in capsys.readouterr().err


def test_path_with_space_is_reported(repo, capsys):
    (repo / "my file.py").write_text(f'KEY = "{SECRET}"\n')
    git("add", "my file.py")
    assert main(["scan"]) == 1
    assert "my file.py" in capsys.readouterr().err


# ---- hook ----


def hook_path(repo):
    return repo / ".git" / "hooks" / "pre-commit"


def test_hook_blocks_secret_then_allows_clean_commit(repo):
    assert main(["install-hook"]) == 0
    assert hook_path(repo).stat().st_mode & 0o111

    (repo / "config.py").write_text(f'KEY = "{SECRET}"\n')
    git("add", "config.py")
    blocked = git("commit", "-m", "tambah config")
    assert blocked.returncode != 0
    assert "aws-access-key-id" in blocked.stderr
    assert SECRET not in blocked.stdout + blocked.stderr

    (repo / "config.py").write_text("KEY = None\n")
    git("add", "config.py")
    assert git("commit", "-m", "tambah config").returncode == 0


def test_hook_fails_closed_when_interpreter_is_missing(repo):
    hook = hook_path(repo)
    hook.write_text(cli.hook_script("/tidak/ada/python"))
    hook.chmod(0o755)
    (repo / "a.txt").write_text("halo\n")
    git("add", "a.txt")
    result = git("commit", "-m", "x")
    assert result.returncode != 0
    assert "interpreter tidak ditemukan" in result.stderr


def test_install_is_idempotent_and_makes_no_backup(repo):
    assert main(["install-hook"]) == 0
    assert main(["install-hook"]) == 0
    assert not list(hook_path(repo).parent.glob("pre-commit.bak*"))


def test_install_refuses_to_overwrite_foreign_hook(repo, capsys):
    hook = hook_path(repo)
    hook.write_text("#!/bin/sh\necho milik-saya\n")
    hook.chmod(0o755)
    assert main(["install-hook"]) == 2
    assert "milik-saya" in hook.read_text()
    assert "--force" in capsys.readouterr().err


def test_force_backs_up_foreign_hook(repo):
    hook = hook_path(repo)
    hook.write_text("#!/bin/sh\necho milik-saya\n")
    hook.chmod(0o755)
    assert main(["install-hook", "--force"]) == 0
    assert cli.HOOK_MARKER in hook.read_text()
    backup = hook.with_name("pre-commit.bak")
    assert "milik-saya" in backup.read_text()


def test_second_force_does_not_overwrite_first_backup(repo):
    hook = hook_path(repo)
    hook.write_text("#!/bin/sh\necho pertama\n")
    main(["install-hook", "--force"])
    hook.write_text("#!/bin/sh\necho kedua\n")
    main(["install-hook", "--force"])
    assert "pertama" in hook.with_name("pre-commit.bak").read_text()
    assert "kedua" in hook.with_name("pre-commit.bak.1").read_text()


def test_uninstall_removes_own_hook(repo):
    main(["install-hook"])
    assert main(["uninstall-hook"]) == 0
    assert not hook_path(repo).exists()


def test_uninstall_leaves_foreign_hook(repo):
    hook = hook_path(repo)
    hook.write_text("#!/bin/sh\necho milik-saya\n")
    assert main(["uninstall-hook"]) == 2
    assert hook.exists()


def test_uninstall_without_hook_is_ok(repo):
    assert main(["uninstall-hook"]) == 0


def test_install_outside_repo_is_error(tmp_path, capsys):
    plain = tmp_path / "plain"
    plain.mkdir()
    os.chdir(plain)
    assert main(["install-hook"]) == 2
    assert "secret-guard:" in capsys.readouterr().err


# ---- laporan rich ----


def scan_output(monkeypatch, capsys, path):
    feed_stdin(monkeypatch, diff_for(path, f'KEY = "{SECRET}"'))
    assert main(["scan", "--stdin"]) == 1
    return capsys.readouterr().err


def test_report_does_not_interpret_markup_in_path(monkeypatch, capsys):
    err = scan_output(monkeypatch, capsys, "[bold]x[/bold].py")
    assert "[bold]x[/bold].py" in err


def test_report_does_not_expand_emoji_codes(monkeypatch, capsys):
    err = scan_output(monkeypatch, capsys, "x:warning:.py")
    assert "x:warning:.py" in err


def test_report_neutralises_control_characters_in_path(monkeypatch, capsys):
    err = scan_output(monkeypatch, capsys, "a\x1b[31mb.py")
    assert "\x1b" not in err
    assert "a?[31mb.py" in err


def test_report_has_no_colour_codes_when_not_a_terminal(monkeypatch, capsys):
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    assert "\x1b" not in scan_output(monkeypatch, capsys, "config.py")


def test_report_uses_colour_when_forced(monkeypatch, capsys):
    monkeypatch.setenv("FORCE_COLOR", "1")
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.delenv("NO_COLOR", raising=False)
    err = scan_output(monkeypatch, capsys, "config.py")
    assert "\x1b[" in err
    assert SECRET not in err


def test_report_respects_no_colour(monkeypatch, capsys):
    monkeypatch.setenv("FORCE_COLOR", "1")
    monkeypatch.setenv("NO_COLOR", "1")
    assert "\x1b[3" not in scan_output(monkeypatch, capsys, "config.py")


# ---- scan-history ----


def commit_file(repo, name, text, msg="c"):
    (repo / name).write_text(text)
    git("add", name)
    assert git("commit", "-m", msg).returncode == 0


def first_commit():
    return git("rev-list", "--max-parents=0", "HEAD").stdout.split()[0]


def test_history_finds_secret_that_was_later_removed(repo, capsys):
    commit_file(repo, "config.py", f'KEY = "{SECRET}"\n', "tambah kunci")
    first = first_commit()
    commit_file(repo, "config.py", "KEY = None\n", "hapus kunci")
    assert main(["scan"]) == 0  # yang di-stage bersih, tapi riwayatnya tidak
    capsys.readouterr()
    assert main(["scan-history"]) == 1
    err = capsys.readouterr().err
    assert "config.py" in err
    assert "aws-access-key-id" in err
    assert first[:7] in err
    assert "SUDAH BOCOR" in err
    assert SECRET not in err


def test_history_counts_commits_where_secret_was_added(repo, capsys):
    commit_file(repo, "config.py", f'KEY = "{SECRET}"\n', "a")
    commit_file(repo, "config.py", "KEY = None\n", "b")
    commit_file(repo, "config.py", f'KEY = "{SECRET}"\n', "c")
    assert main(["scan-history"]) == 1
    err = capsys.readouterr().err
    assert "1 secret ditemukan" in err
    assert "ada di 2 commit" in err


def test_history_scans_other_branches(repo):
    commit_file(repo, "a.txt", "halo\n", "awal")
    assert git("checkout", "-b", "rahasia").returncode == 0
    commit_file(repo, "config.py", f'KEY = "{SECRET}"\n', "kunci di cabang")
    assert git("checkout", "-").returncode == 0
    assert not (repo / "config.py").exists()
    assert main(["scan-history"]) == 1


def test_history_clean_repo(repo, capsys):
    commit_file(repo, "a.txt", "halo\n", "awal")
    assert main(["scan-history"]) == 0
    assert "1 commit dipindai" in capsys.readouterr().out


def test_history_max_commits_limits_scope(repo):
    commit_file(repo, "config.py", f'KEY = "{SECRET}"\n', "tambah kunci")
    commit_file(repo, "config.py", "KEY = None\n", "hapus kunci")
    commit_file(repo, "lain.txt", "halo\n", "lain")
    assert main(["scan-history", "--max-commits", "2"]) == 0
    assert main(["scan-history"]) == 1


def test_history_max_commits_must_be_positive():
    with pytest.raises(SystemExit) as info:
        main(["scan-history", "--max-commits", "0"])
    assert info.value.code == 2


def test_history_respects_ignore_file(repo, capsys):
    commit_file(repo, "config.py", f'KEY = "{SECRET}"\n', "tambah kunci")
    (repo / ".secretguardignore").write_text("config.py\n")
    assert main(["scan-history"]) == 0
    assert "1 temuan diabaikan" in capsys.readouterr().err


def test_history_outside_repo_is_error(tmp_path, capsys):
    plain = tmp_path / "plain"
    plain.mkdir()
    os.chdir(plain)
    assert main(["scan-history"]) == 2
    assert "secret-guard:" in capsys.readouterr().err
