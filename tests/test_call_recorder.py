"""Tests for call-recorder pure functions and vault writers."""
import sys
from pathlib import Path

import pytest

# call-recorder/ is a sibling of tests/'s parent; add it to the import path.
_CR_DIR = Path(__file__).resolve().parent.parent / "call-recorder"
sys.path.insert(0, str(_CR_DIR))

coach = pytest.importorskip("coach")
process = pytest.importorskip("process")


# ── coach._transcript_stats ─────────────────────────────────────────────────
def test_transcript_stats_counts_words_and_duration():
    transcript = "[000.0s] hello there friend\n[030.0s] this is the end\n"
    stats = coach._transcript_stats(transcript)
    assert stats["words"] == 7
    assert stats["lines"] == 2
    assert stats["duration_min"] == 0.5  # 30s


def test_transcript_stats_empty():
    assert coach._transcript_stats("")["words"] == 0


# ── coach._clean_transcript ─────────────────────────────────────────────────
def test_clean_transcript_removes_repeated_tail_spam():
    # detection looks only at the last 20% of lines; need >=5 spam hits there
    body = "\n".join(f"[{i:03d}.0s] sentence number {i} with content" for i in range(12))
    spam = "\n".join(f"[{200 + i}.0s] Let's go" for i in range(25))
    cleaned = coach._clean_transcript(body + "\n" + spam)
    assert "Let's go" not in cleaned
    assert "sentence number 0" in cleaned


def test_clean_transcript_short_unchanged():
    short = "[000.0s] just one line"
    assert coach._clean_transcript(short) == short


# ── coach._sample_excerpt ────────────────────────────────────────────────────
def test_sample_excerpt_returns_full_when_short():
    text = "short text"
    assert coach._sample_excerpt(text, target_chars=5000) == text


def test_sample_excerpt_samples_when_long():
    text = "x" * 12000
    out = coach._sample_excerpt(text, target_chars=5000)
    assert len(out) < len(text)
    assert "[... middle of transcript ...]" in out


# ── process.save_block ───────────────────────────────────────────────────────
_FRONTMATTER = "---\nperson: Ana\ntype: 1on1\n---\n\n## Old session\n\nold body\n"


def test_save_block_prepend_inserts_after_frontmatter(tmp_path):
    f = tmp_path / "1on1.md"
    f.write_text(_FRONTMATTER, encoding="utf-8")
    process.save_block(str(f), "## New session\n\nnew body", mode="prepend")
    out = f.read_text(encoding="utf-8")
    # Frontmatter preserved at the very top
    assert out.startswith("---\nperson: Ana\ntype: 1on1\n---")
    # Newest session appears before the old one
    assert out.index("New session") < out.index("Old session")


def test_save_block_append_adds_at_end(tmp_path):
    f = tmp_path / "Overview.md"
    f.write_text(_FRONTMATTER, encoding="utf-8")
    process.save_block(str(f), "appended note", mode="append")
    out = f.read_text(encoding="utf-8")
    assert out.index("Old session") < out.index("appended note")


def test_save_block_creates_file_when_missing(tmp_path):
    f = tmp_path / "nested" / "new.md"
    process.save_block(str(f), "first content", mode="prepend")
    assert f.exists()
    assert "first content" in f.read_text(encoding="utf-8")
