"""Bandingkan gitleaks dengan secret-guard pada korpus yang sama.

Jalankan: uv run python eval/bandingkan_gitleaks.py
Setiap kasus ditulis ke folder sementara di /tmp (satu file per kasus), lalu
dipindai gitleaks dengan --redact. Folder dihapus sesudahnya.
"""

import json
import subprocess
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

from secret_guard.evaluate import Outcome, evaluate, format_report, load_corpus

CORPUS = Path("eval/corpus.jsonl")


def hide(outcomes):
    """Sembunyikan teks baris: nilainya dirakit utuh dan tidak boleh masuk berkas hasil."""
    return [Outcome(replace(o.case, line="(baris disembunyikan)"), o.rules) for o in outcomes]


def run_gitleaks(cases):
    with tempfile.TemporaryDirectory(prefix="sg-gl-") as tmp:
        root = Path(tmp) / "kasus"
        root.mkdir()
        for case in cases:
            (root / f"{case.id}.txt").write_text(case.line + "\n", encoding="utf-8")
        report = Path(tmp) / "laporan.json"
        proc = subprocess.run(
            [
                "gitleaks", "dir", str(root),
                "--no-banner", "--redact", "--exit-code", "0",
                "--report-format", "json", "--report-path", str(report),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            sys.exit(f"gitleaks gagal ({proc.returncode}): {proc.stderr.strip()[:300]}")
        findings = json.loads(report.read_text()) if report.exists() else []

    hits: dict[str, set[str]] = {}
    for finding in findings:
        case_id = Path(finding["File"]).name.removesuffix(".txt")
        hits.setdefault(case_id, set()).add(finding["RuleID"])
    return [Outcome(c, tuple(sorted(hits.get(c.id, ())))) for c in cases]


def main():
    cases = load_corpus(CORPUS)
    print("== secret-guard ==")
    print(format_report(hide(evaluate(cases))))
    print("\n== gitleaks (paket Kali 8.26.0, aturan bawaan) ==")
    print(format_report(hide(run_gitleaks(cases))))


if __name__ == "__main__":
    main()
