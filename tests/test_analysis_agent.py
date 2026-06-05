"""Tests for agent/analysis_agent.py — pure logic, no Ollama calls."""

from unittest.mock import patch

from agent.analysis_agent import (
    _extract_json,
    analyze_all,
    analyze_idea,
    build_report_section,
)
from backlog.schema import Idea


def _make_idea(**kwargs):
    defaults = dict(id="idea-001", title="Test idea", status="em análise")
    defaults.update(kwargs)
    return Idea(**defaults)


# ── _extract_json ─────────────────────────────────────────────────────────────

def test_extract_json_valid():
    raw = '{"decision": "approve", "reasoning": "Good.", "suggested_todos": ["Do X"]}'
    result = _extract_json(raw)
    assert result["decision"] == "approve"


def test_extract_json_wrapped_in_text():
    raw = 'Some text {"decision": "reject", "reasoning": "No.", "suggested_todos": []} more text'
    result = _extract_json(raw)
    assert result["decision"] == "reject"


def test_extract_json_none_on_garbage():
    assert _extract_json("not json at all") is None
    assert _extract_json("") is None
    assert _extract_json(None) is None


# ── analyze_idea ──────────────────────────────────────────────────────────────

def test_analyze_idea_approve():
    idea = _make_idea()
    mock_response = '{"decision": "approve", "reasoning": "High value.", "suggested_todos": ["Build it"]}'
    with patch("agent.analysis_agent._call_ollama", return_value=mock_response):
        result = analyze_idea(idea)
    assert result["decision"] == "approve"
    assert result["raw_ok"] is True
    assert result["idea_id"] == "idea-001"
    assert "Build it" in result["suggested_todos"]


def test_analyze_idea_reject():
    idea = _make_idea(id="idea-002")
    mock_response = '{"decision": "reject", "reasoning": "Low ROI.", "suggested_todos": []}'
    with patch("agent.analysis_agent._call_ollama", return_value=mock_response):
        result = analyze_idea(idea)
    assert result["decision"] == "reject"
    assert result["suggested_todos"] == []


def test_analyze_idea_adjust():
    idea = _make_idea(id="idea-003")
    mock_response = '{"decision": "adjust", "reasoning": "Needs scoping.", "suggested_todos": ["Define scope"]}'
    with patch("agent.analysis_agent._call_ollama", return_value=mock_response):
        result = analyze_idea(idea)
    assert result["decision"] == "adjust"


def test_analyze_idea_ollama_failure_returns_unknown():
    idea = _make_idea()
    with patch("agent.analysis_agent._call_ollama", return_value=None):
        result = analyze_idea(idea)
    assert result["decision"] == "unknown"
    assert result["raw_ok"] is False


def test_analyze_idea_invalid_decision_returns_unknown():
    idea = _make_idea()
    mock_response = '{"decision": "maybe", "reasoning": "Hmm.", "suggested_todos": []}'
    with patch("agent.analysis_agent._call_ollama", return_value=mock_response):
        result = analyze_idea(idea)
    assert result["decision"] == "unknown"


# ── analyze_all ───────────────────────────────────────────────────────────────

def test_analyze_all_only_processes_em_analise():
    ideas = [
        _make_idea(id="idea-001", status="em análise"),
        _make_idea(id="idea-002", status="backlog"),
        _make_idea(id="idea-003", status="concluído"),
    ]
    mock_response = '{"decision": "approve", "reasoning": "OK.", "suggested_todos": []}'
    with patch("agent.analysis_agent._call_ollama", return_value=mock_response):
        results = analyze_all(ideas)
    assert len(results) == 1
    assert results[0]["idea_id"] == "idea-001"


def test_analyze_all_empty_when_no_review_ideas():
    ideas = [_make_idea(id="idea-001", status="backlog")]
    results = analyze_all(ideas)
    assert results == []


# ── build_report_section ──────────────────────────────────────────────────────

def test_build_report_section_empty_on_no_analyses():
    assert build_report_section([]) == ""


def test_build_report_section_contains_idea_id():
    analyses = [{
        "idea_id": "idea-005",
        "title": "My idea",
        "decision": "approve",
        "reasoning": "Strong value.",
        "suggested_todos": ["Step A", "Step B"],
        "raw_ok": True,
    }]
    section = build_report_section(analyses)
    assert "idea-005" in section
    assert "approve" in section.lower() or "Approve" in section
    assert "Step A" in section


def test_build_report_section_reject_has_no_todos_action():
    analyses = [{
        "idea_id": "idea-006",
        "title": "Rejected idea",
        "decision": "reject",
        "reasoning": "Not worth it.",
        "suggested_todos": [],
        "raw_ok": True,
    }]
    section = build_report_section(analyses)
    assert "idea-006" in section
    assert "suggested_todos" not in section


def test_build_report_section_unknown_decision():
    analyses = [{
        "idea_id": "idea-007",
        "title": "Broken idea",
        "decision": "unknown",
        "reasoning": "Ollama did not respond.",
        "suggested_todos": [],
        "raw_ok": False,
    }]
    section = build_report_section(analyses)
    assert "idea-007" in section
