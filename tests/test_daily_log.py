"""Tests for backlog/daily_log.py

Since 2026-08-26 (idea-067) entries go to the vault's canonical daily note
(`Daily/YYYY-MM-DD.md`, `type: daily`) under a "## 🗂️ Backlog" section, instead
of the retired parallel diary at `Log/diario-YYYY-MM-DD.md`.
"""

from datetime import date

import pytest

from backlog.schema import Idea


@pytest.fixture
def daily_dir(tmp_path, monkeypatch):
    """Redirect the daily note into a temp dir."""
    import backlog.daily_log as dl
    daily = tmp_path / "Daily"
    daily.mkdir()
    monkeypatch.setattr(
        dl, "_daily_note_path",
        lambda today=None: daily / f"{(today or date.today()).isoformat()}.md",
    )
    return daily


def _note(daily_dir):
    return (daily_dir / f"{date.today().isoformat()}.md").read_text(encoding="utf-8")


def _make_idea(**kwargs):
    defaults = dict(id="idea-001", title="Ideia de teste", status="backlog")
    defaults.update(kwargs)
    return Idea(**defaults)


def test_log_entry_creates_daily_note(daily_dir):
    from backlog.daily_log import log_entry
    log_entry("criada", _make_idea())
    files = list(daily_dir.iterdir())
    assert len(files) == 1
    assert files[0].name == f"{date.today().isoformat()}.md"


def test_new_note_uses_canonical_daily_type(daily_dir):
    """`daily`, not the deprecated `daily-log` (2026-07-29 type-taxonomy ADR)."""
    from backlog.daily_log import log_entry
    log_entry("criada", _make_idea())
    content = _note(daily_dir)
    assert "type: daily\n" in content
    assert "daily-log" not in content
    assert "## 🗂️ Backlog" in content


def test_log_entry_label_criada(daily_dir):
    from backlog.daily_log import log_entry
    log_entry("criada", _make_idea())
    content = _note(daily_dir)
    assert "`CRIADA`" in content
    assert "idea-001" in content
    assert "Ideia de teste" in content


def test_log_entry_label_concluida(daily_dir):
    from backlog.daily_log import log_entry
    log_entry("concluida", _make_idea(status="concluído"))
    assert "`CONCLUÍDA`" in _note(daily_dir)


def test_log_entry_label_todo(daily_dir):
    from backlog.daily_log import log_entry
    log_entry("todo_concluido", _make_idea(), "Revisar dados")
    content = _note(daily_dir)
    assert "`TO-DO`" in content
    assert "Revisar dados" in content


def test_log_entry_appends_multiple(daily_dir):
    from backlog.daily_log import log_entry
    idea = _make_idea()
    log_entry("criada", idea)
    log_entry("alterada", idea, "status: backlog -> em análise")
    content = _note(daily_dir)
    assert content.count("`CRIADA`") == 1
    assert content.count("`ALTERADA`") == 1
    assert content.count("## 🗂️ Backlog") == 1


def test_log_entry_detail_appended(daily_dir):
    from backlog.daily_log import log_entry
    log_entry("alterada", _make_idea(), "status: backlog -> em análise")
    assert "status: backlog -> em análise" in _note(daily_dir)


def test_entry_inserted_into_existing_backlog_section(daily_dir):
    """An existing note keeps its other sections, and the next header stays separated."""
    from backlog.daily_log import log_entry
    path = daily_dir / f"{date.today().isoformat()}.md"
    path.write_text(
        "---\ndate: 2026-08-26\ntype: daily\n---\n\n"
        "# Wednesday\n\n"
        "## 🎯 Foco de hoje\n- item de foco\n\n"
        "## 🗂️ Backlog\n- 09:00 `CRIADA` [idea-001] Anterior\n\n"
        "## ✅ Feito\n- algo feito\n",
        encoding="utf-8",
    )
    log_entry("concluida", _make_idea(id="idea-002", title="Nova"))
    content = _note(daily_dir)
    assert "- item de foco" in content
    assert "- algo feito" in content
    assert "[idea-001] Anterior" in content
    # new entry lands inside the Backlog section, above the next header
    backlog_part = content.split("## 🗂️ Backlog")[1].split("## ")[0]
    assert "[idea-002] Nova" in backlog_part
    # blank line preserved before the following section
    assert "\n\n## ✅ Feito" in content


def test_read_log_lines_reads_new_and_legacy(tmp_path, monkeypatch):
    """One reader covers both locations, so history survives the move."""
    import backlog.daily_log as dl
    monkeypatch.setattr(dl, "VAULT_ROOT", tmp_path)
    (tmp_path / "Daily").mkdir()
    (tmp_path / "Log").mkdir()

    new_day = date(2026, 8, 27)
    (tmp_path / "Daily" / f"{new_day.isoformat()}.md").write_text(
        "---\ntype: daily\n---\n\n# Thu\n\n"
        "## 🎯 Foco\n- nao e log\n\n"
        "## 🗂️ Backlog\n- 10:00 `CRIADA` [idea-100] Nova\n\n"
        "## ✅ Feito\n- tambem nao e log\n",
        encoding="utf-8",
    )
    old_day = date(2026, 5, 18)
    (tmp_path / "Log" / f"diario-{old_day.isoformat()}.md").write_text(
        "---\ntype: daily\n---\n\n# Log do dia — 18/05/2026\n\n"
        "- 11:43 `CRIADA` [idea-010] Antiga\n",
        encoding="utf-8",
    )

    new_lines = dl.read_log_lines(new_day)
    assert new_lines == ["- 10:00 `CRIADA` [idea-100] Nova"]
    # only the Backlog section — other sections must not leak in
    assert not any("nao e log" in ln for ln in new_lines)

    old_lines = dl.read_log_lines(old_day)
    assert old_lines == ["- 11:43 `CRIADA` [idea-010] Antiga"]

    assert dl.read_log_lines(date(2020, 1, 1)) == []


def test_section_created_when_missing_from_existing_note(daily_dir):
    from backlog.daily_log import log_entry
    path = daily_dir / f"{date.today().isoformat()}.md"
    path.write_text(
        "---\ndate: 2026-08-26\ntype: daily\n---\n\n# Wednesday\n\n"
        "## 🎯 Foco de hoje\n- so foco\n",
        encoding="utf-8",
    )
    log_entry("criada", _make_idea())
    content = _note(daily_dir)
    assert "- so foco" in content
    assert "## 🗂️ Backlog" in content
    assert "[idea-001]" in content


# ── Real path resolution ─────────────────────────────────────────────────────
# Every other test here monkeypatches _daily_note_path away, which is exactly how
# the wrong root survived: the function resolved to <vault>/App/Personal toolkit/
# Daily/ instead of the vault-root Daily/, so entries landed in a folder nothing
# reads and "diario unico" (Toolkit 2.0 Pacote 2) never actually happened.

def test_daily_note_resolves_under_vault_base():
    from pathlib import Path

    from backlog.daily_log import _daily_note_path
    from config import VAULT_BASE, VAULT_ROOT

    resolved = _daily_note_path(date(2026, 9, 1))
    assert resolved == Path(VAULT_BASE) / "Daily" / "2026-09-01.md"
    # VAULT_ROOT is the app's working area, one level deeper — never the daily note's home.
    assert Path(VAULT_ROOT) not in resolved.parents
