"""Tests for vaultindex F2/F3 (idea-097): vector stream, fusion, neighbours, bench, briefing,
lint, as_of. A deterministic bag-of-words embedder stands in for the ONNX model, so no
download and no model file is needed to test the plumbing."""

import re
import zlib
from datetime import date
from pathlib import Path

import numpy as np
import pytest

from vaultindex import db
from vaultindex.bench import run_bench
from vaultindex.briefing import briefing, extract_sections
from vaultindex.cli import EXIT_OK, memory_corpus
from vaultindex.cli import main as cli_main
from vaultindex.embed import chunk_text_for_embedding, embed_missing, load_vectors
from vaultindex.lint import lint, write_report
from vaultindex.search import search

ADR = "vault/decisions/2026-08-29-retencao-call-recorder.md"
TEAM = "Team/Ana/1on1.md"
PROJECT = "Projects/Call Recorder.md"
DAILY = "Daily/2026-05-01.md"
DEVOLUTIVA = "Projects/devolutiva-x.md"


class FakeEmbedder:
    """Hashed bag of words, L2-normalised. Shares nothing with the real model except the interface."""

    name = "fake"
    dim = 64

    def encode(self, texts, batch_size=32):
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, t in enumerate(texts):
            for tok in re.findall(r"\w+", t.lower()):
                out[i, zlib.crc32(tok.encode("utf-8")) % self.dim] += 1.0
        out /= np.maximum(np.linalg.norm(out, axis=1, keepdims=True), 1e-9)
        return out


FAKE = FakeEmbedder()


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
    return root


@pytest.fixture
def index_dir(tmp_path) -> Path:
    return tmp_path / "index"


def _embedded(vault, index_dir):
    rep = db.build(vault, index_dir, embed=True, model="fake", embedder=FAKE)
    return rep


# ── embeddings ────────────────────────────────────────────────────────────────


def test_embed_missing_fills_then_is_idempotent(vault, index_dir):
    db.build(vault, index_dir)
    with db.IndexWriter(index_dir) as w:
        n_chunks = w.con.execute("SELECT count(*) FROM chunks").fetchone()[0]
        assert embed_missing(w.con, "fake", embedder=FAKE) == n_chunks
        assert embed_missing(w.con, "fake", embedder=FAKE) == 0
        assert db.meta_value(w.con, "embedding_model") == "fake"
        ids, mat = load_vectors(w.con, "fake")
        assert len(ids) == n_chunks and mat.shape == (n_chunks, FAKE.dim)
        assert np.allclose(np.linalg.norm(mat, axis=1), 1.0, atol=1e-4)
    st = db.stats(index_dir)
    assert st["embedding_model"] == "fake" and st["embeddings_by_model"] == {"fake": n_chunks}
    assert st["embeddings_stale_chunks"] == 0


def test_build_with_embed_flag(vault, index_dir):
    rep = _embedded(vault, index_dir)
    assert rep.embedding_model == "fake" and rep.embedded == rep.chunks and rep.embeddings_stale_chunks == 0
    # a new note leaves exactly its chunks without a vector until the next embed
    _w(vault, "Inbox/nova.md", "---\ntype: capture\n---\nAssunto novo, palavraunica.\n")
    rep2 = db.build(vault, index_dir)
    assert rep2.embeddings_stale_chunks == 1
    rep3 = db.build(vault, index_dir, embed=True, embedder=FAKE)  # model defaults to the active one
    assert rep3.embedding_model == "fake" and rep3.embedded == 1 and rep3.embeddings_stale_chunks == 0


def test_two_models_coexist_and_reembed_after_note_change(vault, index_dir):
    _embedded(vault, index_dir)
    with db.IndexWriter(index_dir) as w:
        embed_missing(w.con, "fake-b", embedder=FAKE, activate=False)
    st = db.stats(index_dir)
    assert set(st["embeddings_by_model"]) == {"fake", "fake-b"} and st["embedding_model"] == "fake"
    (vault / PROJECT).write_text("---\ntype: project\n---\n# Call Recorder\n\nTexto trocado.\n", encoding="utf-8")
    rep = db.build(vault, index_dir)
    assert rep.embeddings_stale_chunks == 1  # the rewritten note lost its vectors with its chunks


def test_chunk_text_for_embedding_carries_title_and_heading():
    assert chunk_text_for_embedding("T", "H", "x") == "T\nH\nx"
    assert chunk_text_for_embedding("T", None, "x") == "T\nx"


# ── search: streams, fusion, neighbours ──────────────────────────────────────


def test_hybrid_mode_and_why(vault, index_dir):
    _embedded(vault, index_dir)
    out = search("retenção do transcript", index_dir=index_dir, embedder=FAKE)
    assert out["mode"] == "hybrid" and out["model"] == "fake"
    assert out["candidates"]["fts"] > 0 and out["candidates"]["vec"] > 0
    top = out["results"][0]
    assert top["path"] == ADR
    assert "fts" in top["why"] and "vec" in top["why"]
    assert "vec_sim" in top and 0 < top["vec_sim"] <= 1.0


def test_vec_only_stream(vault, index_dir):
    _embedded(vault, index_dir)
    out = search("transcript", index_dir=index_dir, embedder=FAKE, streams=("vec",), neighbours=False)
    assert out["mode"] == "vec-only" and "fts" not in out["candidates"]
    assert out["results"][0]["path"] == ADR
    assert out["results"][0]["snippets"][0]["from"] == "vec"
    assert out["results"][0]["why"] == ["vec"]


def test_without_active_model_is_fts_only_with_note(vault, index_dir):
    db.build(vault, index_dir)
    out = search("retenção", index_dir=index_dir)
    assert out["mode"] == "fts-only" and out["model"] is None
    assert "embed" in out["note"]
    assert out["results"]


def test_unknown_model_degrades_to_fts_and_says_so(vault, index_dir):
    _embedded(vault, index_dir)
    out = search("retenção", index_dir=index_dir, model="nao-existe")
    assert out["mode"] == "fts-only"
    assert "desligado" in out["note"]
    assert out["results"][0]["path"] == ADR


def test_neighbours_add_link_stream(vault, index_dir):
    _embedded(vault, index_dir)
    # the ADR links to [[Call Recorder]] and both are retrieved; whichever ranks lower of the
    # two is a neighbour of the one above it and gets the lift (bm25 puts the short project
    # note first for this query, so the ADR is the one lifted here).
    out = search("retenção call recorder", index_dir=index_dir, embedder=FAKE)
    by_path = {r["path"]: r for r in out["results"]}
    lifted = {p for p in (ADR, PROJECT) if "link" in by_path[p]["why"]}
    assert len(lifted) == 1 and out["candidates"]["link"] >= 1
    # the lift is applied on the fused order and may swap a near-tie, so only the pair is asserted
    assert {r["path"] for r in out["results"][:2]} == {ADR, PROJECT}
    off = search("retenção call recorder", index_dir=index_dir, embedder=FAKE, neighbours=False)
    assert "link" not in {w for r in off["results"] for w in r["why"]}


def test_sensitive_still_excluded_in_hybrid(vault, index_dir):
    _embedded(vault, index_dir)
    out = search("retenção", index_dir=index_dir, embedder=FAKE)
    assert TEAM not in {r["path"] for r in out["results"]}
    assert out["excluded_sensitive_hits"] == 2


def test_as_of_filters_by_date_and_flags(vault, index_dir):
    _embedded(vault, index_dir)
    out = search("retenção", index_dir=index_dir, embedder=FAKE, as_of="2026-07-15", include_sensitive=True)
    paths = {r["path"] for r in out["results"]}
    assert ADR not in paths and TEAM not in paths  # dated after as_of
    assert DAILY in paths and DEVOLUTIVA in paths
    assert all("changed_since_as_of" in r for r in out["results"])  # None here: tmp vault is not a git repo
    assert out["filters"]["as_of"] == "2026-07-15"


# ── bench ─────────────────────────────────────────────────────────────────────


def test_bench_reports_per_mode(vault, index_dir, tmp_path):
    _embedded(vault, index_dir)
    golden = tmp_path / "golden.jsonl"
    golden.write_text(
        f'{{"q": "retenção do transcript", "expect": "{ADR}"}}\n'
        + '# comentário\n'
        + f'{{"q": "grava chamadas do teams", "expect": "{PROJECT}"}}\n'
        + '{"q": "assunto que não existe em lugar nenhum", "expect": "Inbox/nada.md"}\n',
        encoding="utf-8",
    )
    rep = run_bench(golden, index_dir=index_dir, models=["fake"], embedder=FAKE, k=5)
    assert rep["questions"] == 3 and [r["mode"] for r in rep["runs"]] == ["fts", "vec", "hybrid"]
    fts = rep["runs"][0]
    assert fts["hit@5"] == pytest.approx(2 / 3, abs=1e-3) and fts["missed"] == 1  # the report rounds to 3 places
    assert 0 < fts["mrr"] <= 1
    assert all(len(r["details"]) == 3 for r in rep["runs"])


# ── briefing ──────────────────────────────────────────────────────────────────


SESSION = """---
date: 2026-09-01
---
# Session — 2026-09-01

## Open threads
- coisa velha do primeiro bloco

## Action items
- [x] (Kelvin) feito

# Session — 2026-09-01 14:10

## What happened
- segundo bloco

## Action items
- [x] (Kelvin) já feito
- [ ] (Kelvin) decidir o modelo de embedding

## Open threads
- golden set ainda sem 30 perguntas

## Next session context
Continuar na F2.
"""


def test_extract_sections_uses_last_block_and_unchecked_items():
    s = extract_sections(SESSION)
    assert "golden set" in s["open_threads"] and "coisa velha" not in s["open_threads"]
    assert s["action_items"] == "- [ ] (Kelvin) decidir o modelo de embedding"
    assert s["next_session_context"].startswith("Continuar")


def test_briefing_assembles_without_llm(vault, index_dir):
    _embedded(vault, index_dir)
    _w(vault, "AI/sessions/2026-08-30.md", "# Session — 2026-08-30\n\n## Open threads\n- antiga\n")
    _w(vault, "AI/sessions/2026-09-01.md", SESSION)
    b = briefing(
        root=vault,
        index_dir=index_dir,
        pending_loader=lambda repo: {"open": 2, "items": [{"id": "P-001", "texto": "decidir"}]},
        today=date(2026, 9, 3),
    )
    assert b["last_session"]["path"] == "AI/sessions/2026-09-01.md"
    assert "golden set" in b["last_session"]["open_threads"]
    assert b["pending"]["open"] == 2
    assert [d["path"] for d in b["recent_decisions"]] == [ADR]  # dated 2026-08-29, inside 30 days of 'today'
    recent = {n["path"] for n in b["recent_notes"]}
    assert TEAM not in recent and DEVOLUTIVA not in recent  # sensitive out by default
    assert not any(p.startswith("AI/sessions/") for p in recent)
    assert b["index"]["embedding_model"] == "fake"


# ── lint ──────────────────────────────────────────────────────────────────────


def test_lint_finds_structural_issues_and_writes_report(vault, index_dir):
    _w(vault, "Stakeholders/X/1on1.md", "---\ntype: 1on1\n---\n# 1:1 X\n\nOutro 1on1 com o mesmo nome de arquivo.\n")
    _w(vault, "Resources/velho.md", "---\ntype: reference\ndate: 2025-01-10\n---\nNúmero 42 (as of 2025-01, fonte) e outro (as of 2026-08, fonte).\n")
    _w(vault, "Projects/nota-tipada.md", "---\ntype: decision\ncontradicts: [[Call Recorder]]\nsupersedes: [[Inexistente]]\n---\nDiscorda.\n")
    db.build(vault, index_dir)
    rep = lint(root=vault, index_dir=index_dir, today=date(2026, 9, 3))
    broken = {it["target"] for it in rep["broken_links"]["items"]}
    assert "Projects/BIA-019" in broken
    assert rep["no_frontmatter"]["count"] == 1 and rep["no_frontmatter"]["items"] == [DAILY]
    assert rep["no_type"]["count"] == 0
    assert [d["stem"] for d in rep["duplicate_stems"]["items"]] == ["1on1"]
    assert rep["stale_recency"]["count"] == 1 and rep["stale_recency"]["items"][0]["markers"] == ["as of 2025-01"]
    typed = rep["typed_links"]
    assert typed["count"] == 2 and typed["unresolved"] == 1
    assert [c["to"] for c in typed["open_contradictions"]] == ["Call Recorder"]
    assert rep["sensitive_by_type_only"]["items"] == [DEVOLUTIVA]
    path = write_report(rep, root=vault)
    text = path.read_text(encoding="utf-8")
    assert path == vault / "_reports" / "Vault-Lint.md" and "type: lint-report" in text and "BIA-019" in text


def test_lint_cli_no_write(vault, index_dir, capsys):
    db.build(vault, index_dir)
    assert cli_main(["--root", str(vault), "--index-dir", str(index_dir), "lint", "--no-write"]) == EXIT_OK
    assert not (vault / "_reports" / "Vault-Lint.md").exists()


# ── memory corpus ─────────────────────────────────────────────────────────────


def test_memory_corpus_paths_are_derived_not_guessed():
    root, index_dir = memory_corpus()
    assert root.parts[-1] == "memory" and ".claude" in root.parts
    assert index_dir.name == "memory-index" and index_dir != db.default_index_dir()
