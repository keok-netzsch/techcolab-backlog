"""Tests for backlog/daily_log.py"""

import pytest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

from backlog.schema import Idea


# Patch VAULT_ROOT so log files go to a temp dir during tests
@pytest.fixture
def log_dir(tmp_path, monkeypatch):
    import backlog.daily_log as dl
    monkeypatch.setattr(dl, "_log_path", lambda today=None: tmp_path / f"diario-{(today or date.today()).isoformat()}.md")
    return tmp_path


def _make_idea(**kwargs):
    defaults = dict(id="idea-001", title="Ideia de teste", status="backlog")
    defaults.update(kwargs)
    return Idea(**defaults)


def test_log_entry_creates_file(log_dir):
    from backlog.daily_log import log_entry
    idea = _make_idea()
    log_entry("criada", idea)
    files = list(log_dir.iterdir())
    assert len(files) == 1
    assert files[0].name.startswith("diario-")


def test_log_entry_has_header_on_new_file(log_dir):
    from backlog.daily_log import log_entry
    idea = _make_idea()
    log_entry("criada", idea)
    content = (log_dir / f"diario-{date.today().isoformat()}.md").read_text(encoding="utf-8")
    assert "type: daily-log" in content
    assert "Log do dia" in content


def test_log_entry_label_criada(log_dir):
    from backlog.daily_log import log_entry
    idea = _make_idea()
    log_entry("criada", idea)
    content = (log_dir / f"diario-{date.today().isoformat()}.md").read_text(encoding="utf-8")
    assert "`CRIADA`" in content
    assert "idea-001" in content
    assert "Ideia de teste" in content


def test_log_entry_label_concluida(log_dir):
    from backlog.daily_log import log_entry
    idea = _make_idea(status="concluído")
    log_entry("concluida", idea)
    content = (log_dir / f"diario-{date.today().isoformat()}.md").read_text(encoding="utf-8")
    assert "`CONCLUÍDA`" in content


def test_log_entry_label_todo(log_dir):
    from backlog.daily_log import log_entry
    idea = _make_idea()
    log_entry("todo_concluido", idea, "Revisar dados")
    content = (log_dir / f"diario-{date.today().isoformat()}.md").read_text(encoding="utf-8")
    assert "`TO-DO`" in content
    assert "Revisar dados" in content


def test_log_entry_appends_multiple(log_dir):
    from backlog.daily_log import log_entry
    idea = _make_idea()
    log_entry("criada", idea)
    log_entry("alterada", idea, "status: backlog -> em análise")
    content = (log_dir / f"diario-{date.today().isoformat()}.md").read_text(encoding="utf-8")
    assert content.count("`CRIADA`") == 1
    assert content.count("`ALTERADA`") == 1


def test_log_entry_detail_appended(log_dir):
    from backlog.daily_log import log_entry
    idea = _make_idea()
    log_entry("alterada", idea, "status: backlog -> em análise")
    content = (log_dir / f"diario-{date.today().isoformat()}.md").read_text(encoding="utf-8")
    assert "status: backlog -> em análise" in content
