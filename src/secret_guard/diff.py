import re
from collections.abc import Iterator

HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def added_lines(diff: str) -> Iterator[tuple[str, int, str]]:
    """Dari teks `git diff`, hasilkan (path, nomor_baris, isi) untuk baris yang DITAMBAH."""
    path: str | None = None
    in_hunk = False
    line_no = 0
    for raw in diff.splitlines():
        if raw.startswith("diff --git "):
            in_hunk = False
            path = None
            continue
        if not in_hunk:
            if raw.startswith("+++ "):
                target = raw[4:].split("\t")[0]
                if target == "/dev/null":
                    path = None
                else:
                    path = target.removeprefix("b/")
            elif (m := HUNK_RE.match(raw)):
                in_hunk = True
                line_no = int(m.group(1))
            continue
        m = HUNK_RE.match(raw)
        if m:
            line_no = int(m.group(1))
            continue
        if raw.startswith("+"):
            if path is not None:
                yield path, line_no, raw[1:]
            line_no += 1
        elif raw.startswith(("-", "\\")):
            continue
        else:
            line_no += 1  # baris konteks
