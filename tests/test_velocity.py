"""Tests for Action Velocity (idea-031): deterministic time-to-close of action items
tracked across dated 1:1 sessions. `today` is injected so aging is stable."""
import sys
from pathlib import Path

import pytest

CR_DIR = Path(__file__).resolve().parents[1] / "call-recorder"
sys.path.insert(0, str(CR_DIR))

import process  # noqa: E402


# Action "Revisar Docker" opens 2026-05-01, closes 2026-05-11 (10 days).
# "Concluir Alura" opens 2026-05-01, still open. "Enviar deck" opens+closes same day.
ONE_ON_ONE = """---
type: 1on1-log
---

## 2026-05-11

**Action items:**
- [x] (Kelvin) Revisar Docker
- [ ] (Ana) Concluir Alura
- [x] (Ana) Enviar deck

## 2026-05-01

**Action items:**
- [ ] (Kelvin) Revisar Docker
- [ ] (Ana) Concluir Alura
"""


def _sessions():
    return process.build_session_memory(ONE_ON_ONE)


def test_velocity_closed_action_days():
    vel = process.compute_action_velocity(_sessions(), today="2026-06-01")
    docker = next(a for a in vel["closed"] if "Docker" in a["text"])
    assert docker["opened"] == "2026-05-01"
    assert docker["closed"] == "2026-05-11"
    assert docker["days"] == 10


def test_velocity_same_session_open_and_close_is_zero_days():
    vel = process.compute_action_velocity(_sessions(), today="2026-06-01")
    deck = next(a for a in vel["closed"] if "deck" in a["text"])
    assert deck["days"] == 0            # only ever seen as [x], opened==closed


def test_velocity_open_action_ages_from_today():
    vel = process.compute_action_velocity(_sessions(), today="2026-05-31")
    alura = next(a for a in vel["open"] if "Alura" in a["text"])
    assert alura["opened"] == "2026-05-01"
    assert alura["age_days"] == 30      # 2026-05-01 -> 2026-05-31


def test_velocity_aggregate_metrics():
    vel = process.compute_action_velocity(_sessions(), today="2026-06-01")
    assert vel["count_closed"] == 2     # Docker + deck
    assert vel["count_open"] == 1       # Alura
    assert vel["avg_days_to_close"] == 5.0   # (10 + 0) / 2
    assert vel["median_days_to_close"] == 5.0


def test_velocity_flags_stale_open():
    vel = process.compute_action_velocity(_sessions(), today="2026-07-15")
    assert any("Alura" in a["text"] for a in vel["stale_open"])  # open > 30d


def test_velocity_empty_sessions():
    vel = process.compute_action_velocity([], today="2026-06-01")
    assert vel["count_closed"] == 0 and vel["count_open"] == 0
    assert vel["avg_days_to_close"] is None
    assert vel["median_days_to_close"] is None


def test_cmd_velocity_person_writes_digest(tmp_path, monkeypatch):
    monkeypatch.setattr(process, "VAULT", str(tmp_path))
    p = tmp_path / "Team" / "Ana-Leite"
    p.mkdir(parents=True)
    (p / "1on1.md").write_text(ONE_ON_ONE, encoding="utf-8")

    out = process.cmd_velocity(person_folder="Ana-Leite")

    assert out == str(p / "velocity.md")
    md = (p / "velocity.md").read_text(encoding="utf-8")
    assert "type: action-velocity" in md
    assert "## For future Claude" in md
    assert "Revisar Docker" in md
    assert "10d" in md                 # slowest closed action shows its duration


def test_cmd_velocity_all_writes_rollup(tmp_path, monkeypatch):
    monkeypatch.setattr(process, "VAULT", str(tmp_path))
    for folder in ("Ana-Leite", "Pedro-Klein"):
        d = tmp_path / "Team" / folder
        d.mkdir(parents=True)
        (d / "1on1.md").write_text(ONE_ON_ONE, encoding="utf-8")

    out = process.cmd_velocity()

    assert out == str(tmp_path / "Action-Velocity.md")
    roll = Path(out).read_text(encoding="utf-8")
    assert "# Action Velocity - Team" in roll
    assert "| Person | Closed | Avg (d) | Open | Stale |" in roll
    assert "Ana Leite" in roll and "Pedro Klein" in roll
    assert (tmp_path / "Team" / "Ana-Leite" / "velocity.md").exists()
