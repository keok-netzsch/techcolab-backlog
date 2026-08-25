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


def test_strip_removes_section_at_eof_without_trailing_sep(tmp_path):
    # A section can be the last one in the file with no trailing `---`.
    p = tmp_path / "1on1.md"
    p.write_text("## 2026-05-27\n\n- keep\n\n---\n\n## 2026-06-03\n\n- last, no sep\n", encoding="utf-8")
    process._strip_dated_1on1(p, "2026-06-03")
    t = p.read_text(encoding="utf-8")
    assert "## 2026-06-03" not in t
    assert "## 2026-05-27" in t


def test_strip_removes_all_duplicate_sections(tmp_path):
    p = tmp_path / "1on1.md"
    p.write_text(
        "## 2026-06-03\n\n- A\n\n---\n\n## 2026-06-03\n\n- B (dup)\n\n---\n\n## 2026-05-27\n\n- old\n\n---\n",
        encoding="utf-8",
    )
    process._strip_dated_1on1(p, "2026-06-03")
    t = p.read_text(encoding="utf-8")
    assert t.count("## 2026-06-03") == 0   # both duplicates gone
    assert "## 2026-05-27" in t


# ── language sidecar (regression: English 1:1 stamped as lang: pt) ────────────

def _sweep_note(tdir, monkeypatch, name, sidecar_lang=None, sweep_lang="pt"):
    """Run cmd_sweep over a single note transcript, capturing the lang it passes."""
    t = tdir / name
    t.write_text("In Brazil as well, yes, in Curitiba.", encoding="utf-8")
    _age(t, days=1)
    if sidecar_lang is not None:
        (tdir / (name + ".lang")).write_text(sidecar_lang, encoding="utf-8")

    seen = {}

    def _fake_note(path, date, lang="pt", time_str=None):
        seen["lang"] = lang

    monkeypatch.setattr(process, "cmd_note", _fake_note)
    monkeypatch.setattr(process.requests, "get", lambda *a, **k: None)
    process.cmd_sweep(str(tdir), min_age_min=0, lang=sweep_lang)
    return seen.get("lang")


def test_sweep_uses_lang_sidecar_over_its_default(tmp_path, monkeypatch):
    """The .lang written by Whisper must win over the sweep's blanket default.

    Regression for 2026-08-10: an English recording was transcribed with
    `lang: auto`, Whisper detected `en` and wrote it to the sidecar, but the
    sweep recreated the note with its default `pt`. The English Coach filters on
    `lang: en`, so 36 KB of English conversation was invisible to it.
    """
    tdir = _vault(tmp_path, monkeypatch)
    got = _sweep_note(tdir, monkeypatch, "2026-08-10_10-01_nota-avulsa.txt",
                      sidecar_lang="en", sweep_lang="pt")
    assert got == "en"


def test_sweep_falls_back_to_default_without_sidecar(tmp_path, monkeypatch):
    tdir = _vault(tmp_path, monkeypatch)
    got = _sweep_note(tdir, monkeypatch, "2026-08-12_09-00_nota-avulsa.txt",
                      sidecar_lang=None, sweep_lang="pt")
    assert got == "pt"


def test_sweep_ignores_empty_sidecar(tmp_path, monkeypatch):
    tdir = _vault(tmp_path, monkeypatch)
    got = _sweep_note(tdir, monkeypatch, "2026-08-13_09-00_nota-avulsa.txt",
                      sidecar_lang="   ", sweep_lang="pt")
    assert got == "pt"
