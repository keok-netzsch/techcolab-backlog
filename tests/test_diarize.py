"""Tests for text-based speaker labeling (idea-031, interim — no voice diarization).
Ollama is stubbed so no LLM is called; we assert on prompt construction, file I/O
and edge cases."""
import sys
from pathlib import Path

import pytest

CR_DIR = Path(__file__).resolve().parents[1] / "call-recorder"
sys.path.insert(0, str(CR_DIR))

import process  # noqa: E402


@pytest.fixture
def capture_prompt(monkeypatch):
    """Stub _ollama_generate, recording the prompt it received."""
    seen = {}

    def _fake(prompt, stream=True, model=None):
        seen["prompt"] = prompt
        seen["stream"] = stream
        return "[00.0s] [Kelvin Okuda] oi\n[03.2s] [Ana Leite] tudo bem"

    monkeypatch.setattr(process, "_ollama_generate", _fake)
    return seen


def test_label_speakers_empty_returns_original_without_llm(monkeypatch):
    called = {"n": 0}
    monkeypatch.setattr(process, "_ollama_generate",
                        lambda *a, **k: called.__setitem__("n", called["n"] + 1) or "x")
    assert process.label_speakers("   ") == "   "
    assert process.label_speakers("") == ""
    assert called["n"] == 0            # no LLM call for empty input


def test_label_speakers_returns_llm_output(capture_prompt):
    out = process.label_speakers("[00.0s] oi\n[03.2s] tudo bem",
                                 participants=["Kelvin Okuda", "Ana Leite"])
    assert "[Kelvin Okuda]" in out and "[Ana Leite]" in out
    assert capture_prompt["stream"] is False   # non-streaming for a rewrite pass


def test_label_speakers_puts_participants_in_prompt(capture_prompt):
    process.label_speakers("[00.0s] oi", participants=["Kelvin Okuda", "Ana Leite"])
    assert "Kelvin Okuda" in capture_prompt["prompt"]
    assert "Ana Leite" in capture_prompt["prompt"]


def test_label_speakers_falls_back_to_generic_labels(capture_prompt):
    process.label_speakers("[00.0s] oi")     # no participants
    assert "SPEAKER_1" in capture_prompt["prompt"]


def test_label_speakers_preserves_transcript_in_prompt(capture_prompt):
    process.label_speakers("[00.0s] frase unica de teste")
    assert "frase unica de teste" in capture_prompt["prompt"]


def test_cmd_diarize_writes_diarized_file(tmp_path, monkeypatch):
    monkeypatch.setattr(process, "_ollama_generate",
                        lambda *a, **k: "[00.0s] [Kelvin Okuda] conteudo rotulado")
    src = tmp_path / "2026-07-29_10-00_Ana.txt"
    src.write_text("[00.0s] conteudo\n[02.0s] mais conteudo", encoding="utf-8")

    out_path = process.cmd_diarize(str(src), people="Kelvin Okuda,Ana Leite")

    assert out_path == str(tmp_path / "2026-07-29_10-00_Ana.diarized.txt")
    assert Path(out_path).read_text(encoding="utf-8") == "[00.0s] [Kelvin Okuda] conteudo rotulado"
    assert src.read_text(encoding="utf-8").startswith("[00.0s] conteudo")  # input untouched


def test_cmd_diarize_respects_output_path(tmp_path, monkeypatch):
    monkeypatch.setattr(process, "_ollama_generate", lambda *a, **k: "labeled")
    src = tmp_path / "t.txt"
    src.write_text("[00.0s] x", encoding="utf-8")
    dest = tmp_path / "custom_out.txt"

    out_path = process.cmd_diarize(str(src), output=str(dest))

    assert out_path == str(dest)
    assert dest.read_text(encoding="utf-8") == "labeled"


def test_cmd_diarize_empty_transcript_exits(tmp_path, monkeypatch):
    monkeypatch.setattr(process, "_ollama_generate", lambda *a, **k: "x")
    src = tmp_path / "empty.txt"
    src.write_text("   ", encoding="utf-8")
    with pytest.raises(SystemExit):
        process.cmd_diarize(str(src))
