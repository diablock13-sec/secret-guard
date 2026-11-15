import json
from pathlib import Path

import pytest

from secret_guard.evaluate import (
    CorpusError,
    Metrics,
    evaluate,
    format_report,
    load_corpus,
    main,
    metrics,
)

CORPUS = Path(__file__).resolve().parent.parent / "eval" / "corpus.jsonl"
KEY_HEAD = ["-----BEGIN RSA PRIV", "ATE KEY-----"]  # terdeteksi aturan private-key


def write(tmp_path, *rows):
    f = tmp_path / "c.jsonl"
    f.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return f


def row(cid, label="secret", line="{S}", parts=None, group="g"):
    data = {"id": cid, "label": label, "group": group, "line": line}
    if parts is not None:
        data["parts"] = parts
    return data


# ---- perhitungan ----


def test_metrics_math():
    m = Metrics(tp=3, fp=1, fn=2, tn=4)
    assert m.precision == 0.75
    assert m.recall == 0.6


def test_metrics_undefined_values_are_none():
    m = Metrics(tp=0, fp=0, fn=0, tn=5)
    assert m.precision is None
    assert m.recall is None


# ---- pemuatan ----


def test_parts_are_assembled(tmp_path):
    f = write(tmp_path, row("a", line="x = {S}", parts=["AK", "IA"]))
    assert load_corpus(f)[0].line == "x = AKIA"


@pytest.mark.parametrize(
    ("bad_row", "match"),
    [
        (row("a", parts=None), "wajib memakai 'parts'"),
        (row("a", label="safe", line="x {S}"), "tanpa 'parts'"),
        (row("a", line="tanpa penanda", parts=["x"]), "tepat sekali"),
        (row("a", label="mungkin", parts=["x"]), "label"),
        (row("a", parts=[]), "daftar teks"),
        (row("a", parts=[1]), "daftar teks"),
        ({**row("a", parts=["x"]), "tambahan": 1}, "tidak dikenal"),
        ({"label": "safe", "group": "g", "line": "x"}, "'id'"),
    ],
)
def test_invalid_case_is_rejected(tmp_path, bad_row, match):
    with pytest.raises(CorpusError, match=match):
        load_corpus(write(tmp_path, bad_row))


def test_duplicate_id_rejected(tmp_path):
    f = write(tmp_path, row("a", parts=["x"]), row("a", parts=["y"]))
    with pytest.raises(CorpusError, match="id ganda"):
        load_corpus(f)


def test_bad_json_rejected(tmp_path):
    f = tmp_path / "c.jsonl"
    f.write_text("{bukan json\n", encoding="utf-8")
    with pytest.raises(CorpusError, match="bukan JSON"):
        load_corpus(f)


def test_empty_corpus_rejected(tmp_path):
    f = tmp_path / "c.jsonl"
    f.write_text("\n\n", encoding="utf-8")
    with pytest.raises(CorpusError, match="kosong"):
        load_corpus(f)


def test_missing_file_rejected(tmp_path):
    with pytest.raises(CorpusError, match="tidak bisa membaca"):
        load_corpus(tmp_path / "tidak-ada.jsonl")


# ---- evaluasi ----


def test_evaluate_counts_all_four_outcomes(tmp_path):
    f = write(
        tmp_path,
        row("tp", parts=KEY_HEAD),
        row("fn", parts=["polos"]),
        row("fp", label="safe", parts=KEY_HEAD),
        row("tn", label="safe", line="x = 1"),
    )
    m = metrics(evaluate(load_corpus(f)))
    assert (m.tp, m.fp, m.fn, m.tn) == (1, 1, 1, 1)


# ---- korpus yang dikirim bersama proyek ----


def test_shipped_corpus_is_valid_and_has_both_labels():
    cases = load_corpus(CORPUS)
    assert sum(c.label == "secret" for c in cases) >= 10
    assert sum(c.label == "safe" for c in cases) >= 10


def test_shipped_corpus_file_never_contains_an_assembled_secret():
    raw = CORPUS.read_text(encoding="utf-8")
    assembled = [
        "".join(json.loads(line)["parts"])
        for line in raw.splitlines()
        if line.strip() and "parts" in json.loads(line)
    ]
    assert assembled
    assert all(secret not in raw for secret in assembled)


def test_rule_based_secrets_are_never_missed():
    outcomes = [o for o in evaluate(load_corpus(CORPUS)) if o.case.group == "didukung"]
    assert outcomes
    missed = [o.case.id for o in outcomes if not o.flagged]
    assert missed == []


def test_report_never_prints_a_secret():
    cases = load_corpus(CORPUS)
    report = format_report(evaluate(cases))
    assert "precision" in report
    assert "SEMUA" in report
    for case in cases:
        if case.label == "secret":
            assert case.line not in report


# ---- main ----


def test_main_prints_report_and_exits_zero(capsys):
    assert main([str(CORPUS)]) == 0
    assert "SEMUA" in capsys.readouterr().out


def test_main_threshold_failure(tmp_path, capsys):
    f = write(tmp_path, row("fn", parts=["polos"]))
    assert main([str(f), "--min-recall", "0.5"]) == 1
    assert "GAGAL" in capsys.readouterr().err


def test_main_threshold_met(tmp_path):
    f = write(tmp_path, row("tp", parts=KEY_HEAD))
    assert main([str(f), "--min-recall", "1.0"]) == 0


def test_main_corpus_error_exits_two(tmp_path, capsys):
    assert main([str(tmp_path / "tidak-ada.jsonl")]) == 2
    assert "evaluate:" in capsys.readouterr().err


def test_main_unknown_group_exits_two(capsys):
    assert main([str(CORPUS), "--group", "tidak-ada"]) == 2
    assert "tidak ada kasus" in capsys.readouterr().err
