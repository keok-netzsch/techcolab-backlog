"""Tests for backlog/store.py"""

import pytest
from datetime import date
from pathlib import Path
import tempfile

from backlog.store import BacklogStore, _parse_todos, _render_todos
from backlog.schema import Idea


# ── _parse_todos / _render_todos ─────────────────────────────────────────────

def test_parse_todos_pending():
    raw = "- [ ] Fazer relatório"
    todos = _parse_todos(raw)
    assert len(todos) == 1
    assert todos[0]["done"] is False
    assert todos[0]["text"] == "Fazer relatório"
    assert todos[0]["due_date"] is None


def test_parse_todos_done():
    raw = "- [x] Tarefa concluída"
    todos = _parse_todos(raw)
    assert todos[0]["done"] is True


def test_parse_todos_with_due_date():
    raw = "- [ ] Revisar dados @2026-06-15"
    todos = _parse_todos(raw)
    assert todos[0]["due_date"] == "2026-06-15"
    assert todos[0]["text"] == "Revisar dados"


def test_parse_todos_multiple():
    raw = "- [ ] Task A\n- [x] Task B @2026-05-01\n- [ ] Task C"
    todos = _parse_todos(raw)
    assert len(todos) == 3
    assert todos[1]["done"] is True
    assert todos[1]["due_date"] == "2026-05-01"


def test_render_todos_roundtrip():
    todos = [
        {"done": False, "text": "Task A", "due_date": None},
        {"done": True, "text": "Task B", "due_date": "2026-06-01"},
    ]
    rendered = _render_todos(todos)
    parsed = _parse_todos(rendered)
    assert parsed[0]["text"] == "Task A"
    assert parsed[0]["done"] is False
    assert parsed[1]["done"] is True
    assert parsed[1]["due_date"] == "2026-06-01"


def test_render_todos_empty():
    assert _render_todos([]) == ""


# ── BacklogStore ─────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_store(tmp_path):
    return BacklogStore(tmp_path)


def test_create_assigns_id(tmp_store):
    idea = tmp_store.create(title="Primeira ideia")
    assert idea.id == "idea-001"


def test_create_sequential_ids(tmp_store):
    a = tmp_store.create(title="Ideia A")
    b = tmp_store.create(title="Ideia B")
    assert a.id == "idea-001"
    assert b.id == "idea-002"


def test_save_creates_file(tmp_store):
    idea = tmp_store.create(title="Arquivo criado")
    path = tmp_store.dir / "idea-001.md"
    assert path.exists()


def test_save_and_load_roundtrip(tmp_store):
    idea = tmp_store.create(
        title="Roundtrip test",
        status="em análise",
        priority="alta",
        area="dados",
        description="Descrição de teste",
        notes="Nota aqui",
        due_date=date(2026, 7, 1),
        todos=[{"text": "Fazer algo", "done": False, "due_date": "2026-06-15"}],
    )
    loaded = tmp_store.load_by_id("idea-001")
    assert loaded is not None
    assert loaded.title == "Roundtrip test"
    assert loaded.status == "em análise"
    assert loaded.priority == "alta"
    assert loaded.area == "dados"
    assert loaded.description == "Descrição de teste"
    assert loaded.notes == "Nota aqui"
    assert loaded.due_date == date(2026, 7, 1)
    assert len(loaded.todos) == 1
    assert loaded.todos[0]["text"] == "Fazer algo"
    assert loaded.todos[0]["due_date"] == "2026-06-15"


def test_due_date_none_roundtrip(tmp_store):
    tmp_store.create(title="Sem prazo", due_date=None)
    loaded = tmp_store.load_by_id("idea-001")
    assert loaded.due_date is None


def test_todo_done_flag_persists(tmp_store):
    idea = tmp_store.create(
        title="Checkbox test",
        todos=[
            {"text": "Pendente", "done": False, "due_date": None},
            {"text": "Feito", "done": True, "due_date": None},
        ],
    )
    loaded = tmp_store.load_by_id("idea-001")
    assert loaded.todos[0]["done"] is False
    assert loaded.todos[1]["done"] is True


def test_load_all_returns_all_ideas(tmp_store):
    tmp_store.create(title="A")
    tmp_store.create(title="B")
    tmp_store.create(title="C")
    all_ideas = tmp_store.load_all()
    assert len(all_ideas) == 3


def test_load_by_id_missing_returns_none(tmp_store):
    result = tmp_store.load_by_id("idea-999")
    assert result is None


def test_save_updates_updated_at(tmp_store):
    idea = tmp_store.create(title="Atualização")
    idea.title = "Atualizado"
    tmp_store.save(idea)
    loaded = tmp_store.load_by_id("idea-001")
    assert loaded.updated_at == date.today()


def test_todo_at_suffix_in_file(tmp_store):
    """Verify @YYYY-MM-DD appears in the raw .md when due_date is set on a todo."""
    tmp_store.create(
        title="Sufixo test",
        todos=[{"text": "Revisar", "done": False, "due_date": "2026-08-01"}],
    )
    raw = (tmp_store.dir / "idea-001.md").read_text(encoding="utf-8")
    assert "@2026-08-01" in raw
