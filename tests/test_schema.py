"""Tests for backlog/schema.py"""

import pytest
from datetime import date
from backlog.schema import Idea, VALID_STATUSES, VALID_PRIORITIES, VALID_AREAS


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


# ── VALID_AREAS ───────────────────────────────────────────────────────────────

def test_valid_areas_contains_all_expected():
    expected = {"produto", "dados & IA", "automação", "gestão",
                "governança", "infraestrutura", "comunicação", "business"}
    assert expected == set(VALID_AREAS)


def test_valid_areas_excludes_removed():
    removed = {"call-recorder", "dados", "IA", "desenvolvimento",
               "planejamento", "negócio", "infra"}
    assert removed.isdisjoint(set(VALID_AREAS)), \
        f"Old areas still present: {removed & set(VALID_AREAS)}"


# ── Idea field defaults ───────────────────────────────────────────────────────

def test_idea_is_bug_default_false():
    idea = Idea(id="idea-001", title="Test")
    assert idea.is_bug is False


def test_idea_agente_autorizado_default_false():
    idea = Idea(id="idea-001", title="Test")
    assert idea.agente_autorizado is False


def test_to_frontmatter_includes_is_bug():
    idea = Idea(id="idea-001", title="Bug idea", is_bug=True)
    fm = idea.to_frontmatter()
    assert "is_bug" in fm
    assert fm["is_bug"] is True


def test_to_frontmatter_agente_autorizado():
    idea = Idea(id="idea-001", title="Auto idea", agente_autorizado=True)
    fm = idea.to_frontmatter()
    assert "agente_autorizado" in fm
    assert fm["agente_autorizado"] is True
