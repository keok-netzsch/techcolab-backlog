"""Tests for team_agenda — shared 1:1 agenda generation (agent + Team view)."""

import team_agenda


def _seed_member(base, folder, with_files=True):
    d = base / folder
    d.mkdir(parents=True, exist_ok=True)
    if with_files:
        (d / "OKR.md").write_text("### KR: Ship X\n**Status:** on track\n", encoding="utf-8")
        (d / "1on1.md").write_text("---\n---\n\n## 2026-05-01\n**Topics:**\n- carga\n", encoding="utf-8")
    return d


def test_list_team_folders_filters_stray(tmp_path, monkeypatch):
    monkeypatch.setattr(team_agenda, "TEAM_DIR", tmp_path)
    _seed_member(tmp_path, "Ana-Leite")
    _seed_member(tmp_path, "Pedro-Klein")
    (tmp_path / "1on1").mkdir()      # stray group folder -> excluded
    (tmp_path / "_hidden").mkdir()   # underscore -> excluded
    folders = team_agenda.list_team_folders()
    names = {f for f, _ in folders}
    assert names == {"Ana-Leite", "Pedro-Klein"}
    assert ("Ana-Leite", "Ana Leite") in folders  # display name de-slugged


def test_read_agenda_absent_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(team_agenda, "TEAM_DIR", tmp_path)
    _seed_member(tmp_path, "Ana-Leite")
    assert team_agenda.read_agenda("Ana-Leite") is None


def test_write_then_read_agenda(tmp_path, monkeypatch):
    monkeypatch.setattr(team_agenda, "TEAM_DIR", tmp_path)
    monkeypatch.setattr(team_agenda, "generate_agenda_text",
                        lambda folder, name, timeout=60: "1. Carga de trabalho\n2. OKR Ship X")
    _seed_member(tmp_path, "Ana-Leite")

    out = team_agenda.write_agenda("Ana-Leite", "Ana Leite")
    assert out.name == "next-agenda.md"

    res = team_agenda.read_agenda("Ana-Leite")
    assert res is not None
    gen, body = res
    assert gen != ""                          # generated date in frontmatter
    assert "Carga de trabalho" in body        # body after frontmatter
    assert "type: 1on1-agenda" not in body    # frontmatter stripped from body


def test_generate_all_is_graceful_on_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(team_agenda, "TEAM_DIR", tmp_path)
    _seed_member(tmp_path, "Ana-Leite")
    _seed_member(tmp_path, "Pedro-Klein")

    def _boom(folder, name, timeout=60):
        raise RuntimeError("ollama down")

    monkeypatch.setattr(team_agenda, "write_agenda", _boom)
    result = team_agenda.generate_all()
    assert result["ok"] == []
    assert len(result["failed"]) == 2          # both collected, nothing raised
