import hashlib
import math
import re
from collections import Counter
from dataclasses import dataclass, field

from secret_guard.diff import added_lines

IGNORE_MARKER = "secret-guard:ignore"
MAX_LINE_CHARS = 10_000
ENTROPY_MIN = 3.6
VALUE_MIN_LEN = 16
PLACEHOLDER_HINTS = (
    "example", "your", "changeme", "placeholder", "dummy", "sample",
    "xxxx", "****", "${", "{{", "<",
)


@dataclass(frozen=True)
class Rule:
    name: str
    pattern: re.Pattern[str]


@dataclass(frozen=True)
class Finding:
    rule: str
    path: str
    line: int
    preview: str  # sudah disensor, tidak pernah memuat rahasia utuh
    # hash rahasia, untuk membedakan rahasia berbeda yang pratinjaunya sama.
    # Tidak ikut perbandingan, repr, atau keluaran apa pun.
    fingerprint: str = field(default="", repr=False, compare=False)


RULES = (
    Rule("aws-access-key-id", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    Rule(
        "github-token",
        re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,255}|github_pat_[A-Za-z0-9_]{22,255})\b"),
    ),
    Rule("slack-token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b")),
    Rule("telegram-bot-token", re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b")),
    Rule(
        "private-key",
        re.compile(
            r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY(?: BLOCK)?-----"
        ),
    ),
    Rule("stripe-secret-key", re.compile(r"\b[sr]k_live_[0-9A-Za-z]{24,99}\b")),
    Rule("google-api-key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}(?![0-9A-Za-z_-])")),
    Rule(
        "jwt",
        re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    ),
    Rule(
        "url-credentials",
        re.compile(
            r"""(?i)\b[a-z][a-z0-9+.-]{1,20}://[^\s:/@"']{1,64}:"""
            r"""(?!(?:pass(?:word)?|pwd|secret|changeme|example|x{3,}|\*+|your|<|\{|\$)[^\s@/"']*@)"""
            r"""[^\s@/"']{8,}@"""
        ),
    ),
)

GENERIC = re.compile(
    r"""(?i)(?:api[_-]?key|secret|token|passw(?:or)?d|pwd|auth)[\w-]{0,64}["']?\s*[:=]\s*["']([^"'\s]{16,})["']"""
)

# Bentuk dotenv: NAMA=nilai tanpa spasi dan tanpa kutip. Sengaja sempit supaya kode
# seperti "token = get_token_x1" (pakai spasi) dan ekspresi tidak ikut tertangkap.
GENERIC_UNQUOTED = re.compile(
    r"""(?im)^\s*(?:export\s+)?"""
    r"""(?P<name>[\w-]{0,64}(?:api[_-]?key|secret|token|passw(?:or)?d|pwd|auth)[\w-]{0,64})"""
    r"""=(?!\$)(?P<value>[^\s"'`#<>()\[\]{},;]{16,})\s*(?:#.*)?$"""
)


def shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    n = len(s)
    return -sum(c / n * math.log2(c / n) for c in Counter(s).values())


def mask(secret: str) -> str:
    """Tampilkan paling banyak 4 karakter pertama."""
    return secret[:4] + "****"


def secret_fingerprint(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()[:16]


PATH_OR_URL = re.compile(r"^(?:/|\./|\.\./|~/|[A-Za-z][A-Za-z0-9+.-]*://)")
# Kata di nama kunci yang menandakan nilainya bukan kredensial (diperiksa per kata,
# supaya 'shared_secret' tidak salah dikira memuat 'sha').
NON_SECRET_NAME_WORDS = frozenset(
    {"hash", "md5", "checksum", "digest", "etag", "commit", "uuid", "guid"}
)


def is_word_identifier(value: str) -> bool:
    """Nama bergaya kode: tiga kata atau lebih dari huruf saja, dipisah '-' atau '_'."""
    parts = [p for p in re.split(r"[-_]+", value) if p]
    return len(parts) >= 3 and all(p.isalpha() for p in parts)


def is_hash_like_name(name: str) -> bool:
    return any(
        part in NON_SECRET_NAME_WORDS or re.fullmatch(r"sha\d*", part)
        for part in re.split(r"[_-]+", name.lower())
    )


def key_name(text: str, match: re.Match[str]) -> str:
    """Nama kunci lengkap, termasuk awalan di luar kecocokan ('sha256_' pada 'sha256_token')."""
    prefix = re.search(r"[\w-]*$", text[max(0, match.start() - 64) : match.start()])
    inner = re.match(r"[\w-]*", match.group(0))
    return (prefix.group(0) if prefix else "") + (inner.group(0) if inner else "")


def looks_random(value: str) -> bool:
    if len(value) < VALUE_MIN_LEN:
        return False
    lowered = value.lower()
    if any(hint in lowered for hint in PLACEHOLDER_HINTS):
        return False
    if PATH_OR_URL.match(value) or is_word_identifier(value):
        return False
    classes = sum(any(check(c) for c in value) for check in (str.islower, str.isupper, str.isdigit))
    if classes < 2:
        return False
    return shannon_entropy(value) >= ENTROPY_MIN


def scan_line(path: str, line_no: int, text: str) -> list[Finding]:
    if IGNORE_MARKER in text:
        return []
    text = text[:MAX_LINE_CHARS]
    findings: list[Finding] = []
    spans: list[tuple[int, int]] = []

    for rule in RULES:
        for m in rule.pattern.finditer(text):
            spans.append(m.span())
            secret = m.group(0)
            findings.append(
                Finding(rule.name, path, line_no, mask(secret), secret_fingerprint(secret))
            )

    for m in GENERIC.finditer(text):
        start, end = m.span(1)
        if any(s <= start and end <= e for s, e in spans):
            continue  # sudah tertangkap aturan yang lebih spesifik
        if is_hash_like_name(key_name(text, m)):
            continue
        if looks_random(m.group(1)):
            secret = m.group(1)
            findings.append(
                Finding(
                    "generic-secret", path, line_no, mask(secret), secret_fingerprint(secret)
                )
            )

    for m in GENERIC_UNQUOTED.finditer(text):
        start, end = m.span("value")
        if any(s <= start and end <= e for s, e in spans):
            continue
        if is_hash_like_name(m.group("name")):
            continue
        if looks_random(m.group("value")):
            secret = m.group("value")
            findings.append(
                Finding(
                    "generic-secret", path, line_no, mask(secret), secret_fingerprint(secret)
                )
            )

    return findings


def scan_diff(diff: str) -> list[Finding]:
    findings: list[Finding] = []
    for path, line_no, text in added_lines(diff):
        findings.extend(scan_line(path, line_no, text))
    return findings
