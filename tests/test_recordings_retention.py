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
