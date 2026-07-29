"""Tests for Team Health Metrics (idea-031): deterministic consolidation of 1:1
recency + open/stale action load + PDI/OKR alerts into a 0-100 score. `today`
injected for stable recency math."""
import sys
from pathlib import Path

import pytest

CR_DIR = Path(__file__).resolve().parents[1] / "call-recorder"
sys.path.insert(0, str(CR_DIR))

import process  # noqa: E402

TODAY = "2026-07-29"


def _mem(last_date, sessions=3):
    return {"session_count": sessions, "first_date": "2026-01-01",
            "last_date": last_date, "open_actions": [], "recurring_topics": []}


def _vel(open_n=0, stale_n=0):
    return {"closed": [], "open": [{}] * open_n, "stale_open": [{}] * stale_n,
            "count_closed": 0, "count_open": open_n, "avg_days_to_close": None,
            "median_days_to_close": None}


def test_health_healthy_when_recent_and_clean():
    h = process.compute_person_health(_mem("2026-07-20"), _vel(), 0, today=TODAY)
    assert h["score"] == 100 and h["status"] == "healthy"
    assert h["signals"] == []


def test_health_no_data_when_no_sessions():
    h = process.compute_person_health(_mem(None, sessions=0), _vel(), 0, today=TODAY)
    assert h["status"] == "no-data" and h["score"] is None


def test_health_penalizes_stale_contact():
    h = process.compute_person_health(_mem("2026-05-01"), _vel(), 0, today=TODAY)
    assert h["days_since_last"] == 89
    assert h["score"] == 70            # -30 for >60d
    assert h["status"] == "watch"


def test_health_penalizes_alerts_and_stale_actions():
    h = process.compute_person_health(_mem("2026-07-20"), _vel(open_n=3, stale_n=2), 3, today=TODAY)
    # -10 (2 stale) -15 (3 alerts) = -25 -> 75
    assert h["score"] == 75 and h["status"] == "healthy"


def test_health_backlog_penalty_over_five_open():
    h = process.compute_person_health(_mem("2026-07-20"), _vel(open_n=8), 0, today=TODAY)
    assert h["score"] == 94            # -min(15, 2*(8-5)) = -6
    assert any("open actions" in s for s in h["signals"])


def test_health_worst_case_is_at_risk():
    # penalty caps sum to 95 (30 recency + 25 stale + 15 backlog + 25 alerts),
    # so the worst realistic score is 5 — still firmly at-risk, never negative.
    h = process.compute_person_health(_mem("2026-01-01"), _vel(open_n=20, stale_n=20), 20, today=TODAY)
    assert h["score"] == 5 and h["status"] == "at-risk"
    assert h["score"] >= 0             # never clamps below zero


def test_cmd_health_person_writes_digest(tmp_path, monkeypatch):
    monkeypatch.setattr(process, "VAULT", str(tmp_path))
    p = tmp_path / "Team" / "Ana-Leite"
    p.mkdir(parents=True)
    (p / "1on1.md").write_text(
        "## 2026-07-20\n\n**Action items:**\n- [ ] (Ana) tarefa aberta\n", encoding="utf-8")
    (p / "OKR.md").write_text("- **Deadline:** 2026-05-01\n", encoding="utf-8")
    (p / "PDI.md").write_text("", encoding="utf-8")

    out = process.cmd_health(person_folder="Ana-Leite")

    assert out == str(p / "health.md")
    md = (p / "health.md").read_text(encoding="utf-8")
    assert "type: team-health" in md
    assert "## For future Claude" in md
    assert "Score:" in md


def test_cmd_health_all_writes_rollup(tmp_path, monkeypatch):
    monkeypatch.setattr(process, "VAULT", str(tmp_path))
    for folder in ("Ana-Leite", "Pedro-Klein"):
        d = tmp_path / "Team" / folder
        d.mkdir(parents=True)
        (d / "1on1.md").write_text("## 2026-07-20\n\n**Topics:**\n- x\n", encoding="utf-8")
        (d / "OKR.md").write_text("", encoding="utf-8")
        (d / "PDI.md").write_text("", encoding="utf-8")

    out = process.cmd_health()

    assert out == str(tmp_path / "Team-Health.md")
    roll = Path(out).read_text(encoding="utf-8")
    assert "# Team Health" in roll
    assert "| Person | Score | Status |" in roll
    assert "Ana Leite" in roll and "Pedro Klein" in roll
    assert (tmp_path / "Team" / "Ana-Leite" / "health.md").exists()
