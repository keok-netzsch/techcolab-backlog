"""Tests for the Action Dashboard generator (idea-031): consolidate all open
`- [ ]` tasks across the vault into a single grouped markdown note."""
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

CR_DIR = Path(__file__).resolve().parents[1] / "call-recorder"
sys.path.insert(0, str(CR_DIR))

import process  # noqa: E402


@pytest.fixture
def vault(tmp_path, monkeypatch):
    monkeypatch.setattr(process, "VAULT", str(tmp_path))
    return tmp_path


def _write(p: Path, text: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_dashboard_groups_by_due(vault):
    today = datetime.now().date()
    past   = (today - timedelta(days=3)).strftime("%Y-%m-%d")
    future = (today + timedelta(days=5)).strftime("%Y-%m-%d")
    td     = today.strftime("%Y-%m-%d")

    _write(vault / "Projects" / "a.md",
           f"# A\n- [ ] (Kelvin) tarefa atrasada @{past}\n- [ ] (Ana) sem prazo aqui\n")
    _write(vault / "Team" / "b.md",
           f"- [ ] (Kelvin) entregar hoje @{td}\n- [ ] tarefa sem dono @{future}\n"
           f"- [x] (Kelvin) ja feita @{past}\n")  # done task must be ignored

    counts = process.cmd_dashboard()

    assert counts == {"total": 4, "overdue": 1, "today": 1, "upcoming": 1, "undated": 1}
    out = (vault / "Action-Dashboard.md").read_text(encoding="utf-8")
    assert "## Atrasadas (1)" in out
    assert "## Hoje (1)" in out
    assert "## Proximas (1)" in out
    assert "## Sem prazo (1)" in out
    assert "ja feita" not in out                 # done task excluded
    assert "(sem dono)" in out                   # missing owner labelled
    assert "[[b]]" in out and "[[a]]" in out     # source backlinks


def test_dashboard_excludes_dirs_and_self(vault):
    _write(vault / ".obsidian" / "x.md", "- [ ] (Kelvin) ignore me\n")
    _write(vault / "Archive" / "old.md", "- [ ] (Kelvin) archived\n")
    _write(vault / "live.md", "- [ ] (Kelvin) real task\n")
    # pre-existing dashboard must not be re-scanned into itself
    _write(vault / "Action-Dashboard.md", "- [ ] (Kelvin) stale dashboard line\n")

    counts = process.cmd_dashboard()

    assert counts["total"] == 1
    out = (vault / "Action-Dashboard.md").read_text(encoding="utf-8")
    assert "real task" in out
    assert "ignore me" not in out
    assert "archived" not in out
    assert "stale dashboard line" not in out


def test_dashboard_skips_plain_checklist_noise(vault):
    # plain `- [ ]` with neither owner nor due is template/checklist noise -> excluded
    _write(vault / "Templates" / "tpl.md",
           "# Checklist\n- [ ] preencher nome\n- [ ] preencher data\n")
    _write(vault / "real.md",
           "- [ ] (Kelvin) acao com dono\n- [ ] tarefa com prazo @2026-09-01\n")

    counts = process.cmd_dashboard()

    assert counts["total"] == 2  # only the owner + the dated task
    out = (vault / "Action-Dashboard.md").read_text(encoding="utf-8")
    assert "preencher nome" not in out
    assert "acao com dono" in out


def test_dashboard_empty_vault(vault):
    counts = process.cmd_dashboard()
    assert counts["total"] == 0
    assert (vault / "Action-Dashboard.md").exists()
