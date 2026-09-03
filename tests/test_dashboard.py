"""Tests for the Action Dashboard generator (idea-031): consolidate all open
`- [ ]` tasks across the vault into a single grouped markdown note."""
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

CR_DIR = Path(__file__).resolve().parents[1] / "call-recorder"
sys.path.insert(0, str(CR_DIR))

import process


def _dash_path(vault):
    """Onde o dashboard e gravado.

    Desde 2026-09-02 e `_reports/Action-Dashboard.md`, nao a raiz do vault: saida
    gerada por codigo nao mora ao lado do `_CLAUDE.md`. O teste pergunta ao proprio
    modulo em vez de repetir o caminho — repetir e como o leitor da daily acabou
    apontando para uma pasta que nao existia.
    """
    return vault / process.REPORTS_DIRNAME / process.DASHBOARD_FILE  # noqa: E402


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
    out = _dash_path(vault).read_text(encoding="utf-8")
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
    out = _dash_path(vault).read_text(encoding="utf-8")
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
    out = _dash_path(vault).read_text(encoding="utf-8")
    assert "preencher nome" not in out
    assert "acao com dono" in out


def test_dashboard_empty_vault(vault):
    counts = process.cmd_dashboard()
    assert counts["total"] == 0
    assert _dash_path(vault).exists()


def test_dashboard_dedups_repeated_action(vault):
    # Same action carried across the cumulative log, the per-meeting note, a
    # daily note and two project notes must count once, keeping every backlink.
    line = "- [ ] (Ana) Entregar documentacao do pipeline\n"
    _write(vault / "Team" / "Ana" / "1on1.md", line)
    _write(vault / "Team" / "Ana" / "1on1" / "2026-05-25_1on1_Ana.md", line)
    _write(vault / "Daily" / "2026-05-26.md", line)
    _write(vault / "Projects" / "p1.md", line)
    _write(vault / "Projects" / "p2.md", line)

    counts = process.cmd_dashboard()

    assert counts["total"] == 1          # five copies collapse to one action
    assert counts["undated"] == 1
    out = _dash_path(vault).read_text(encoding="utf-8")
    assert out.count("Entregar documentacao do pipeline") == 1
    assert "×5" in out                   # ×5 duplicate multiplier shown
    assert "[[1on1]]" in out                  # at least one source preserved


def test_dashboard_dedup_is_case_and_whitespace_insensitive(vault):
    _write(vault / "a.md", "- [ ] (Kelvin)  Revisar   Deck \n")
    _write(vault / "b.md", "- [ ] (kelvin) revisar deck\n")

    counts = process.cmd_dashboard()

    assert counts["total"] == 1


def test_dashboard_excludes_agent_reports(vault):
    # Daily agent snapshots echo open actions; they are not a task source.
    _write(vault / "agent-reports" / "report-2026-06-19.md",
           "- [ ] (Kelvin) acao ecoada no report @2026-06-19\n")
    _write(vault / "Projects" / "real.md",
           "- [ ] (Kelvin) acao real do projeto\n")

    counts = process.cmd_dashboard()

    assert counts["total"] == 1
    out = _dash_path(vault).read_text(encoding="utf-8")
    assert "acao ecoada" not in out
    assert "acao real do projeto" in out


def test_dashboard_skips_closed_backlog_notes(vault):
    # A discarded/finished idea's open sub-todos are stale -> whole note skipped.
    _write(vault / "backlog items" / "idea-028.md",
           "---\nid: idea-028\nstatus: descartado\n---\n"
           "- [ ] (Kelvin) instalar Tailscale @2026-06-05\n")
    _write(vault / "backlog items" / "idea-099.md",
           "---\nid: idea-099\nstatus: concluído\n---\n"
           "- [ ] (Kelvin) tarefa ja concluida\n")
    _write(vault / "backlog items" / "idea-031.md",
           "---\nid: idea-031\nstatus: em desenvolvimento\n---\n"
           "- [ ] (Kelvin) feature ativa do roadmap @2026-08-14\n")

    counts = process.cmd_dashboard()

    assert counts["total"] == 1                 # only the active idea contributes
    out = _dash_path(vault).read_text(encoding="utf-8")
    assert "instalar Tailscale" not in out
    assert "tarefa ja concluida" not in out
    assert "feature ativa do roadmap" in out


def test_dashboard_caps_source_links(vault):
    # More than MAX_SOURCES origins -> show the cap then a "+N" overflow marker.
    line = "- [ ] (Kelvin) acao muito repetida\n"
    for i in range(process.MAX_SOURCES + 3):
        _write(vault / f"src{i}.md", line)

    process.cmd_dashboard()

    out = _dash_path(vault).read_text(encoding="utf-8")
    assert f"+{3}" in out                     # 3 sources beyond the cap
    assert out.count("[[src") == process.MAX_SOURCES
