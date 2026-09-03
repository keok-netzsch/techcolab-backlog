"""
vaultindex/search.py — retrieval over the derived index.

F1 ships the full-text stream (FTS5, bm25) inside the fusion + authority pipeline that
F2 extends with the local-embedding stream. Every response says which mode it ran in
and how old the index is. A sensitive hit the caller did not opt into is counted in
`excluded_sensitive_hits`, never silently dropped.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

from vaultindex.db import IndexLocked, build, connect_ro

RRF_K = 60
CANDIDATES = 60  # chunks pulled per stream before fusion
SNIPPETS_PER_NOTE = 2

# Authority multiplier (ADR §2.4 step 3): a bounded nudge, never an override.
AUTHORITY_UP = frozenset({"decision", "adr", "person", "project", "area", "reference"})
AUTHORITY_DOWN = frozenset({"session", "daily", "agent-report", "capture"})
AUTHORITY_MIN, AUTHORITY_MAX = 0.7, 1.3
EPISODIC_OLD_DAYS = 90

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def fts_match_expression(query: str) -> str | None:
    """Turn free text into an FTS5 MATCH expression.

    Tokens are quoted (so `and`/`or`/`not` in the query are words, not operators) and
    joined with OR: bm25 already rewards chunks that carry more of them. Tokens of five
    or more characters also match as prefixes, which covers Portuguese inflection
    (retenção / retenções) without a stemmer.
    """
    tokens = [t for t in _TOKEN_RE.findall(query) if len(t) > 1]
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
        m *= 1.15
    if t in AUTHORITY_DOWN:
        m *= 0.9
        age = _age_days(note["date"], today)
        if age is not None and age > EPISODIC_OLD_DAYS:
            m *= 0.8
    if note["rel_path"].startswith("Archive/"):
        m *= 0.85
    if note["pinned"]:
        m *= 1.2
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


def search(
    query: str,
    *,
    k: int = 10,
    include_sensitive: bool = False,
    types: list[str] | None = None,
    folder: str | None = None,
    since: str | None = None,
    until: str | None = None,
    refresh: bool = False,
    root: Path | None = None,
    index_dir: Path | None = None,
) -> dict:
    """Search the index. Returns a JSON-ready dict; see docs/vault-index.md for the contract."""
    types = [t.lower() for t in types] if types else None
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
        stale_chunks = con.execute(
            "SELECT count(*) FROM chunks c LEFT JOIN embeddings e ON e.chunk_id = c.id WHERE e.chunk_id IS NULL"
        ).fetchone()[0]

        match = fts_match_expression(query)
        out = {
            "query": query,
            "mode": "fts-only",
            "match": match,
            "last_build": last_build,
            "index_age_seconds": index_age_seconds,
            "embeddings_stale_chunks": stale_chunks,
            "refreshed": refreshed,
            "filters": {
                "include_sensitive": include_sensitive,
                "types": types,
                "folder": folder,
                "since": since,
                "until": until,
            },
            "candidates": {"fts": 0},
            "excluded_sensitive_hits": 0,
            "excluded_by_filter": 0,
            "results": [],
        }
        if not match:
            out["note"] = "nenhum termo pesquisável na query"
            return out

        fts_rows = con.execute(
            """SELECT rowid, bm25(chunks_fts, 1.0, 4.0, 2.0) AS score,
                      snippet(chunks_fts, 0, '[', ']', ' … ', 14) AS snip
               FROM chunks_fts WHERE chunks_fts MATCH ? ORDER BY score LIMIT ?""",
            (match, CANDIDATES),
        ).fetchall()
        out["candidates"]["fts"] = len(fts_rows)
        if not fts_rows:
            return out

        ids = [r["rowid"] for r in fts_rows]
        placeholders = ",".join("?" * len(ids))
        chunk_rows = {
            r["chunk_id"]: r
            for r in con.execute(
                f"""SELECT c.id AS chunk_id, c.heading, c.note_id, n.rel_path, n.title, n.type, n.date,
                           n.date_source, n.sensitive, n.pinned, n.has_frontmatter, n.tags
                    FROM chunks c JOIN notes n ON n.id = c.note_id WHERE c.id IN ({placeholders})""",
                ids,
            )
        }

        today = date.today()
        # stream ranks at note level (first appearance wins), plus per-note snippets
        streams: dict[str, list[int]] = {"fts": []}
        snippets: dict[int, list[dict]] = {}
        notes: dict[int, object] = {}
        hidden_sensitive: set[int] = set()
        hidden_other: set[int] = set()
        for r in fts_rows:
            c = chunk_rows.get(r["rowid"])
            if c is None:
                continue
            nid = c["note_id"]
            ok, why = _passes_filters(
                c, include_sensitive=include_sensitive, types=types, folder=folder, since=since, until=until
            )
            if not ok:
                (hidden_sensitive if why == "sensitive" else hidden_other).add(nid)
                continue
            notes.setdefault(nid, c)
            if nid not in streams["fts"]:
                streams["fts"].append(nid)
            bucket = snippets.setdefault(nid, [])
            if len(bucket) < SNIPPETS_PER_NOTE:
                bucket.append({"heading": c["heading"] or None, "text": r["snip"]})

        fused: dict[int, float] = {}
        why: dict[int, list[str]] = {}
        for name, ranked in streams.items():
            for rank, nid in enumerate(ranked):
                fused[nid] = fused.get(nid, 0.0) + 1.0 / (RRF_K + rank + 1)
                why.setdefault(nid, []).append(name)
        scored = sorted(
            ((fused[nid] * authority(notes[nid], today), nid) for nid in fused),
            key=lambda x: (-x[0], notes[x[1]]["rel_path"]),
        )
        out["excluded_sensitive_hits"] = len(hidden_sensitive)
        out["excluded_by_filter"] = len(hidden_other)
        for rank, (score, nid) in enumerate(scored[:k], start=1):
            n = notes[nid]
            out["results"].append(
                {
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
            )
        return out
    finally:
        con.close()
