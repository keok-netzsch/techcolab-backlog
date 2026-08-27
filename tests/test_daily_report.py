"""Tests for agent/daily_report.py — analyze() and build_report()"""

from agent.daily_report import analyze, build_report
from backlog.schema import Idea


def _make_idea(**kwargs):
    defaults = dict(id="idea-001", title="Test idea", status="backlog")
    defaults.update(kwargs)
    return Idea(**defaults)


# ── analyze() ────────────────────────────────────────────────────────────────

def test_analyze_open_bugs_empty_when_no_bugs():
    ideas = [_make_idea(is_bug=False), _make_idea(id="idea-002", is_bug=False)]
    result = analyze(ideas)
    assert result["open_bugs"] == []


def test_analyze_open_bugs_counts_active_bugs():
    bug = _make_idea(id="idea-bug", is_bug=True, status="em desenvolvimento")
    normal = _make_idea(id="idea-normal", is_bug=False)
    result = analyze([bug, normal])
    assert len(result["open_bugs"]) == 1
    assert result["open_bugs"][0].id == "idea-bug"


def test_analyze_closed_bugs_not_in_open_bugs():
    done_bug = _make_idea(id="idea-done", is_bug=True, status="concluído")
    result = analyze([done_bug])
    assert result["open_bugs"] == []


def test_analyze_open_bugs_key_present():
    result = analyze([_make_idea()])
    assert "open_bugs" in result


# ── build_report() ────────────────────────────────────────────────────────────

def _minimal_tests():
    return {"passed": 5, "failed": 0, "errors": 0, "summary": "5 passed", "ok": True}


def test_build_report_shows_no_bugs_check():
    data = analyze([_make_idea(is_bug=False)])
    report = build_report(_minimal_tests(), data)
    assert "Open bugs" in report
    assert "none" in report


def test_build_report_shows_bug_id_in_health_check():
    bug = _make_idea(id="idea-007", is_bug=True, status="backlog")
    data = analyze([bug])
    report = build_report(_minimal_tests(), data)
    assert "Open bugs" in report
    assert "idea-007" in report
    assert "🐛" in report


def test_build_report_bug_appears_in_alerts():
    bug = _make_idea(id="idea-bug", is_bug=True, status="backlog")
    data = analyze([bug])
    report = build_report(_minimal_tests(), data)
    # The alerts section should mention the bug
    assert "Alerts" in report
    assert "idea-bug" in report


def test_build_report_bug_badge_shown():
    bug = _make_idea(id="idea-bug", is_bug=True, status="backlog", impacto="alta", priority="alta")
    data = analyze([bug])
    report = build_report(_minimal_tests(), data)
    # The bug badge marks the item in the health check / alerts
    assert "🐛" in report


def test_build_report_has_no_action_checkboxes():
    """Toolkit 2.0 (idea-066): the daily report states, it never asks.

    No checkbox may reach this report — the approval loop moved to the
    Weekly Brief, answered in conversation.
    """
    ideas = [
        _make_idea(id="idea-a", status="backlog", impacto="alta", priority="alta"),
        _make_idea(id="idea-b", status="análise - aprovado", impacto="alta", priority="alta"),
    ]
    report = build_report(_minimal_tests(), analyze(ideas))
    assert "- [ ]" not in report
    assert "- [x]" not in report
    assert "Proposed actions" not in report


def test_analysis_section_has_no_checkboxes():
    """Toolkit 2.0 (idea-066): the Phase 2 section suggests, it does not queue.

    This was the second source of the dead approval loop — daily_report's own
    "Proposed actions" was removed first, while analysis_agent kept injecting
    "- [ ] Apply: move idea-NNN -> status" lines into the same report.
    """
    from agent.analysis_agent import build_report_section
    analyses = [{
        "idea_id": "idea-011", "title": "T", "decision": "approve",
        "reasoning": "R", "suggested_todos": ["passo a", "passo b"],
        "worker_error": None,
    }]
    section = build_report_section(analyses)
    assert "- [ ]" not in section
    assert "- [x]" not in section
    assert "Check the boxes" not in section
    # the suggestion itself must survive — we removed the checkbox, not the signal
    assert "passo a" in section
    assert "análise - aprovado" in section
