"""Tests for agent/weekly_brief.py — the Toolkit 2.0 decision loop (idea-066)."""

from datetime import date, timedelta

from agent.weekly_brief import (
    MAX_ITEMS,
    STALE_DAYS,
    build_brief,
    collect_decisions,
    week_id,
)
from backlog.schema import Idea


def _idea(**kw):
    defaults = dict(id="idea-001", title="Alguma ideia", status="backlog")
    defaults.update(kw)
    return Idea(**defaults)


def _days_ago(n: int) -> str:
    return (date.today() - timedelta(days=n)).isoformat()


# ── week id ───────────────────────────────────────────────────────────────────

def test_week_id_format():
    assert week_id(date(2026, 8, 27)) == "2026-W35"
    assert week_id(date(2026, 1, 5)) == "2026-W02"


def test_week_id_pads_single_digit_week():
    """W02, never W2 — otherwise files sort wrong in the vault."""
    assert "W0" in week_id(date(2026, 1, 5))


# ── collection ────────────────────────────────────────────────────────────────

def test_fresh_item_is_not_raised():
    ideas = [_idea(updated_at=_days_ago(1))]
    assert collect_decisions(ideas) == []


def test_closed_items_never_raised():
    """A discarded idea untouched for a year is not a decision."""
    ideas = [
        _idea(id="idea-old", status="descartado", updated_at=_days_ago(365)),
        _idea(id="idea-done", status="concluído", updated_at=_days_ago(365)),
    ]
    assert collect_decisions(ideas) == []


def test_stale_threshold_is_respected():
    just_under = [_idea(updated_at=_days_ago(STALE_DAYS - 1))]
    just_over = [_idea(updated_at=_days_ago(STALE_DAYS))]
    assert collect_decisions(just_under) == []
    assert len(collect_decisions(just_over)) == 1


def test_open_bug_outranks_stale_item():
    ideas = [
        _idea(id="idea-stale", updated_at=_days_ago(20)),
        _idea(id="idea-bug", is_bug=True, updated_at=_days_ago(1)),
    ]
    out = collect_decisions(ideas)
    assert out[0]["id"] == "idea-bug"


def test_overdue_item_is_raised():
    ideas = [_idea(due_date=_days_ago(5), updated_at=_days_ago(1))]
    out = collect_decisions(ideas)
    assert len(out) == 1
    assert "days past" in out[0]["why"]
    assert out[0]["options"] == ("new date", "drop date")


def test_future_due_date_is_not_overdue():
    future = (date.today() + timedelta(days=5)).isoformat()
    ideas = [_idea(due_date=future, updated_at=_days_ago(1))]
    assert collect_decisions(ideas) == []


def test_one_line_per_idea_even_with_several_reasons():
    """An item that is both overdue and stale appears once, at its worst rank."""
    ideas = [_idea(id="idea-x", due_date=_days_ago(10), updated_at=_days_ago(40))]
    out = collect_decisions(ideas)
    assert len(out) == 1
    assert out[0]["id"] == "idea-x"


def test_cap_limits_output_but_no_cap_reveals_all():
    ideas = [_idea(id=f"idea-{n:03d}", updated_at=_days_ago(30)) for n in range(1, 10)]
    assert len(collect_decisions(ideas, limit=MAX_ITEMS)) == MAX_ITEMS
    assert len(collect_decisions(ideas, limit=None)) == 9


# ── rendering ─────────────────────────────────────────────────────────────────

def test_brief_asks_questions_never_checkboxes():
    """The whole point of Toolkit 2.0: no checkbox may reappear here."""
    ideas = [_idea(id="idea-a", updated_at=_days_ago(30))]
    text = build_brief(collect_decisions(ideas), total_active=1)
    assert "- [ ]" not in text
    assert "- [x]" not in text
    assert "**Decision:**" in text


def test_brief_uses_no_star_symbols():
    """Kelvin's standing rule: never signal emphasis with stars."""
    ideas = [_idea(id="idea-a", updated_at=_days_ago(30), priority="alta")]
    text = build_brief(collect_decisions(ideas), total_active=1)
    for star in ("★", "⭐", "\U0001f31f"):
        assert star not in text


def test_brief_letters_items_for_conversational_answer():
    ideas = [_idea(id=f"idea-{n:03d}", updated_at=_days_ago(30)) for n in range(1, 4)]
    text = build_brief(collect_decisions(ideas), total_active=3)
    assert "### A." in text
    assert "### B." in text
    assert "### C." in text


def test_empty_brief_says_so_plainly():
    text = build_brief([], total_active=7)
    assert "Nothing needs a decision" in text
    assert "7 active items" in text


def test_truncation_is_reported_never_silent():
    ideas = [_idea(id=f"idea-{n:03d}", updated_at=_days_ago(30)) for n in range(1, 10)]
    shown = collect_decisions(ideas, limit=MAX_ITEMS)
    dropped = len(collect_decisions(ideas, limit=None)) - len(shown)
    text = build_brief(shown, total_active=9, dropped=dropped)
    assert f"{dropped} further item(s)" in text


def test_brief_frontmatter_has_canonical_type():
    text = build_brief([], total_active=0)
    assert "type: session" in text
    assert f"week: {week_id()}" in text
