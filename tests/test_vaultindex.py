"""Tests for vaultindex (idea-097). Everything runs against a synthetic mini-vault in
tmp_path; the writer itself refuses the real index dir under pytest (pattern 10)."""

import os
from pathlib import Path

import pytest

from vaultindex import corpus, db
from vaultindex.cli import EXIT_ERROR, EXIT_LOCKED, EXIT_MISSING, EXIT_OK
from vaultindex.cli import main as cli_main
from vaultindex.search import fts_match_expression, search

ADR = "vault/decisions/2026-08-29-retencao-call-recorder.md"
TEAM = "Team/Ana/1on1.md"
PROJECT = "Projects/Call Recorder.md"
DAILY = "Daily/2026-05-01.md"
DEVOLUTIVA = "Projects/devolutiva-x.md"


def _w(root: Path, rel: str, text: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


@pytest.fixture
def vault(tmp_path) -> Path:
    root = tmp_path / "vault"
    _w(
        root,
        ADR,
        "---\ndate: 2026-08-29\ntype: decision\ntags: [adr, call-recorder]\n---\n"
        "# ADR retenção do call recorder\n\n"
        "## Decisão\nRetenção de 7 dias para áudio transcrito. Ver [[Call Recorder]] e [[Projects/BIA-019]].\n\n"
        "## Consequências\nO transcript fica indefinidamente.\n",
    )
    _w(root, TEAM, "---\ntype: 1on1-log\ndate: 2026-08-20\n---\n# 1:1 Ana\n\nRetenção de talentos e carga de trabalho.\n")
    _w(root, PROJECT, "---\ntype: project\ndate: 2026-06-01\n---\n# Call Recorder\n\nGrava chamadas do Teams em 2 canais.\n")
    _w(root, DAILY, "Nota diária antiga sem frontmatter. Retenção comentada de passagem.\n")
    _w(root, DEVOLUTIVA, "---\ntype: devolutiva\ndate: 2026-07-01\n---\nRetenção e feedback.\n")
    _w(root, "Templates/modelo.md", "---\ntype: template\n---\nretenção retenção retenção\n")
    _w(root, "vault/backup-notas-2026-09-02/velho.md", "retenção duplicada de backup\n")
    return root


@pytest.fixture
def index_dir(tmp_path) -> Path:
    return tmp_path / "index"


# ── build ─────────────────────────────────────────────────────────────────────


def test_build_indexes_notes_and_skips_excluded_dirs(vault, index_dir):
    rep = db.build(vault, index_dir)
    assert rep.notes == 5  # template and backup folders never enter
    assert rep.added == 5 and rep.updated == 0 and rep.removed == 0
    assert rep.no_frontmatter == 1
    assert rep.sensitive_notes == 2  # Team/ by folder, devolutiva by type
    assert rep.chunks >= 5
    assert (index_dir / db.DB_NAME).exists()
    assert not (index_dir / db.LOCK_NAME).exists()  # lock released


def test_incremental_build_skips_unchanged(vault, index_dir):
    db.build(vault, index_dir)
    rep = db.build(vault, index_dir)
    assert rep.unchanged == 5 and rep.added == 0 and rep.updated == 0


def test_incremental_build_sees_modified_and_deleted(vault, index_dir):
    db.build(vault, index_dir)
    (vault / PROJECT).write_text("---\ntype: project\n---\n# Call Recorder\n\nAgora com autocapture e fila.\n", encoding="utf-8")
    (vault / DAILY).unlink()
    rep = db.build(vault, index_dir)
    assert rep.updated == 1 and rep.removed == 1 and rep.unchanged == 3
    con = db.connect_ro(index_dir)
    paths = {r["rel_path"] for r in con.execute("SELECT rel_path FROM notes")}
    con.close()
    assert DAILY not in paths and PROJECT in paths
    # the FTS side followed: the old text is gone, the new one is findable
    assert not search("canais", index_dir=index_dir)["results"]
    assert search("autocapture", index_dir=index_dir)["results"][0]["path"] == PROJECT


def test_full_build_recreates_from_scratch(vault, index_dir):
    db.build(vault, index_dir)
    rep = db.build(vault, index_dir, full=True)
    assert rep.full and rep.added == 5 and rep.unchanged == 0


def test_frontmatterless_note_metadata(vault, index_dir):
    db.build(vault, index_dir)
    con = db.connect_ro(index_dir)
    row = con.execute("SELECT * FROM notes WHERE rel_path = ?", (DAILY,)).fetchone()
    con.close()
    assert row["has_frontmatter"] == 0
    assert row["title"] == "2026-05-01"
    assert row["date"] == "2026-05-01" and row["date_source"] == "filename"
    assert row["type"] is None


def test_links_resolved_by_stem_or_path(vault, index_dir):
    db.build(vault, index_dir)
    con = db.connect_ro(index_dir)
    rows = con.execute(
        "SELECT l.to_title, n.rel_path AS target FROM links l LEFT JOIN notes n ON n.id = l.to_note "
        "JOIN notes f ON f.id = l.from_note WHERE f.rel_path = ? ORDER BY l.id",
        (ADR,),
    ).fetchall()
    con.close()
    resolved = {r["to_title"]: r["target"] for r in rows}
    assert resolved["Call Recorder"] == PROJECT
    assert resolved["Projects/BIA-019"] is None  # file does not exist: stays unresolved, not invented


def test_links_resolve_through_aliases_and_filename_still_wins(tmp_path, index_dir):
    root = tmp_path / "aliasvault"
    _w(
        root,
        "Stakeholders/Stefan-Lautenschlager/Overview.md",
        "---\ntype: capture\ndate: 2026-09-04\naliases: [Stefan Lautenschlager, Chefe]\n---\n# Stefan\n",
    )
    _w(root, "Notes/Chefe.md", "---\ntype: note\ndate: 2026-09-04\n---\n# Chefe\n\nOutra nota.\n")
    _w(
        root,
        "Notes/menciona.md",
        "---\ntype: note\ndate: 2026-09-04\n---\nFalei com [[Stefan Lautenschlager]] sobre o [[Chefe]].\n",
    )
    db.build(root, index_dir)
    con = db.connect_ro(index_dir)
    rows = con.execute(
        "SELECT l.to_title, n.rel_path AS target FROM links l LEFT JOIN notes n ON n.id = l.to_note "
        "JOIN notes f ON f.id = l.from_note WHERE f.rel_path = ? ORDER BY l.id",
        ("Notes/menciona.md",),
    ).fetchall()
    con.close()
    resolved = {r["to_title"]: r["target"] for r in rows}
    assert resolved["Stefan Lautenschlager"] == "Stakeholders/Stefan-Lautenschlager/Overview.md"
    assert resolved["Chefe"] == "Notes/Chefe.md"  # a real file outranks someone else's alias


# ── check (the independent reader) ───────────────────────────────────────────


def test_check_passes_after_build_and_fails_after_edit(vault, index_dir):
    db.build(vault, index_dir)
    assert db.check(vault, index_dir).ok
    with open(vault / PROJECT, "a", encoding="utf-8") as fh:
        fh.write("\nlinha nova\n")
    rep = db.check(vault, index_dir)
    assert not rep.ok and rep.changed == [PROJECT]
    assert cli_main(["--root", str(vault), "--index-dir", str(index_dir), "check"]) == EXIT_ERROR


# ── search ────────────────────────────────────────────────────────────────────


def test_search_excludes_sensitive_by_default_and_counts_it(vault, index_dir):
    db.build(vault, index_dir)
    out = search("retenção", index_dir=index_dir)
    paths = [r["path"] for r in out["results"]]
    assert ADR in paths and DAILY in paths
    assert TEAM not in paths and DEVOLUTIVA not in paths
    assert out["excluded_sensitive_hits"] == 2
    assert out["mode"] == "fts-only"
    assert out["index_age_seconds"] is not None


def test_search_opt_in_includes_sensitive(vault, index_dir):
    db.build(vault, index_dir)
    out = search("retenção", include_sensitive=True, index_dir=index_dir)
    paths = {r["path"] for r in out["results"]}
    assert {TEAM, DEVOLUTIVA} <= paths
    assert out["excluded_sensitive_hits"] == 0
    flagged = {r["path"] for r in out["results"] if r["sensitive"]}
    assert flagged == {TEAM, DEVOLUTIVA}


def test_search_is_accent_insensitive(vault, index_dir):
    db.build(vault, index_dir)
    assert search("retencao", index_dir=index_dir)["results"][0]["path"] == ADR


def test_search_ranks_decision_first_and_explains_why(vault, index_dir):
    db.build(vault, index_dir)
    # "retenção" alone is in four notes; "transcript" pins the ADR. bm25 favours short
    # notes whose title carries the query, so a project called "Call Recorder" beats the
    # ADR on "retenção call recorder" and that is the right answer for that query.
    out = search("retenção do transcript", index_dir=index_dir)
    top = out["results"][0]
    assert top["path"] == ADR
    assert top["why"] == ["fts"]
    assert top["authority"] == pytest.approx(1.08)
    assert top["snippets"] and "[" in top["snippets"][0]["text"]


def test_search_filters_by_type_and_folder(vault, index_dir):
    db.build(vault, index_dir)
    out = search("retenção", types=["decision"], index_dir=index_dir)
    assert [r["path"] for r in out["results"]] == [ADR]
    assert out["excluded_by_filter"] >= 1
    out = search("retenção", folder="Daily/", index_dir=index_dir)
    assert [r["path"] for r in out["results"]] == [DAILY]


def test_search_refresh_picks_up_new_note(vault, index_dir):
    db.build(vault, index_dir)
    _w(vault, "Inbox/nova.md", "---\ntype: capture\n---\nAssunto inédito: palavrachave.\n")
    assert not search("palavrachave", index_dir=index_dir)["results"]
    out = search("palavrachave", refresh=True, root=vault, index_dir=index_dir)
    assert out["refreshed"]["added"] == 1
    assert out["results"][0]["path"] == "Inbox/nova.md"


def test_search_without_searchable_terms(vault, index_dir):
    db.build(vault, index_dir)
    out = search("& !", index_dir=index_dir)
    assert out["results"] == [] and "note" in out


# ── errors look like errors ──────────────────────────────────────────────────


def test_missing_index_is_an_error_not_an_empty_answer(tmp_path):
    with pytest.raises(db.IndexMissing):
        db.connect_ro(tmp_path / "nope")
    rc = cli_main(["--index-dir", str(tmp_path / "nope"), "search", "--no-refresh", "x"])
    assert rc == EXIT_MISSING


def test_lock_held_by_live_pid_blocks_build(vault, index_dir):
    index_dir.mkdir()
    (index_dir / db.LOCK_NAME).write_text(str(os.getpid()))
    with pytest.raises(db.IndexLocked):
        db.build(vault, index_dir)
    assert cli_main(["--root", str(vault), "--index-dir", str(index_dir), "build"]) == EXIT_LOCKED


def test_orphan_lock_is_reclaimed(vault, index_dir):
    index_dir.mkdir()
    (index_dir / db.LOCK_NAME).write_text("999999999")  # no such process
    rep = db.build(vault, index_dir)
    assert rep.notes == 5 and not (index_dir / db.LOCK_NAME).exists()


def test_writer_refuses_the_real_index_under_pytest():
    with pytest.raises(RuntimeError):
        db.IndexWriter(index_dir=db.default_index_dir())


def test_cli_build_and_search_roundtrip(vault, index_dir, capsys):
    assert cli_main(["--root", str(vault), "--index-dir", str(index_dir), "build"]) == EXIT_OK
    assert cli_main(["--index-dir", str(index_dir), "search", "--no-refresh", "transcript"]) == EXIT_OK
    out = capsys.readouterr().out
    assert "[fts-only]" in out and ADR in out


# ── corpus internals ─────────────────────────────────────────────────────────


def test_fts_match_expression_quotes_and_prefixes():
    assert fts_match_expression("retenção call") == '"retenção"* OR "call"'
    assert fts_match_expression("and or not") == '"and" OR "not"'  # 2-letter tokens drop when longer ones exist
    assert fts_match_expression("do de") == '"do" OR "de"'  # alone they stay
    assert fts_match_expression("a") is None
    assert fts_match_expression('say "hi"') == '"say"'


def test_chunk_body_respects_cap_and_keeps_headings():
    long_para = " ".join(["palavra"] * 200)  # ~1600 chars, one paragraph
    body = "Intro curta.\n\n## Seção A\n" + long_para + "\n\n## Seção B\nCurta.\n\n### Sub B1\n" + long_para
    chunks = corpus.chunk_body(body, chunk_max=900)
    assert all(len(c.text) <= 900 for c in chunks)
    assert chunks[0].heading is None and chunks[0].text.startswith("Intro")
    assert any(c.heading == "Seção A" for c in chunks)
    assert any(c.heading == "Sub B1" for c in chunks)
    for c in chunks:  # offsets point back into the body
        assert body[c.char_start : c.char_end] == c.text


def test_chunk_body_merges_tiny_sections():
    body = "## A\nx\n\n## B\ny\n\n## C\nz\n"
    chunks = corpus.chunk_body(body, chunk_max=900)
    assert len(chunks) == 1 and "## C" in chunks[0].text


def test_split_frontmatter_tolerates_broken_yaml():
    fm, body, had = corpus.split_frontmatter("---\ntype: [unclosed\n---\ncorpo\n")
    assert had is True and fm == {} and body.strip() == "corpo"
    fm, body, had = corpus.split_frontmatter("﻿---\ntype: x\n---\ncorpo")
    assert had is True and fm == {"type": "x"}
    fm, body, had = corpus.split_frontmatter("sem bloco")
    assert had is False and fm == {} and body == "sem bloco"


def test_sensitivity_rules():
    assert corpus.parse_note  # smoke: module wired
    assert "Team/" in corpus.SENSITIVE_FOLDERS and "1on1-session" in corpus.SENSITIVE_TYPES


def test_authority_multiplier_is_bounded_and_typed():
    from datetime import date

    from vaultindex.search import authority

    today = date(2026, 9, 3)

    def note(**kw):
        base = {"type": None, "date": "2026-09-01", "rel_path": "Inbox/x.md", "pinned": 0}
        base.update(kw)
        return base

    assert authority(note(), today) == 1.0
    assert authority(note(type="decision"), today) == pytest.approx(1.08)
    assert authority(note(type="session", date="2026-09-01"), today) == pytest.approx(0.95)
    assert authority(note(type="session", date="2026-01-01"), today) == pytest.approx(0.855)
    assert authority(note(type="daily", date=None), today) == pytest.approx(0.95)  # unknown age: no decay
    assert authority(note(rel_path="Archive/_archived_x.md"), today) == pytest.approx(0.95)
    assert authority(note(rel_path="App/Personal toolkit/backlog items/_arquivo/idea-006.md"), today) == pytest.approx(0.95)
    assert authority(note(type="decision", pinned=1), today) == pytest.approx(1.188)
    assert authority(note(type="session", date="2026-01-01", rel_path="Archive/x.md"), today) == pytest.approx(0.81225)
    assert authority(note(type="session", date="2026-01-01", rel_path="Archive/x.md", pinned=0), today) >= 0.8
