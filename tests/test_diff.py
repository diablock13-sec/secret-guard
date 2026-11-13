from secret_guard.diff import added_lines


def make(*lines: str) -> str:
    return "\n".join(lines)


def test_removed_dashes_and_added_pluses_are_not_headers():
    diff = make(
        "diff --git a/app.py b/app.py",
        "index 111..222 100644",
        "--- a/app.py",
        "+++ b/app.py",
        "@@ -1,3 +1,4 @@",
        " import os",
        "--- hapus komentar",
        "+++ tambah baris",
        "+x = 1",
        " print(x)",
        "@@ -10,0 +12,1 @@",
        "+last = 2",
    )
    assert list(added_lines(diff)) == [
        ("app.py", 2, "++ tambah baris"),
        ("app.py", 3, "x = 1"),
        ("app.py", 12, "last = 2"),
    ]


def test_new_file():
    diff = make(
        "diff --git a/new.txt b/new.txt",
        "new file mode 100644",
        "index 0000000..abc",
        "--- /dev/null",
        "+++ b/new.txt",
        "@@ -0,0 +1,2 @@",
        "+one",
        "+two",
    )
    assert list(added_lines(diff)) == [("new.txt", 1, "one"), ("new.txt", 2, "two")]


def test_deleted_file_yields_nothing():
    diff = make(
        "diff --git a/old.txt b/old.txt",
        "deleted file mode 100644",
        "--- a/old.txt",
        "+++ /dev/null",
        "@@ -1,2 +0,0 @@",
        "-one",
        "-two",
    )
    assert list(added_lines(diff)) == []


def test_path_with_space_and_trailing_tab():
    diff = make(
        "diff --git a/my file.txt b/my file.txt",
        "--- a/my file.txt\t",
        "+++ b/my file.txt\t",
        "@@ -0,0 +1 @@",
        "+hi",
    )
    assert list(added_lines(diff)) == [("my file.txt", 1, "hi")]


def test_no_newline_marker_is_skipped():
    diff = make(
        "diff --git a/f.txt b/f.txt",
        "--- a/f.txt",
        "+++ b/f.txt",
        "@@ -1 +1 @@",
        "-old",
        "\\ No newline at end of file",
        "+new",
        "\\ No newline at end of file",
    )
    assert list(added_lines(diff)) == [("f.txt", 1, "new")]


def test_binary_file_yields_nothing():
    diff = "diff --git a/x.png b/x.png\nBinary files a/x.png and b/x.png differ\n"
    assert list(added_lines(diff)) == []


def test_two_files_do_not_leak_state():
    diff = make(
        "diff --git a/a.txt b/a.txt",
        "--- a/a.txt",
        "+++ b/a.txt",
        "@@ -0,0 +1 @@",
        "+dari a",
        "diff --git a/b.txt b/b.txt",
        "--- a/b.txt",
        "+++ b/b.txt",
        "@@ -0,0 +5 @@",
        "+dari b",
    )
    assert list(added_lines(diff)) == [("a.txt", 1, "dari a"), ("b.txt", 5, "dari b")]
