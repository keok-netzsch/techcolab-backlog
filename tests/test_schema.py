"""Tests for backlog/schema.py"""

import pytest
from datetime import date
from backlog.schema import Idea, VALID_STATUSES, VALID_PRIORITIES


def test_default_status():
    idea = Idea(id="idea-001", title="Test")
    assert idea.status == "backlog"


def test_default_priority():
    idea = Idea(id="idea-001", title="Test")
    assert idea.priority == "média"


def test_due_date_none_by_default():
    idea = Idea(id="idea-001", title="Test")
    assert idea.due_date is None


def test_todos_empty_by_default():
    idea = Idea(id="idea-001", title="Test")
    assert idea.todos == []


def test_to_frontmatter_keys():
    idea = Idea(id="idea-001", title="Minha ideia", area="dados")
    fm = idea.to_frontmatter()
    assert fm["id"] == "idea-001"
    assert fm["titulo"] == "Minha ideia"
    assert fm["area"] == "dados"
    assert "due_date" in fm


def test_to_frontmatter_due_date_serialized():
    idea = Idea(id="idea-001", title="Test", due_date=date(2026, 6, 30))
    fm = idea.to_frontmatter()
    assert fm["due_date"] == "2026-06-30"


def test_to_frontmatter_due_date_empty_when_none():
    idea = Idea(id="idea-001", title="Test", due_date=None)
    fm = idea.to_frontmatter()
    assert fm["due_date"] == ""


def test_valid_statuses_contains_expected():
    expected = {"backlog", "em análise", "concluído", "descartado", "em desenvolvimento"}
    assert expected.issubset(set(VALID_STATUSES))


def test_valid_priorities():
    assert set(VALID_PRIORITIES) == {"alta", "média", "baixa"}
