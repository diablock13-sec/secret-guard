from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field

from secret_guard.scanner import Finding, LongLine, scan_diff_report

# Penanda commit di keluaran `git log`. Baris isi diff selalu diawali +, -, spasi, atau @@,
# jadi baris berawalan karakter kendali ini tidak mungkin berasal dari isi file.
MARK = "\x01"
MARK_FORMAT = "%x01%H%x01%ad"


@dataclass(frozen=True)
class Leak:
    rule: str
    path: str
    line: int  # nomor baris di versi file pada commit pertama
    preview: str  # sudah disensor
    commit: str  # commit pertama yang memasukkannya
    date: str
    commits: int  # jumlah commit tempat rahasia yang sama ditambahkan


@dataclass(frozen=True)
class HistoryResult:
    leaks: list[Leak]
    commits: int
    ignored: int
    long_lines: list[LongLine] = field(default_factory=list)


def split_commits(lines: Iterable[str]) -> Iterator[tuple[str, str, str]]:
    """Pecah keluaran `git log -p --format=<MARK_FORMAT>` per commit: (hash, tanggal, diff)."""
    header: tuple[str, str] | None = None
    buf: list[str] = []
    for line in lines:
        if line.startswith(MARK):
            if header:
                yield (*header, "\n".join(buf).lstrip("\n"))
            parts = line.split(MARK)
            header = (
                parts[1] if len(parts) > 1 else "",
                parts[2] if len(parts) > 2 else "",
            )
            buf = []
        elif header:
            buf.append(line)
    if header:
        yield (*header, "\n".join(buf).lstrip("\n"))


def find_leaks(
    commits: Iterable[tuple[str, str, str]], is_ignored: Callable[[str], bool]
) -> HistoryResult:
    """Pindai commit dari yang tertua. Satu rahasia di satu file dilaporkan sekali,
    pada commit pertama yang memasukkannya."""
    Key = tuple[str, str, str]
    first: dict[Key, tuple[Finding, str, str]] = {}
    counts: dict[Key, int] = {}
    total = ignored = 0
    long_seen: dict[str, LongLine] = {}  # satu laporan per path
    for sha, date, diff in commits:
        total += 1
        seen_here: set[Key] = set()
        findings, long_lines = scan_diff_report(diff)
        for item in long_lines:
            if not is_ignored(item[0]):
                long_seen.setdefault(item[0], item)
        for f in findings:
            if is_ignored(f.path):
                ignored += 1
                continue
            key = (f.rule, f.fingerprint or f"{f.line}:{f.preview}", f.path)
            first.setdefault(key, (f, sha, date))
            if key not in seen_here:
                seen_here.add(key)
                counts[key] = counts.get(key, 0) + 1
    leaks = [
        Leak(f.rule, f.path, f.line, f.preview, sha, date, counts[key])
        for key, (f, sha, date) in first.items()
    ]
    return HistoryResult(leaks, total, ignored, list(long_seen.values()))
