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


def test_build_report_bug_badge_in_proposed_actions():
    bug = _make_idea(id="idea-bug", is_bug=True, status="backlog", impacto="alta", priority="alta")
    data = analyze([bug])
    report = build_report(_minimal_tests(), data)
    # The bug badge should appear in Proposed actions next to the item
    assert "🐛" in report
