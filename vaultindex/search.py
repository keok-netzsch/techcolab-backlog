"""
vaultindex/search.py — hybrid retrieval over the derived index.

Streams: `fts` (FTS5, bm25) and `vec` (cosine over local ONNX embeddings), joined by
reciprocal-rank fusion. Two bounded multipliers then nudge the fused score: authority by
note type, and a small lift for notes that are wikilink neighbours of a higher-ranked hit.
Every response says which mode it ran in, how old the index is and how many chunks still
lack a vector. A sensitive hit the caller did not opt into is counted in
`excluded_sensitive_hits`, never silently dropped.
"""

from __future__ import annotations

import re
import subprocess
from datetime import date, datetime
from pathlib import Path

import numpy as np

from vaultindex.db import IndexLocked, build, connect_ro, stale_chunks

# RRF with a small k keeps rank differences visible: with k=60, rank 1 and rank 3 differ by
# 3 %, and any multiplier above that reorders the top of the list at will. With k=20 the gap
# is 9 %, and a 1.08 authority nudge lifts a decision past a plain note only when they were
# already close (rank 2 beats rank 1; rank 3 does not).
RRF_K = 20
CANDIDATES = 60  # chunks pulled per stream before fusion
SNIPPETS_PER_NOTE = 2
NEIGHBOUR_SEEDS = 5  # a note linked to one of the N notes above it gets LINK_MULT
VEC_EXCERPT = 220  # characters of chunk text shown when only the vector stream found it

# Authority (ADR §2.4 step 3): a bounded nudge, never an override.
AUTHORITY_UP = frozenset({"decision", "adr", "person", "project", "area", "reference"})
AUTHORITY_DOWN = frozenset({"session", "daily", "agent-report", "capture"})
UP_MULT, DOWN_MULT, OLD_MULT, ARCHIVE_MULT, PINNED_MULT = 1.08, 0.95, 0.9, 0.95, 1.1
AUTHORITY_MIN, AUTHORITY_MAX = 0.8, 1.2
EPISODIC_OLD_DAYS = 90
LINK_MULT = 1.05

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def fts_match_expression(query: str) -> str | None:
    """Turn free text into an FTS5 MATCH expression.

    Tokens are quoted (so `and`/`or`/`not` in the query are words, not operators) and
    joined with OR: bm25 already rewards chunks that carry more of them. Two-letter tokens
    (`do`, `de`, `em`) are dropped whenever a longer token exists; alone they only fetch
    noise. Tokens of five or more characters also match as prefixes, which covers
    Portuguese inflection (retenção / retenções) without a stemmer.
    """
    tokens = [t for t in _TOKEN_RE.findall(query) if len(t) > 1]
    if any(len(t) >= 3 for t in tokens):
        tokens = [t for t in tokens if len(t) >= 3]
    if not tokens:
        return None
    parts = []
    for t in tokens:
        t = t.replace('"', '""')
        parts.append(f'"{t}"*' if len(t) >= 5 else f'"{t}"')
    return " OR ".join(parts)


def _age_days(iso: str | None, today: date) -> int | None:
    if not iso:
        return None
    try:
        return (today - date.fromisoformat(iso)).days
    except ValueError:
        return None


def authority(note, today: date) -> float:
    m = 1.0
    t = note["type"]
    if t in AUTHORITY_UP:
        m *= UP_MULT
    if t in AUTHORITY_DOWN:
        m *= DOWN_MULT
        age = _age_days(note["date"], today)
        if age is not None and age > EPISODIC_OLD_DAYS:
            m *= OLD_MULT
    path_l = note["rel_path"].lower()
    if path_l.startswith("archive/") or "/_arquivo/" in path_l or "/archive/" in path_l:
        m *= ARCHIVE_MULT  # closed or archived material: still searchable, slightly behind live notes
    if note["pinned"]:
        m *= PINNED_MULT
    return min(AUTHORITY_MAX, max(AUTHORITY_MIN, m))


def _passes_filters(note, *, include_sensitive, types, folder, since, until) -> tuple[bool, str | None]:
    if note["sensitive"] and not include_sensitive:
        return False, "sensitive"
    if types and (note["type"] or "") not in types:
        return False, "type"
    if folder and not note["rel_path"].lower().startswith(folder.lower()):
        return False, "folder"
    d = note["date"]
    if since and (not d or d < since):
        return False, "date"
    if until and (not d or d > until):
        return False, "date"
    return True, None


def _excerpt(text: str, limit: int = VEC_EXCERPT) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[:limit].rsplit(" ", 1)[0] + " …"


def _changed_since(root: Path, rel_paths: list[str], since_iso: str) -> dict[str, bool | None]:
    """Per path: did the vault's own git see a commit after `since_iso`? None when unknown."""
    out: dict[str, bool | None] = {}
    for rel in rel_paths:
        try:
            r = subprocess.run(
                ["git", "-C", str(root), "log", "-1", "--format=%H", f"--since={since_iso}", "--", rel],
                capture_output=True,
                text=True,
                timeout=20,
            )
            out[rel] = bool(r.stdout.strip()) if r.returncode == 0 else None
        except Exception:
            out[rel] = None
    return out


def search(
    query: str,
    *,
    k: int = 10,
    include_sensitive: bool = False,
    types: list[str] | None = None,
    folder: str | None = None,
    since: str | None = None,
    until: str | None = None,
    as_of: str | None = None,
    refresh: bool = False,
    root: Path | None = None,
    index_dir: Path | None = None,
    streams: tuple[str, ...] = ("fts", "vec"),
    model: str | None = None,
    neighbours: bool = True,
    embedder=None,
) -> dict:
    """Search the index. Returns a JSON-ready dict; contract in docs/vault-index.md.

    `streams` picks the retrieval streams (`fts`, `vec`); `neighbours` turns the wikilink
    lift on or off. `as_of` keeps notes dated on or before that day and, when the corpus
    root is a git repo, flags results changed since (approximate, by design).
    """
    types = [t.lower() for t in types] if types else None
    until_eff = min(until, as_of) if (until and as_of) else (as_of or until)
    refreshed: dict | None = None
    if refresh:
        # The refresh IS the writer (same lock, same code path); search itself stays read-only.
        try:
            rep = build(root=root, index_dir=index_dir)
            refreshed = {"added": rep.added, "updated": rep.updated, "removed": rep.removed, "seconds": rep.seconds}
        except IndexLocked as e:
            refreshed = {"skipped": f"build em andamento (PID {e.pid})"}

    con = connect_ro(index_dir)
    try:
        meta = {r["key"]: r["value"] for r in con.execute("SELECT key, value FROM meta")}
        last_build = meta.get("last_build")
        index_age_seconds = None
        if last_build:
            index_age_seconds = int((datetime.now() - datetime.fromisoformat(last_build)).total_seconds())
        active_model = model or meta.get("embedding_model")
        notes_out: list[str] = []

        out = {
            "query": query,
            "mode": "fts-only",
            "match": None,
            "model": active_model,
            "last_build": last_build,
            "index_age_seconds": index_age_seconds,
            "embeddings_stale_chunks": stale_chunks(con, active_model),
            "refreshed": refreshed,
            "filters": {
                "include_sensitive": include_sensitive,
                "types": types,
                "folder": folder,
                "since": since,
                "until": until,
                "as_of": as_of,
            },
            "streams": list(streams),
            "candidates": {},
            "excluded_sensitive_hits": 0,
            "excluded_by_filter": 0,
            "results": [],
        }

        # -- stream 1: full text ----------------------------------------------------------
        fts_hits: list[tuple[int, str]] = []  # (chunk_id, snippet) in rank order
        if "fts" in streams:
            match = fts_match_expression(query)
            out["match"] = match
            if match:
                rows = con.execute(
                    """SELECT rowid, bm25(chunks_fts, 1.0, 4.0, 2.0) AS score,
                              snippet(chunks_fts, 0, '[', ']', ' … ', 14) AS snip
                       FROM chunks_fts WHERE chunks_fts MATCH ? ORDER BY score LIMIT ?""",
                    (match, CANDIDATES),
                ).fetchall()
                fts_hits = [(r["rowid"], r["snip"]) for r in rows]
            else:
                notes_out.append("nenhum termo pesquisável para o fluxo full-text")
            out["candidates"]["fts"] = len(fts_hits)

        # -- stream 2: vectors ------------------------------------------------------------
        vec_hits: list[tuple[int, float]] = []  # (chunk_id, cosine) in rank order
        if "vec" in streams:
            if not active_model:
                notes_out.append("sem modelo de embedding ativo; rode: python -m vaultindex embed")
            else:
                try:
                    from vaultindex.embed import ModelUnavailable, get_embedder, load_vectors

                    emb = embedder or get_embedder(active_model, index_dir, download=False)
                    ids, mat = load_vectors(con, active_model)
                    if len(ids) == 0:
                        notes_out.append(f"nenhum vetor para {active_model}; rode: python -m vaultindex embed")
                    else:
                        qv = emb.encode([query])[0]
                        sims = mat @ qv
                        n = min(CANDIDATES, len(ids))
                        top = np.argpartition(-sims, n - 1)[:n]
                        top = top[np.argsort(-sims[top])]
                        vec_hits = [(int(ids[i]), float(sims[i])) for i in top]
                except ModelUnavailable as e:
                    notes_out.append(f"fluxo vetorial desligado: {e}")
            out["candidates"]["vec"] = len(vec_hits)

        if vec_hits and fts_hits:
            out["mode"] = "hybrid"
        elif vec_hits:
            out["mode"] = "vec-only"

        chunk_ids = list({cid for cid, _ in fts_hits} | {cid for cid, _ in vec_hits})
        if not chunk_ids:
            if notes_out:
                out["note"] = "; ".join(notes_out)
            return out

        placeholders = ",".join("?" * len(chunk_ids))
        chunk_rows = {
            r["chunk_id"]: r
            for r in con.execute(
                f"""SELECT c.id AS chunk_id, c.heading, c.text, c.note_id, n.rel_path, n.title, n.type, n.date,
                           n.date_source, n.sensitive, n.pinned, n.has_frontmatter, n.tags
                    FROM chunks c JOIN notes n ON n.id = c.note_id WHERE c.id IN ({placeholders})""",
                chunk_ids,
            )
        }

        today = date.today()
        notes: dict[int, object] = {}
        hidden_sensitive: set[int] = set()
        hidden_other: set[int] = set()
        stream_ranks: dict[str, list[int]] = {}
        snippets: dict[int, list[dict]] = {}
        vec_sim: dict[int, float] = {}

        def admit(chunk_id: int) -> int | None:
            c = chunk_rows.get(chunk_id)
            if c is None:
                return None
            nid = c["note_id"]
            if nid in notes:
                return nid
            if nid in hidden_sensitive or nid in hidden_other:
                return None
            ok, why = _passes_filters(
                c, include_sensitive=include_sensitive, types=types, folder=folder, since=since, until=until_eff
            )
            if not ok:
                (hidden_sensitive if why == "sensitive" else hidden_other).add(nid)
                return None
            notes[nid] = c
            return nid

        for cid, snip in fts_hits:
            nid = admit(cid)
            if nid is None:
                continue
            ranked = stream_ranks.setdefault("fts", [])
            if nid not in ranked:
                ranked.append(nid)
            bucket = snippets.setdefault(nid, [])
            if len(bucket) < SNIPPETS_PER_NOTE:
                bucket.append({"heading": chunk_rows[cid]["heading"] or None, "text": snip, "from": "fts"})
        for cid, sim in vec_hits:
            nid = admit(cid)
            if nid is None:
                continue
            ranked = stream_ranks.setdefault("vec", [])
            if nid not in ranked:
                ranked.append(nid)
                vec_sim[nid] = round(sim, 4)
            bucket = snippets.setdefault(nid, [])
            if len(bucket) < SNIPPETS_PER_NOTE and not any(s["from"] == "fts" for s in bucket):
                c = chunk_rows[cid]
                bucket.append({"heading": c["heading"] or None, "text": _excerpt(c["text"]), "from": "vec"})

        fused: dict[int, float] = {}
        for ranked in stream_ranks.values():
            for rank, nid in enumerate(ranked):
                fused[nid] = fused.get(nid, 0.0) + 1.0 / (RRF_K + rank + 1)
        why: dict[int, list[str]] = {}
        for name, ranked in stream_ranks.items():
            for nid in ranked:
                why.setdefault(nid, []).append(name)

        # -- wikilink neighbours: a note linked to one ranked above it gets a small lift ---
        boosted: list[int] = []
        if neighbours and len(fused) > 1:
            order = sorted(fused, key=lambda nid: (-fused[nid], notes[nid]["rel_path"]))
            ph = ",".join("?" * len(order))
            pairs: set[tuple[int, int]] = set()
            for r in con.execute(
                f"SELECT from_note, to_note FROM links WHERE to_note IS NOT NULL AND from_note IN ({ph}) AND to_note IN ({ph})",
                order + order,
            ):
                pairs.add((r[0], r[1]))
                pairs.add((r[1], r[0]))
            for pos, nid in enumerate(order):
                above = order[: min(pos, NEIGHBOUR_SEEDS)]
                if any((nid, a) in pairs for a in above):
                    fused[nid] *= LINK_MULT
                    why[nid].append("link")
                    boosted.append(nid)
            out["candidates"]["link"] = len(boosted)

        scored = sorted(
            ((fused[nid] * authority(notes[nid], today), nid) for nid in fused),
            key=lambda x: (-x[0], notes[x[1]]["rel_path"]),
        )
        out["excluded_sensitive_hits"] = len(hidden_sensitive)
        out["excluded_by_filter"] = len(hidden_other)
        top_k = scored[:k]

        changed: dict[str, bool | None] = {}
        if as_of and top_k:
            changed = _changed_since(
                Path(root) if root else _corpus_root(meta), [notes[nid]["rel_path"] for _, nid in top_k], as_of
            )

        for rank, (score, nid) in enumerate(top_k, start=1):
            n = notes[nid]
            item = {
                "rank": rank,
                "path": n["rel_path"],
                "title": n["title"],
                "type": n["type"],
                "date": n["date"],
                "date_source": n["date_source"],
                "sensitive": bool(n["sensitive"]),
                "has_frontmatter": bool(n["has_frontmatter"]),
                "score": round(score, 6),
                "authority": round(authority(n, today), 3),
                "why": why[nid],
                "snippets": snippets.get(nid, []),
            }
            if nid in vec_sim:
                item["vec_sim"] = vec_sim[nid]
            if as_of:
                item["changed_since_as_of"] = changed.get(n["rel_path"])
            out["results"].append(item)
        if notes_out:
            out["note"] = "; ".join(notes_out)
        return out
    finally:
        con.close()


def _corpus_root(meta: dict) -> Path:
    root = meta.get("corpus_root")
    if root:
        return Path(root)
    from vaultindex.db import default_root

    return default_root()
