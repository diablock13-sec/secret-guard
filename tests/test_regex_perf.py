import time

import pytest

from secret_guard import scanner
from secret_guard.scanner import scan_line

SECRET = "Zx7Qm4Lp9vRt" + "2WbNc8Kd"  # dirakit saat runtime
LIMIT = 0.1  # detik; kode kuadratik butuh 0,3 s sampai 2,5 s, kode linear di bawah 0,01 s


@pytest.mark.parametrize("unit", ["token", "api_key", "password-", "secret_"])
@pytest.mark.parametrize("name", ["GENERIC", "GENERIC_UNQUOTED"])
def test_pattern_scales_linearly_on_repeated_keyword(name, unit):
    line = unit * (20_000 // len(unit))
    start = time.perf_counter()
    list(getattr(scanner, name).finditer(line))
    assert time.perf_counter() - start < LIMIT


def test_key_name_suffix_within_limit_is_still_flagged():
    line = f'api_key_{"x" * 50} = "{SECRET}"'
    assert [f.rule for f in scan_line("a.py", 1, line)] == ["generic-secret"]


def test_key_name_lookup_scales_linearly_before_keyword(monkeypatch):
    # Lepas pemotongan baris supaya yang diukur hanya pencarian awalan nama kunci.
    monkeypatch.setattr(scanner, "MAX_LINE_CHARS", 10**9)
    line = "x" * 20_000 + f' api_key = "{SECRET}"'
    start = time.perf_counter()
    findings = scan_line("a.js", 1, line)
    assert time.perf_counter() - start < LIMIT
    assert [f.rule for f in findings] == ["generic-secret"]


def test_hash_like_name_prefix_is_still_skipped():
    hex40 = "9fceb02d0ae598e9" + "5dc970b74767f193" + "72d61af8"  # dirakit saat runtime
    assert scan_line("a.py", 1, f'sha256_token = "{hex40}"') == []
