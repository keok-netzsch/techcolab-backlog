"""Tests for the call-processing sweep + BLOCO fallback in process.py."""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "call-recorder"))

import process  # noqa: E402


def _vault(tmp_path, monkeypatch):
    monkeypatch.setattr(process, "VAULT", str(tmp_path))
    (tmp_path / "Team" / "Ana-Leite" / "1on1").mkdir(parents=True)
    (tmp_path / "Stakeholders" / "Alberto-Reuters" / "1on1").mkdir(parents=True)
    (tmp_path / "Inbox").mkdir()
    tdir = tmp_path / "transcripts"
    tdir.mkdir()
    return tdir


def _age(path, *, days=0, minutes=0):
    ts = time.time() - days * 86400 - minutes * 60
    os.utime(path, (ts, ts))


# ── classification ────────────────────────────────────────────────────────────

def test_classify_person_manager_note_unknown(tmp_path, monkeypatch):
    _vault(tmp_path, monkeypatch)
    assert process._classify_transcript("2026-06-03_14-03_Ana-Leite.txt")[3] == "person"
    assert process._classify_transcript("2026-05-29_11-34_Alberto-Reuters.txt")[3] == "manager"
    assert process._classify_transcript("2026-06-03_18-18_nota-avulsa.txt")[3] == "note"
    assert process._classify_transcript("2026-06-03_10-00_Ghost-Person.txt")[3] == "unknown"
    assert process._classify_transcript("not-a-transcript.txt") is None


# ── processed detection ───────────────────────────────────────────────────────

def test_is_processed_person(tmp_path, monkeypatch):
    _vault(tmp_path, monkeypatch)
    one = tmp_path / "Team" / "Ana-Leite" / "1on1.md"
    one.write_text("---\n---\n\n## 2026-06-03\n", encoding="utf-8")
    assert process._is_processed("2026-06-03", "14-03", "Ana-Leite", "person") is True
    assert process._is_processed("2026-06-02", "14-03", "Ana-Leite", "person") is False


def test_is_processed_note(tmp_path, monkeypatch):
    _vault(tmp_path, monkeypatch)
    (tmp_path / "Inbox" / "2026-06-03_18-18_nota-avulsa.md").write_text("x", encoding="utf-8")
    assert process._is_processed("2026-06-03", "18-18", None, "note") is True
    assert process._is_processed("2026-06-03", "09-00", None, "note") is False


# ── sweep (dry-run, no Ollama) ────────────────────────────────────────────────

def test_sweep_detects_missing_and_skips_ok(tmp_path, monkeypatch):
    tdir = _vault(tmp_path, monkeypatch)
    # Ana processed (1on1.md has the section) -> ok
    (tmp_path / "Team" / "Ana-Leite" / "1on1.md").write_text("## 2026-06-03\n", encoding="utf-8")
    ok_f = tdir / "2026-06-03_14-03_Ana-Leite.txt"; ok_f.write_text("...", encoding="utf-8"); _age(ok_f, minutes=30)
    # Alberto NOT processed -> reprocess
    bad_f = tdir / "2026-06-03_11-00_Alberto-Reuters.txt"; bad_f.write_text("...", encoding="utf-8"); _age(bad_f, minutes=30)

    r = process.cmd_sweep(str(tdir), min_age_min=5, dry_run=True)
    assert "2026-06-03_11-00_Alberto-Reuters.txt" in r["reprocessed"]
    assert "2026-06-03_14-03_Ana-Leite.txt" in r["ok"]


def test_sweep_skips_too_new(tmp_path, monkeypatch):
    tdir = _vault(tmp_path, monkeypatch)
    f = tdir / "2026-06-03_11-00_Alberto-Reuters.txt"; f.write_text("...", encoding="utf-8"); _age(f, minutes=1)
    r = process.cmd_sweep(str(tdir), min_age_min=5, dry_run=True)
    assert f.name in r["skipped"] and f.name not in r["reprocessed"]


def test_sweep_skips_too_old(tmp_path, monkeypatch):
    tdir = _vault(tmp_path, monkeypatch)
    f = tdir / "2026-05-01_11-00_Alberto-Reuters.txt"; f.write_text("...", encoding="utf-8"); _age(f, days=20)
    r = process.cmd_sweep(str(tdir), min_age_min=5, dry_run=True, max_age_days=7)
    assert f.name in r["skipped"] and f.name not in r["reprocessed"]


def test_sweep_skips_unknown_folder(tmp_path, monkeypatch):
    tdir = _vault(tmp_path, monkeypatch)
    f = tdir / "2026-06-03_11-00_Ghost-Person.txt"; f.write_text("...", encoding="utf-8"); _age(f, minutes=30)
    r = process.cmd_sweep(str(tdir), min_age_min=5, dry_run=True)
    assert f.name in r["skipped"]


# ── fallback ──────────────────────────────────────────────────────────────────

def test_fallback_writes_dated_section(tmp_path, monkeypatch):
    _vault(tmp_path, monkeypatch)
    one = tmp_path / "Team" / "Ana-Leite" / "1on1.md"
    one.write_text("---\n---\n", encoding="utf-8")
    process._fallback_1on1(one, "2026-06-03")
    assert "## 2026-06-03" in one.read_text(encoding="utf-8")


# ── idempotent same-date replacement ──────────────────────────────────────────

def test_strip_replaces_only_target_section(tmp_path):
    p = tmp_path / "1on1.md"
    p.write_text(
        "---\nx\n---\n\n> callout\n\n## 2026-06-03\n\n- new\n\n---\n\n"
        "# Log\n\n---\n\n## 2026-05-27\n\n- old\n\n---\n",
        encoding="utf-8",
    )
    process._strip_dated_1on1(p, "2026-06-03")
    t = p.read_text(encoding="utf-8")
    assert "## 2026-06-03" not in t   # target removed
    assert "# Log" in t               # log header preserved
    assert "## 2026-05-27" in t       # other session preserved


def test_strip_noop_when_section_absent(tmp_path):
    p = tmp_path / "1on1.md"
    p.write_text("## 2026-05-27\n\n- old\n\n---\n", encoding="utf-8")
    process._strip_dated_1on1(p, "2026-06-03")
    assert "## 2026-05-27" in p.read_text(encoding="utf-8")
