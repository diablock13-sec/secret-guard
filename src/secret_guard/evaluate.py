"""Ukur precision dan recall pemindai pada korpus berlabel (JSONL).

Jalankan: python -m secret_guard.evaluate eval/corpus.jsonl
"""

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from secret_guard.scanner import scan_line

PLACEHOLDER = "{S}"
LABELS = ("secret", "safe")


class CorpusError(ValueError):
    """Isi korpus tidak valid."""


@dataclass(frozen=True)
class Case:
    id: str
    label: str
    group: str
    line: str  # sudah dirakit dari parts


@dataclass(frozen=True)
class Outcome:
    case: Case
    rules: tuple[str, ...]

    @property
    def flagged(self) -> bool:
        return bool(self.rules)


@dataclass(frozen=True)
class Metrics:
    tp: int
    fp: int
    fn: int
    tn: int

    @property
    def precision(self) -> float | None:
        flagged = self.tp + self.fp
        return self.tp / flagged if flagged else None

    @property
    def recall(self) -> float | None:
        positives = self.tp + self.fn
        return self.tp / positives if positives else None


def _case(number: int, raw: str) -> Case:
    try:
        data = json.loads(raw)
    except ValueError:
        raise CorpusError(f"baris {number}: bukan JSON yang valid") from None
    if not isinstance(data, dict):
        raise CorpusError(f"baris {number}: harus berupa objek JSON")
    unknown = set(data) - {"id", "label", "group", "line", "parts"}
    if unknown:
        raise CorpusError(f"baris {number}: kunci tidak dikenal: {sorted(unknown)}")
    for key in ("id", "label", "group", "line"):
        if not isinstance(data.get(key), str) or not data[key]:
            raise CorpusError(f"baris {number}: '{key}' wajib berupa teks tidak kosong")
    if data["label"] not in LABELS:
        raise CorpusError(f"baris {number}: label harus salah satu dari {LABELS}")

    line, parts = data["line"], data.get("parts")
    if parts is None:
        if data["label"] == "secret":
            raise CorpusError(
                f"baris {number}: kasus secret wajib memakai 'parts', "
                "supaya tidak ada rahasia utuh di file"
            )
        if PLACEHOLDER in line:
            raise CorpusError(f"baris {number}: memuat {PLACEHOLDER} tanpa 'parts'")
    else:
        valid = isinstance(parts, list) and parts
        if not valid or not all(isinstance(p, str) and p for p in parts):
            raise CorpusError(f"baris {number}: 'parts' harus daftar teks, tidak boleh kosong")
        if line.count(PLACEHOLDER) != 1:
            raise CorpusError(f"baris {number}: 'line' harus memuat {PLACEHOLDER} tepat sekali")
        line = line.replace(PLACEHOLDER, "".join(parts))
    return Case(data["id"], data["label"], data["group"], line)


def load_corpus(path: Path | str) -> list[Case]:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise CorpusError(f"tidak bisa membaca {path} ({type(exc).__name__})") from exc
    cases: list[Case] = []
    seen: set[str] = set()
    for number, raw in enumerate(text.splitlines(), 1):
        if not raw.strip():
            continue
        case = _case(number, raw)
        if case.id in seen:
            raise CorpusError(f"baris {number}: id ganda '{case.id}'")
        seen.add(case.id)
        cases.append(case)
    if not cases:
        raise CorpusError("korpus kosong")
    return cases


def evaluate(cases: list[Case]) -> list[Outcome]:
    outcomes = []
    for case in cases:
        findings = scan_line("korpus.txt", 1, case.line)
        outcomes.append(Outcome(case, tuple(sorted({f.rule for f in findings}))))
    return outcomes


def metrics(outcomes: list[Outcome]) -> Metrics:
    def count(label: str, flagged: bool) -> int:
        return sum(1 for o in outcomes if o.case.label == label and o.flagged == flagged)

    return Metrics(
        tp=count("secret", True),
        fp=count("safe", True),
        fn=count("secret", False),
        tn=count("safe", False),
    )


def _fmt(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}"


def format_report(outcomes: list[Outcome]) -> str:
    groups = sorted({o.case.group for o in outcomes})
    rows = [("SEMUA", outcomes)]
    rows += [(g, [o for o in outcomes if o.case.group == g]) for g in groups]

    header = (
        f"{'kelompok':<16}{'kasus':>6}{'TP':>5}{'FP':>5}{'FN':>5}{'TN':>5}"
        f"{'precision':>11}{'recall':>8}"
    )
    lines = [header]
    for name, rs in rows:
        m = metrics(rs)
        lines.append(
            f"{name:<16}{len(rs):>6}{m.tp:>5}{m.fp:>5}{m.fn:>5}{m.tn:>5}"
            f"{_fmt(m.precision):>11}{_fmt(m.recall):>8}"
        )

    # Hanya id yang dicetak untuk secret yang terlewat: rahasia utuh tidak pernah tampil.
    missed = [o for o in outcomes if o.case.label == "secret" and not o.flagged]
    false_alarms = [o for o in outcomes if o.case.label == "safe" and o.flagged]
    lines += ["", f"Terlewat (FN), {len(missed)}:"]
    lines += [f"  {o.case.id}  [{o.case.group}]" for o in missed] or ["  (tidak ada)"]
    lines += ["", f"Salah alarm (FP), {len(false_alarms)}:"]
    lines += [
        f"  {o.case.id}  [{o.case.group}]  oleh {', '.join(o.rules)}\n    {o.case.line}"
        for o in false_alarms
    ] or ["  (tidak ada)"]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m secret_guard.evaluate",
        description="Ukur precision dan recall pemindai pada korpus berlabel.",
    )
    parser.add_argument("corpus", help="file JSONL berisi kasus berlabel")
    parser.add_argument("--group", help="hanya hitung satu kelompok")
    parser.add_argument("--min-precision", type=float, metavar="X")
    parser.add_argument("--min-recall", type=float, metavar="X")
    args = parser.parse_args(argv)

    try:
        cases = load_corpus(args.corpus)
    except CorpusError as e:
        print(f"evaluate: {e}", file=sys.stderr)
        return 2
    if args.group:
        cases = [c for c in cases if c.group == args.group]
        if not cases:
            print(f"evaluate: tidak ada kasus di kelompok '{args.group}'", file=sys.stderr)
            return 2

    outcomes = evaluate(cases)
    print(format_report(outcomes))

    overall = metrics(outcomes)
    failed = False
    for name, value, minimum in (
        ("precision", overall.precision, args.min_precision),
        ("recall", overall.recall, args.min_recall),
    ):
        if minimum is not None and value is not None and value < minimum:
            print(f"GAGAL: {name} {value:.2f} di bawah batas {minimum:.2f}", file=sys.stderr)
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
