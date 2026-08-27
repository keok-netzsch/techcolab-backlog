"""Tests for the call-recorder audio retention policy (record.prune_old_recordings)."""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "call-recorder"))

import record  # noqa: E402


def _touch(path, age_days=0):
    open(path, "w").close()
    if age_days:
        ts = time.time() - age_days * 86400
        os.utime(path, (ts, ts))


def test_removes_wav_older_than_retention(tmp_path):
    _touch(tmp_path / "recent.wav", age_days=1)
    _touch(tmp_path / "old.wav", age_days=10)
    removed = record.prune_old_recordings(str(tmp_path), days=7)
    assert removed == 1
    assert (tmp_path / "recent.wav").exists()
    assert not (tmp_path / "old.wav").exists()


def test_keeps_non_wav_files(tmp_path):
    _touch(tmp_path / "notes.txt", age_days=30)
    removed = record.prune_old_recordings(str(tmp_path), days=7)
    assert removed == 0
    assert (tmp_path / "notes.txt").exists()


def test_missing_directory_is_safe(tmp_path):
    assert record.prune_old_recordings(str(tmp_path / "nope"), days=7) == 0


def test_default_retention_is_seven_days():
    assert record.RECORDINGS_RETENTION_DAYS == 7


# ── Retention is driven by successful transcription, not by age (2026-08-27) ──
# The old policy deleted by mtime alone: a recording whose transcription had been
# failing all week was destroyed exactly like one that succeeded. Worse,
# autocapture writes `.pending.json` sidecars that nothing consumes yet, so every
# auto-captured call was on a silent 7-day path to deletion.

import json


def _wav_with_job(tmp_path, stem, *, transcript_bytes=None, done=True,
                  age_days=10, pending=False):
    wav = tmp_path / f"{stem}.wav"
    _touch(wav, age_days=age_days)
    if pending:
        (tmp_path / f"{stem}.pending.json").write_text("{}", encoding="utf-8")
        return wav
    tpath = tmp_path / f"{stem}.txt"
    if transcript_bytes is not None:
        tpath.write_text("x" * transcript_bytes, encoding="utf-8")
    meta = {"wav": wav.name, "transcript": str(tpath)}
    suffix = ".job.json.done" if done else ".job.json"
    (tmp_path / f"{stem}{suffix}").write_text(json.dumps(meta), encoding="utf-8")
    return wav


def test_deletes_only_when_transcript_succeeded(tmp_path):
    wav = _wav_with_job(tmp_path, "ok", transcript_bytes=5000)
    assert record.prune_old_recordings(str(tmp_path), days=7) == 1
    assert not wav.exists()


def test_failed_transcription_is_quarantined_not_deleted(tmp_path):
    wav = _wav_with_job(tmp_path, "broke", transcript_bytes=None)
    assert record.prune_old_recordings(str(tmp_path), days=7) == 0
    assert not wav.exists()                                   # saiu de recordings/
    assert (tmp_path / "failed" / "broke.wav").exists()       # mas nao foi apagado


def test_degenerate_transcript_counts_as_failure(tmp_path):
    """Whisper collapsing to '.' produced a tiny file the old code called success."""
    _wav_with_job(tmp_path, "sparse", transcript_bytes=3)
    assert record.prune_old_recordings(str(tmp_path), days=7) == 0
    assert (tmp_path / "failed" / "sparse.wav").exists()


def test_queued_recording_is_never_deleted_by_age(tmp_path):
    wav = _wav_with_job(tmp_path, "queued", transcript_bytes=None, done=False)
    assert record.prune_old_recordings(str(tmp_path), days=7) == 0
    assert wav.exists()


def test_autocapture_pending_is_never_deleted_by_age(tmp_path):
    """classify.py does not exist yet; these must survive until it does."""
    wav = _wav_with_job(tmp_path, "auto", pending=True)
    assert record.prune_old_recordings(str(tmp_path), days=7) == 0
    assert wav.exists()
