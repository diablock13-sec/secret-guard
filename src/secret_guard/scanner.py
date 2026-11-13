import math
import re
from collections import Counter
from dataclasses import dataclass

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
)

GENERIC = re.compile(
    r"""(?i)(?:api[_-]?key|secret|token|passw(?:or)?d|pwd|auth)[\w-]*\s*[:=]\s*["']([^"'\s]{16,})["']"""
)


def shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    n = len(s)
    return -sum(c / n * math.log2(c / n) for c in Counter(s).values())


def mask(secret: str) -> str:
    """Tampilkan paling banyak 4 karakter pertama."""
    return secret[:4] + "****"


def looks_random(value: str) -> bool:
    if len(value) < VALUE_MIN_LEN:
        return False
    lowered = value.lower()
    if any(hint in lowered for hint in PLACEHOLDER_HINTS):
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
            findings.append(Finding(rule.name, path, line_no, mask(m.group(0))))

    for m in GENERIC.finditer(text):
        start, end = m.span(1)
        if any(s <= start and end <= e for s, e in spans):
            continue  # sudah tertangkap aturan yang lebih spesifik
        if looks_random(m.group(1)):
            findings.append(Finding("generic-secret", path, line_no, mask(m.group(1))))

    return findings


def scan_diff(diff: str) -> list[Finding]:
    findings: list[Finding] = []
    for path, line_no, text in added_lines(diff):
        findings.extend(scan_line(path, line_no, text))
    return findings
