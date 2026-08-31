"""Tests for components/prefs.py — on-disk UI preference persistence."""

import components.prefs as prefs


def test_get_returns_default_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(prefs, "_PREFS_FILE", tmp_path / ".ui_prefs.json")
    assert prefs.get_pref("backlog_view", "List") == "List"


def test_set_then_get_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(prefs, "_PREFS_FILE", tmp_path / ".ui_prefs.json")
    prefs.set_pref("backlog_view", "Kanban")
    assert prefs.get_pref("backlog_view", "List") == "Kanban"


def test_set_preserves_other_keys(tmp_path, monkeypatch):
    monkeypatch.setattr(prefs, "_PREFS_FILE", tmp_path / ".ui_prefs.json")
    prefs.set_pref("a", 1)
    prefs.set_pref("b", 2)
    assert prefs.get_pref("a") == 1
    assert prefs.get_pref("b") == 2


def test_corrupt_file_falls_back_to_default(tmp_path, monkeypatch):
    f = tmp_path / ".ui_prefs.json"
    f.write_text("{ not valid json", encoding="utf-8")
    monkeypatch.setattr(prefs, "_PREFS_FILE", f)
    assert prefs.get_pref("backlog_view", "List") == "List"
    # set still recovers (overwrites the corrupt file)
    prefs.set_pref("backlog_view", "Kanban")
    assert prefs.get_pref("backlog_view", "List") == "Kanban"
