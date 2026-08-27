"""Retry accounting on the recording queue (process._bump_retry).

Before this, a job that could never be transcribed was left untouched on failure,
so it retried every night forever and nothing recorded that it was failing. The
counter parks it after MAX_JOB_RETRIES — the audio itself is never deleted here;
retention quarantines it into failed/ instead.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "call-recorder"))

import process  # noqa: E402


def _job(tmp_path, **extra):
    p = tmp_path / "2026-08-27_10-00_Someone.job.json"
    p.write_text(json.dumps({"wav": "x.wav", **extra}), encoding="utf-8")
    return p


def test_first_failure_counts_one(tmp_path):
    p = _job(tmp_path)
    assert process._bump_retry(p, "boom") == 1
    assert json.loads(p.read_text(encoding="utf-8"))["retry_count"] == 1


def test_counter_accumulates(tmp_path):
    p = _job(tmp_path)
    for expected in (1, 2, 3):
        assert process._bump_retry(p, "boom") == expected


def test_error_and_timestamp_are_recorded(tmp_path):
    p = _job(tmp_path)
    process._bump_retry(p, "CUDA melted")
    meta = json.loads(p.read_text(encoding="utf-8"))
    assert "CUDA melted" in meta["last_error"]
    assert meta["last_attempt"]


def test_long_error_is_truncated(tmp_path):
    p = _job(tmp_path)
    process._bump_retry(p, "x" * 5000)
    assert len(json.loads(p.read_text(encoding="utf-8"))["last_error"]) <= 300


def test_unreadable_sidecar_does_not_loop_forever(tmp_path):
    p = tmp_path / "broken.job.json"
    p.write_text("{not json", encoding="utf-8")
    assert process._bump_retry(p, "boom") > process.MAX_JOB_RETRIES


def test_existing_count_is_preserved(tmp_path):
    p = _job(tmp_path, retry_count=2)
    assert process._bump_retry(p, "boom") == 3
