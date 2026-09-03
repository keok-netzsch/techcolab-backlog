"""
vaultindex/corpus.py — walk the vault and turn each note into an indexable record.

Markdown is the source of truth; nothing here writes to the vault. The parser is
tolerant on purpose: 164 of 1,149 notes had no frontmatter on 2026-09-03 and they
still have to be searchable. Whatever is missing is recorded as missing
(`has_frontmatter = 0`, `date_source = "mtime"`), never guessed silently.
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass, field
from datetime import date as _date
from datetime import datetime
from pathlib import Path

import yaml

# Folders that never enter the index. Backups and rollback snapshots are duplicates
# of live notes and would show up as competing results; templates are not knowledge.
EXCLUDE_DIRS = frozenset(
    {
        ".git",
        ".obsidian",
        ".trash",
        ".smart-env",
        "_attachments",
        "_obsidian-second-brain-ref",
        "Templates",
        "rollback",
        "__pycache__",
        "node_modules",
    }
)
EXCLUDE_DIR_PREFIXES = ("backup",)  # vault/backup-notas-2026-09-02 and the like

# Sensitivity (ADR 2026-09-03 §2.1 item 6): out of every result unless the caller
# opts in. Same contract as vault_get_context_for_idea(include_sensitive=...).
SENSITIVE_FOLDERS = ("Team/", "Stakeholders/")
SENSITIVE_TYPES = frozenset(
    {"1on1", "1on1-session", "1on1-log", "1on1-agenda", "manager-call", "devolutiva", "person"}
)

# Characters per chunk. Env override exists for the chunk-size experiment only; the value that
# wins the bench is what ships here, and every build of an index must use the same value
# (a different one re-chunks everything and drops every vector on the next --full build).
# 600 won the bench on 2026-09-03 against 900 (hybrid hit@5 0.763 vs 0.684, MRR 0.486 vs 0.447):
# the active model has a 128-token window, and a 900-character chunk was losing its tail.
CHUNK_MAX = int(os.environ.get("TECHCOLAB_CHUNK_MAX") or 600)
CHUNK_MERGE_MIN = 200  # a section shorter than this merges into the previous chunk when it fits

TYPED_LINK_FIELDS = ("supersedes", "superseded_by", "contradicts", "causes", "fixes")

_FM_RE = re.compile(r"\A\ufeff?---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.S)
_H1_RE = re.compile(r"^#[ \t]+(.+?)[ \t]*$", re.M)
_SECTION_SPLIT_RE = re.compile(r"(?=^#{2,3}[ \t]+)", re.M)
_HEADING_LINE_RE = re.compile(r"\A#{2,3}[ \t]+(.+?)[ \t]*$", re.M)
_PARAGRAPH_SPLIT_RE = re.compile(r"(\n[ \t]*\n)")
_WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
_ISO_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


@dataclass
class Chunk:
    ord: int
    heading: str | None
    text: str
    char_start: int
    char_end: int


@dataclass
class Link:
    kind: str  # wikilink | supersedes | superseded_by | contradicts | causes | fixes
    target: str  # note stem or relative path, as written in the source


@dataclass
class Note:
    rel_path: str
    stem: str
    title: str
    type: str | None
    date: str | None
    date_source: str  # frontmatter | filename | mtime
    tags: list[str]
    folder: str
    sensitive: bool
    pinned: bool
    has_frontmatter: bool
    sha256: str
    mtime: float
    size: int
    chunks: list[Chunk] = field(default_factory=list)
    links: list[Link] = field(default_factory=list)


# ── walking ───────────────────────────────────────────────────────────────────


def _excluded_dir(name: str) -> bool:
    return name in EXCLUDE_DIRS or name.lower().startswith(EXCLUDE_DIR_PREFIXES)


def iter_note_paths(root: Path):
    """Yield every indexable .md under root, in a stable order."""
    root = Path(root)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not _excluded_dir(d))
        for name in sorted(filenames):
            if name.lower().endswith(".md"):
                yield Path(dirpath) / name


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def file_sha256(path: Path) -> str:
    return sha256_bytes(Path(path).read_bytes())


# ── frontmatter ───────────────────────────────────────────────────────────────


def split_frontmatter(text: str) -> tuple[dict, str, bool]:
    """Return (frontmatter dict, body, had_block).

    A block that exists but does not parse still counts as present (`had_block=True`)
    with an empty dict; the lint pass is the place that names unparsable blocks.
    """
    m = _FM_RE.match(text)
    if not m:
        return {}, text.lstrip("\ufeff"), False
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        fm = {}
    if not isinstance(fm, dict):
        fm = {}
    return fm, text[m.end() :], True


def _as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = value.strip()
        return [value] if value else []
    if isinstance(value, (list, tuple, set)):
        out: list[str] = []
        for v in value:
            # `contradicts: [[Note]]` is YAML for a list inside a list: flatten one level
            items = v if isinstance(v, (list, tuple, set)) else [v]
            out.extend(str(x).strip() for x in items if str(x).strip())
        return out
    return [str(value).strip()]


def _iso_date(value) -> str | None:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, _date):
        return value.isoformat()
    if isinstance(value, str):
        m = _ISO_DATE_RE.search(value)
        if m:
            try:
                return _date.fromisoformat(m.group(1)).isoformat()
            except ValueError:
                return None
    return None


def _resolve_date(fm: dict, stem: str, mtime: float) -> tuple[str, str]:
    d = _iso_date(fm.get("date"))
    if d:
        return d, "frontmatter"
    d = _iso_date(stem)
    if d:
        return d, "filename"
    return datetime.fromtimestamp(mtime).date().isoformat(), "mtime"


def _first_h1(body: str) -> str | None:
    m = _H1_RE.search(body)
    return m.group(1).strip() if m else None


def _note_type(fm: dict) -> str | None:
    value = fm.get("type")
    if isinstance(value, (list, tuple)):
        value = value[0] if value else None
    if value in (None, ""):
        return None
    return str(value).strip().lower()


# ── chunking ──────────────────────────────────────────────────────────────────


def _hard_split(text: str, start: int, chunk_max: int):
    """Split one oversized paragraph at whitespace, yielding (piece, abs_start)."""
    pos = 0
    n = len(text)
    while pos < n:
        end = min(pos + chunk_max, n)
        if end < n:
            cut = text.rfind(" ", pos + chunk_max // 2, end)
            if cut > pos:
                end = cut
        yield text[pos:end], start + pos
        pos = end


def _split_section(text: str, start: int, chunk_max: int):
    """Yield (piece, abs_start) pieces no longer than chunk_max, on paragraph boundaries."""
    if len(text) <= chunk_max:
        yield text, start
        return
    buf, buf_start, offset = "", start, start
    for part in _PARAGRAPH_SPLIT_RE.split(text):
        if buf and len(buf) + len(part) > chunk_max:
            if buf.strip():
                if len(buf) > chunk_max:
                    yield from _hard_split(buf, buf_start, chunk_max)
                else:
                    yield buf, buf_start
            buf, buf_start = "", offset
        buf += part
        offset += len(part)
    if buf.strip():
        if len(buf) > chunk_max:
            yield from _hard_split(buf, buf_start, chunk_max)
        else:
            yield buf, buf_start


def chunk_body(body: str, chunk_max: int = CHUNK_MAX) -> list[Chunk]:
    """Split a note body at H2/H3 boundaries, then cap each section at chunk_max chars.

    The heading line stays with its section. Tiny sections merge into the previous
    chunk when the result still fits, so a note made of one-line headings does not
    become a pile of near-empty chunks.
    """
    if not body.strip():
        return []
    pieces: list[tuple[str | None, str, int]] = []  # (heading, text, abs_start)
    offset = 0
    for section in _SECTION_SPLIT_RE.split(body):
        if not section:
            continue
        m = _HEADING_LINE_RE.match(section)
        heading = m.group(1).strip() if m else None
        for piece, abs_start in _split_section(section, offset, chunk_max):
            pieces.append((heading, piece, abs_start))
        offset += len(section)

    chunks: list[Chunk] = []
    for heading, text, abs_start in pieces:
        if not text.strip():
            continue
        if chunks and len(text) < CHUNK_MERGE_MIN and len(chunks[-1].text) + len(text) <= chunk_max:
            prev = chunks[-1]
            gap = body[prev.char_end : abs_start]  # keep text == body[start:end] across the merge
            prev.text = prev.text + gap + text
            prev.char_end = abs_start + len(text)
            continue
        chunks.append(Chunk(len(chunks), heading, text, abs_start, abs_start + len(text)))
    for c in chunks:  # trim the edges without breaking the offset invariant
        lead = len(c.text) - len(c.text.lstrip())
        c.char_start += lead
        c.text = c.text[lead:].rstrip()
        c.char_end = c.char_start + len(c.text)
    return chunks


# ── links ─────────────────────────────────────────────────────────────────────


def _clean_target(raw: str) -> str:
    t = raw.strip().strip("[]").strip().strip("\"'").strip()
    if "|" in t:
        t = t.split("|", 1)[0].strip()
    if "#" in t:
        t = t.split("#", 1)[0].strip()
    if t.lower().endswith(".md"):
        t = t[:-3]
    return t


def extract_links(body: str, fm: dict) -> list[Link]:
    links: list[Link] = []
    seen: set[tuple[str, str]] = set()
    for m in _WIKILINK_RE.finditer(body):
        target = _clean_target(m.group(1))
        key = ("wikilink", target.lower())
        if target and key not in seen:
            seen.add(key)
            links.append(Link("wikilink", target))
    for kind in TYPED_LINK_FIELDS:
        for raw in _as_list(fm.get(kind)):
            target = _clean_target(raw)
            key = (kind, target.lower())
            if target and key not in seen:
                seen.add(key)
                links.append(Link(kind, target))
    return links


# ── the record ────────────────────────────────────────────────────────────────


def parse_note(path: Path, root: Path, *, raw: bytes | None = None, chunk_max: int = CHUNK_MAX) -> Note:
    path, root = Path(path), Path(root)
    if raw is None:
        raw = path.read_bytes()
    st = path.stat()
    text = raw.decode("utf-8", errors="replace")
    fm, body, has_fm = split_frontmatter(text)
    rel = path.relative_to(root).as_posix()
    stem = path.stem
    folder = rel.rsplit("/", 1)[0] if "/" in rel else ""
    # backlog ideas carry `titulo:` (PT schema); everything else `title:`
    title = str(fm.get("title") or fm.get("titulo") or "").strip() or _first_h1(body) or stem
    ntype = _note_type(fm)
    date, date_source = _resolve_date(fm, stem, st.st_mtime)
    sensitive = rel.startswith(SENSITIVE_FOLDERS) or (ntype in SENSITIVE_TYPES)
    return Note(
        rel_path=rel,
        stem=stem,
        title=title,
        type=ntype,
        date=date,
        date_source=date_source,
        tags=_as_list(fm.get("tags")),
        folder=folder,
        sensitive=bool(sensitive),
        pinned=fm.get("pinned") is True,
        has_frontmatter=has_fm,
        sha256=sha256_bytes(raw),
        mtime=st.st_mtime,
        size=len(raw),
        chunks=chunk_body(body, chunk_max),
        links=extract_links(body, fm),
    )
