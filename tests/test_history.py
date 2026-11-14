from secret_guard.history import MARK, find_leaks, split_commits
from secret_guard.scanner import Finding, scan_line

# Dirakit saat dijalankan: sumber tes tidak memuat string kunci utuh.
SECRET_A = "AKIA" + "QWERTYUIOPASDFGH"
SECRET_B = "AKIA" + "ZXCVBNMASDFGHJKL"


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


def commit(sha, date, path, line):
    return (sha, date, diff_for(path, line))


def never(_path):
    return False


# ---- split_commits ----


def test_split_commits_parses_marker_lines():
    lines = [
        "baris sebelum commit pertama diabaikan",
        f"{MARK}aaa{MARK}2026-01-01",
        "",
        "diff --git a/x b/x",
        "+hi",
        f"{MARK}bbb{MARK}2026-01-02",
        "",
    ]
    got = list(split_commits(lines))
    assert [(sha, date) for sha, date, _ in got] == [
        ("aaa", "2026-01-01"),
        ("bbb", "2026-01-02"),
    ]
    assert got[0][2].startswith("diff --git")
    assert got[1][2] == ""


def test_split_commits_empty_input():
    assert list(split_commits([])) == []


# ---- find_leaks ----


def test_same_secret_in_several_commits_is_reported_once_at_first_commit():
    commits = [
        commit("c1", "2026-01-01", "config.py", f'KEY = "{SECRET_A}"'),
        commit("c2", "2026-01-02", "config.py", f'KEY = "{SECRET_A}"'),
    ]
    result = find_leaks(commits, never)
    assert result.commits == 2
    assert len(result.leaks) == 1
    leak = result.leaks[0]
    assert (leak.commit, leak.date, leak.commits) == ("c1", "2026-01-01", 2)


def test_different_secrets_with_same_preview_are_not_merged():
    commits = [
        commit("c1", "2026-01-01", "a.py", f'KEY = "{SECRET_A}"'),
        commit("c2", "2026-01-02", "b.py", f'KEY = "{SECRET_B}"'),
    ]
    leaks = find_leaks(commits, never).leaks
    assert len(leaks) == 2
    assert leaks[0].preview == leaks[1].preview


def test_same_secret_in_two_files_lists_both_locations():
    commits = [
        commit("c1", "2026-01-01", "a.py", f'KEY = "{SECRET_A}"'),
        commit("c2", "2026-01-02", "b.py", f'KEY = "{SECRET_A}"'),
    ]
    assert {leak.path for leak in find_leaks(commits, never).leaks} == {"a.py", "b.py"}


def test_ignored_paths_are_skipped_and_counted():
    commits = [commit("c1", "2026-01-01", "fixtures/a.py", f'KEY = "{SECRET_A}"')]
    result = find_leaks(commits, lambda path: path.startswith("fixtures/"))
    assert result.leaks == []
    assert result.ignored == 1


def test_inline_marker_is_honoured():
    line = f'KEY = "{SECRET_A}"  # secret-guard:ignore'
    assert find_leaks([commit("c1", "2026-01-01", "a.py", line)], never).leaks == []


def test_clean_history():
    result = find_leaks([commit("c1", "2026-01-01", "a.py", "x = 1")], never)
    assert result.leaks == []
    assert result.commits == 1


def test_leak_does_not_contain_the_secret():
    commits = [commit("c1", "2026-01-01", "a.py", f'KEY = "{SECRET_A}"')]
    assert SECRET_A not in repr(find_leaks(commits, never))


# ---- sidik jari ----


def test_fingerprint_ignored_in_equality_and_repr():
    plain = Finding("r", "p", 1, "x")
    with_fp = Finding("r", "p", 1, "x", fingerprint="abc123")
    assert plain == with_fp
    assert "abc123" not in repr(with_fp)


def test_fingerprint_distinguishes_secrets():
    a = scan_line("p", 1, f'KEY = "{SECRET_A}"')[0]
    b = scan_line("p", 1, f'KEY = "{SECRET_B}"')[0]
    again = scan_line("p", 9, f'OTHER = "{SECRET_A}"')[0]
    assert a.fingerprint != b.fingerprint
    assert a.fingerprint == again.fingerprint
    assert SECRET_A not in a.fingerprint
