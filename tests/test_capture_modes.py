"""Tests for the call-recorder standalone capture modes (idea-031):
project meeting / retrospective / idea capture -> Inbox note.

process.py lives under call-recorder/ (a hyphenated dir, not importable as a
package), so we add it to sys.path and import the module directly.
"""
import sys
from pathlib import Path

import pytest

CR_DIR = Path(__file__).resolve().parents[1] / "call-recorder"
sys.path.insert(0, str(CR_DIR))

import process  # noqa: E402


@pytest.fixture
def vault(tmp_path, monkeypatch):
    """Point process.VAULT at a temp dir and stub Ollama so no LLM is called."""
    monkeypatch.setattr(process, "VAULT", str(tmp_path))
    monkeypatch.setattr(process, "_ollama_generate",
                        lambda *a, **k: "## Secao\n- conteudo estruturado")
    return tmp_path


@pytest.mark.parametrize("mode,suffix,ntype", [
    ("project",      "project-meeting",  "project-meeting"),
    ("retro",        "retrospective",    "retrospective"),
    ("idea",         "idea-capture",     "idea-capture"),
    ("requirements", "requirements",     "requirements"),
    ("learning",     "learning-capture", "learning-capture"),
])
def test_capture_writes_inbox_note(vault, mode, suffix, ntype):
    t = vault / "t.txt"
    t.write_text("conteudo real da gravacao para estruturar", encoding="utf-8")

    process.cmd_capture(mode, str(t), "2026-06-18", lang="pt", time_str="10-00")

    out = vault / "Inbox" / f"2026-06-18_10-00_{suffix}.md"
    assert out.exists()
    txt = out.read_text(encoding="utf-8")
    assert f"type: {ntype}" in txt
    assert "status: a-triar" in txt
    assert "## Transcricao" in txt
    assert "conteudo real da gravacao" in txt  # original transcript preserved


def test_capture_unknown_mode_exits(vault):
    t = vault / "t.txt"
    t.write_text("algo", encoding="utf-8")
    with pytest.raises(SystemExit):
        process.cmd_capture("bogus", str(t), "2026-06-18", time_str="10-00")


def test_capture_empty_transcript_exits(vault):
    t = vault / "empty.txt"
    t.write_text("   ", encoding="utf-8")
    with pytest.raises(SystemExit):
        process.cmd_capture("idea", str(t), "2026-06-18", time_str="10-00")


def test_classify_transcript_recognizes_capture(vault):
    # filename suffix should map back to the capture mode for sweep reprocessing
    d, t, target, kind = process._classify_transcript("2026-06-18_10-00_idea-capture.txt")
    assert kind == "idea"
    assert target is None
    assert (d, t) == ("2026-06-18", "10-00")
