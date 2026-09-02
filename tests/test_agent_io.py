"""
Regression tests for the cp1252 stdout bug that silently killed Phase 2.

Background: run_agent.bat redirects stdout to logs/agent-last.log. A redirected
stdout on Windows defaults to the ANSI code page (cp1252), so a print carrying
U+2192 / U+2705 / U+1F504 raised UnicodeEncodeError *inside* the analysis
worker. The surrounding `except Exception` then threw the finished Ollama
analysis away and logged a generic "Worker error" -- Phase 2 was a no-op and
nobody noticed.

These tests pin both halves of the fix:
  1. the print path survives a cp1252 stdout;
  2. when a worker really does die, it is reported loudly.
"""

import io
import sys
from unittest.mock import patch

import pytest

from agent.agent_io import force_utf8_stdio, safe_print
from agent.analysis_agent import analyze_all, build_report_section
from backlog.schema import Idea

# The exact characters that broke the 2026-08-24 run.
OFFENDERS = "-> → ✅ ❌ 🔄"


def _cp1252_stdout() -> io.TextIOWrapper:
    """A stdout that behaves like a Task Scheduler-redirected log file."""
    return io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict", newline="")


def _make_idea(**kwargs) -> Idea:
    defaults = dict(id="idea-011", title="Automatizar relatorio", status="em análise")
    defaults.update(kwargs)
    return Idea(**defaults)


# -- the raw failure mode ------------------------------------------------------

def test_cp1252_stdout_really_does_reject_the_arrow():
    """Guard the guard: if this stops raising, the tests below prove nothing."""
    stream = _cp1252_stdout()
    with pytest.raises(UnicodeEncodeError):
        stream.write(OFFENDERS)
        stream.flush()


# -- fix 1: force_utf8_stdio ---------------------------------------------------

def test_force_utf8_stdio_switches_a_cp1252_stream(monkeypatch):
    stream = _cp1252_stdout()
    monkeypatch.setattr(sys, "stdout", stream)
    force_utf8_stdio()
    assert sys.stdout.encoding.lower().replace("-", "") == "utf8"
    print(OFFENDERS)  # would have raised before the reconfigure
    sys.stdout.flush()
    assert "→".encode() in stream.buffer.getvalue()


def test_force_utf8_stdio_is_safe_on_a_stream_it_cannot_touch(monkeypatch):
    class Dumb:
        encoding = "cp1252"

        def write(self, _):
            return 0

    monkeypatch.setattr(sys, "stdout", Dumb())
    force_utf8_stdio()  # no reconfigure attribute -- must not raise


# -- fix 2: safe_print never raises -------------------------------------------

def test_safe_print_does_not_raise_on_cp1252(monkeypatch):
    stream = _cp1252_stdout()
    monkeypatch.setattr(sys, "stdout", stream)
    safe_print(f"[analysis_agent]   {OFFENDERS} approve (idea-011)")
    sys.stdout.flush()
    written = stream.buffer.getvalue().decode("cp1252")
    assert "approve (idea-011)" in written  # the message still lands in the log


# -- fix 3: the real Phase 2 path under a cp1252 stdout ------------------------

def test_analyze_all_survives_cp1252_stdout_and_keeps_the_analysis(monkeypatch):
    """
    The actual 2026-08-24 regression: with stdout forced to cp1252, running the
    analysis must neither raise nor lose the decision the model returned.
    """
    monkeypatch.setattr(sys, "stdout", _cp1252_stdout())

    ideas = [_make_idea(id="idea-011"), _make_idea(id="idea-048"), _make_idea(id="idea-056")]
    response = '{"decision": "approve", "reasoning": "Vale.", "suggested_todos": ["Do X"]}'

    with patch("agent.analysis_agent._call_llm", return_value=response):
        results = analyze_all(ideas, max_workers=2)

    assert len(results) == 3
    assert [r["decision"] for r in results] == ["approve"] * 3
    assert all(r["raw_ok"] for r in results)
    assert not any(r.get("worker_error") for r in results)


# -- fix 4: a worker that really dies is loud ---------------------------------

def test_dead_worker_is_recorded_as_worker_error():
    ideas = [_make_idea(id="idea-011")]
    with patch("agent.analysis_agent.analyze_idea", side_effect=RuntimeError("boom")):
        results = analyze_all(ideas, max_workers=1)

    assert len(results) == 1
    assert results[0]["decision"] == "unknown"
    assert "RuntimeError: boom" in results[0]["worker_error"]


def test_report_section_flags_a_dead_worker():
    analyses = [
        {"idea_id": "idea-011", "title": "A", "decision": "approve",
         "reasoning": "ok", "suggested_todos": [], "raw_ok": True},
        {"idea_id": "idea-048", "title": "B", "decision": "unknown",
         "reasoning": "Worker error: RuntimeError: boom", "suggested_todos": [],
         "raw_ok": False, "worker_error": "RuntimeError: boom"},
    ]
    section = build_report_section(analyses)
    assert "Phase 2 DEGRADED" in section
    assert "1 of 2" in section
    assert "`idea-048`" in section
    assert "RuntimeError: boom" in section


def test_report_section_has_no_failure_banner_when_all_workers_survive():
    analyses = [
        {"idea_id": "idea-011", "title": "A", "decision": "approve",
         "reasoning": "ok", "suggested_todos": [], "raw_ok": True},
    ]
    assert "DEGRADED" not in build_report_section(analyses)
