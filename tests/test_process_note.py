"""Tests for process.cmd_note — the 'Outro' loose-note path (Inbox/ triage)."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "call-recorder"))

import process  # noqa: E402


def test_cmd_note_writes_inbox_note(tmp_path, monkeypatch):
    monkeypatch.setattr(process, "VAULT", str(tmp_path))
    monkeypatch.setattr(process, "_ollama_generate", lambda *a, **k: "- ponto 1\n- ponto 2")

    t = tmp_path / "t.txt"
    t.write_text("conteudo da conversa avulsa", encoding="utf-8")

    process.cmd_note(str(t), "2026-06-03", lang="en", time_str="09-15")

    out = tmp_path / "Inbox" / "2026-06-03_09-15_nota-avulsa.md"
    assert out.exists()
    txt = out.read_text(encoding="utf-8")
    assert "type: nota-avulsa" in txt
    assert "status: a-triar" in txt
    assert "lang: en" in txt
    assert "time: 09:15" in txt          # HH-MM -> HH:MM in frontmatter
    assert "- ponto 1" in txt             # Ollama summary
    assert "conteudo da conversa avulsa" in txt  # raw transcript preserved


def test_cmd_note_empty_transcript_exits(tmp_path, monkeypatch):
    monkeypatch.setattr(process, "VAULT", str(tmp_path))
    monkeypatch.setattr(process, "_ollama_generate", lambda *a, **k: "x")
    t = tmp_path / "empty.txt"
    t.write_text("   ", encoding="utf-8")
    with pytest.raises(SystemExit):
        process.cmd_note(str(t), "2026-06-03", lang="pt")
