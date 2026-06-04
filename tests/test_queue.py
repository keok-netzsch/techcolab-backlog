"""Tests for the decoupled recording queue (process.cmd_queue)."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "call-recorder"))

import process  # noqa: E402
import record  # noqa: E402


def _ollama_ok(monkeypatch):
    monkeypatch.setattr(process.requests, "get", lambda *a, **k: type("R", (), {})())


def _write_job(rdir, base, **fields):
    wav = rdir / f"{base}.wav"
    wav.write_bytes(b"RIFFfakeWAV")
    job = rdir / f"{base}.job.json"
    job.write_text(json.dumps(fields), encoding="utf-8")
    return job


def test_queue_transcribes_and_routes_person(tmp_path, monkeypatch):
    _ollama_ok(monkeypatch)
    rdir = tmp_path / "recordings"; rdir.mkdir()
    tpath = tmp_path / "transcripts" / "2026-06-04_11-00_Ana-Leite.txt"
    job = _write_job(
        rdir, "2026-06-04_11-00_Ana-Leite",
        wav="2026-06-04_11-00_Ana-Leite.wav", transcript=str(tpath),
        kind="person", target="Ana-Leite", lang="pt", date="2026-06-04", time="11-00",
    )
    monkeypatch.setattr(record, "transcribe", lambda w, language="pt": "transcricao fake")
    routed = {}
    monkeypatch.setattr(process, "cmd_transcript",
                        lambda target, t, date, structured=False, lang="pt": routed.update(target=target))

    r = process.cmd_queue(str(rdir))

    assert job.name in r["processed"]
    assert not job.exists()                          # job consumed
    assert tpath.read_text(encoding="utf-8") == "transcricao fake"
    assert routed["target"] == "Ana-Leite"           # routed to the person


def test_queue_routes_note_and_runs_coach_for_english(tmp_path, monkeypatch):
    _ollama_ok(monkeypatch)
    rdir = tmp_path / "recordings"; rdir.mkdir()
    tpath = tmp_path / "transcripts" / "2026-06-04_12-00_nota-avulsa.txt"
    _write_job(
        rdir, "2026-06-04_12-00_nota-avulsa",
        wav="2026-06-04_12-00_nota-avulsa.wav", transcript=str(tpath),
        kind="note", target=None, lang="en", date="2026-06-04", time="12-00", coach=True,
    )
    monkeypatch.setattr(record, "transcribe", lambda w, language="pt": "hello this is english")
    monkeypatch.setattr(process, "cmd_note", lambda *a, **k: None)
    coach_called = {}
    monkeypatch.setattr(process.subprocess, "run",
                        lambda *a, **k: coach_called.setdefault("ran", True))

    r = process.cmd_queue(str(rdir))
    assert len(r["processed"]) == 1
    assert coach_called.get("ran") is True           # English → coach ran


def test_queue_drops_orphan_job_when_wav_missing(tmp_path, monkeypatch):
    _ollama_ok(monkeypatch)
    rdir = tmp_path / "recordings"; rdir.mkdir()
    job = rdir / "x.job.json"
    job.write_text(json.dumps({"wav": "missing.wav", "transcript": "t.txt",
                               "kind": "note", "date": "2026-06-04"}), encoding="utf-8")
    r = process.cmd_queue(str(rdir))
    assert job.name in r["skipped"]
    assert not job.exists()                           # orphan dropped


def test_queue_empty_when_no_jobs(tmp_path):
    rdir = tmp_path / "recordings"; rdir.mkdir()
    r = process.cmd_queue(str(rdir))
    assert r == {"processed": [], "failed": [], "skipped": []}
