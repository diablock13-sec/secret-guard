from fnmatch import fnmatchcase

IGNORE_FILE = ".secretguardignore"


class IgnoreError(ValueError):
    """Isi file ignore tidak valid."""


def parse_ignore(text: str, source: str = IGNORE_FILE) -> list[str]:
    """Baca isi file ignore. Satu pola per baris, komentar diawali # di baris sendiri."""
    patterns = []
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("!"):
            raise IgnoreError(f"{source}:{number}: tanda '!' (negasi) tidak didukung")
        if set(line) <= set("*/"):
            raise IgnoreError(
                f"{source}:{number}: pola '{line}' terlalu luas, "
                "akan mematikan seluruh pemindaian"
            )
        patterns.append(line)
    return patterns


def _matches(pattern: str, path: str) -> bool:
    anchored = pattern.startswith("/") or "/" in pattern.rstrip("/")
    body = pattern.strip("/")
    if pattern.endswith("/"):  # direktori
        prefix = body + "/"
        if anchored:
            return path.startswith(prefix)
        return path.startswith(prefix) or f"/{prefix}" in path
    if anchored:  # pola berisi '/': dicocokkan ke path penuh dari akar repo
        return fnmatchcase(path, body)
    return fnmatchcase(path.rsplit("/", 1)[-1], body)  # tanpa '/': nama file saja


def is_ignored(path: str, patterns: list[str]) -> bool:
    path = path.replace("\\", "/")
    return any(_matches(p, path) for p in patterns)
