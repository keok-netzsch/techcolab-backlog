"""Regression tests for backlog.cache._backlog_mtime cache key.

The original key was max(mtime) only, which does NOT change when a file is
moved/deleted out of the backlog dir — leaving a stale 'ghost' card and a
FileNotFoundError on delete. The key now also includes the file count.
"""

import backlog.cache as cache


def _make_idea(p, name, body="x"):
    f = p / f"{name}.md"
    f.write_text(body, encoding="utf-8")
    return f


def test_key_is_tuple_of_count_and_mtime(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "BACKLOG_DIR", tmp_path)
    _make_idea(tmp_path, "idea-001")
    _make_idea(tmp_path, "idea-002")
    key = cache._backlog_mtime()
    assert isinstance(key, tuple)
    assert key[0] == 2  # file count


def test_key_changes_when_file_deleted(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "BACKLOG_DIR", tmp_path)
    f1 = _make_idea(tmp_path, "idea-001")
    _make_idea(tmp_path, "idea-002")
    before = cache._backlog_mtime()

    f1.unlink()  # delete/move out — max(mtime) of survivors is unchanged
    after = cache._backlog_mtime()

    assert before != after, "cache key must change when an idea is deleted"
    assert after[0] == 1


def test_key_changes_when_file_added(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "BACKLOG_DIR", tmp_path)
    _make_idea(tmp_path, "idea-001")
    before = cache._backlog_mtime()

    _make_idea(tmp_path, "idea-002")
    after = cache._backlog_mtime()

    assert before != after
    assert after[0] == 2


def test_key_empty_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "BACKLOG_DIR", tmp_path)
    assert cache._backlog_mtime() == (0, 0.0)
