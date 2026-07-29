"""Tests for File Processing (idea-031): transcribe an existing audio/video file
(e.g. an MP4 recording) instead of capturing from the mic. Whisper itself is
mocked so these run in CI without the model / ffmpeg."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "call-recorder"))

import record  # noqa: E402


def test_is_supported_media_accepts_audio_and_video():
    for ok in ("meeting.mp4", "call.MOV", "note.wav", "clip.m4a", "x.webm"):
        assert record.is_supported_media(ok), ok


def test_is_supported_media_rejects_other_files():
    for bad in ("notes.txt", "deck.pptx", "archive.zip", "noext"):
        assert not record.is_supported_media(bad), bad


def test_transcribe_file_missing_input_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        record.transcribe_file(str(tmp_path / "nope.mp4"))


def test_transcribe_file_unsupported_type_raises(tmp_path):
    f = tmp_path / "notes.txt"
    f.write_text("not media", encoding="utf-8")
    with pytest.raises(ValueError):
        record.transcribe_file(str(f))


def test_transcribe_file_writes_transcript_and_lang_sidecar(tmp_path, monkeypatch):
    monkeypatch.setattr(record, "transcribe",
                        lambda path, language=None: ("[00.0s] hello world", "en"))
    src = tmp_path / "meeting.mp4"
    src.write_bytes(b"fake video bytes")
    out = tmp_path / "out.txt"

    out_path, detected = record.transcribe_file(str(src), str(out), language="auto")

    assert out_path == str(out)
    assert detected == "en"
    assert out.read_text(encoding="utf-8") == "[00.0s] hello world"
    assert (tmp_path / "out.txt.lang").read_text(encoding="utf-8") == "en"


def test_transcribe_file_derives_output_name_from_input_stem(tmp_path, monkeypatch):
    captured = {}

    def _fake_transcribe(path, language=None):
        captured["path"] = path
        captured["language"] = language
        return ("texto", "pt")

    monkeypatch.setattr(record, "transcribe", _fake_transcribe)
    src = tmp_path / "reuniao_diretoria.mp4"
    src.write_bytes(b"data")

    out_path, detected = record.transcribe_file(str(src))  # no output_path

    assert captured["path"] == str(src)          # file passed straight to Whisper
    assert detected == "pt"
    assert "reuniao_diretoria" in os.path.basename(out_path)
    assert out_path.endswith(".txt")
    assert os.path.isfile(out_path)
    assert os.path.isfile(out_path + ".lang")


def test_transcribe_file_passes_none_language_when_auto(tmp_path, monkeypatch):
    captured = {}
    monkeypatch.setattr(record, "transcribe",
                        lambda path, language=None: captured.update(language=language) or ("t", "pt"))
    src = tmp_path / "c.wav"
    src.write_bytes(b"d")

    record.transcribe_file(str(src), str(tmp_path / "o.txt"), language="auto")

    assert captured["language"] is None          # "auto" -> None (Whisper detects)
