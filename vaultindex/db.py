"""
vaultindex/db.py — the derived index: SQLite + FTS5 built from the vault, rebuildable any time.

One writer. `IndexWriter` takes `index.lock` (PID inside) before touching the database,
the same single-flight rule as the call-recorder queue. Readers open the file in
`mode=ro`; WAL lets them read while a build runs. A missing index is an error on the
read path (`IndexMissing`), never an empty result set — the rule config.py applies to
the vault path (2026-09-01) applies here too.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from vaultindex.corpus import Note, file_sha256, iter_note_paths, parse_note, sha256_bytes

SCHEMA_VERSION = 1
DB_NAME = "index.sqlite"
LOCK_NAME = "index.lock"


class IndexMissing(RuntimeError):
    """No index on disk. The fix is `python -m vaultindex build`, not an empty answer."""


class IndexLocked(RuntimeError):
    def __init__(self, pid: int | None):
        self.pid = pid
        super().__init__(f"outro build está com o índice (PID {pid})" if pid else "índice travado")


class SchemaMismatch(RuntimeError):
    """Index written by another schema version. Rebuild with `build --full`."""


# ── paths ─────────────────────────────────────────────────────────────────────


def default_index_dir() -> Path:
    from config import VAULT_INDEX_DIR  # lazy: tests pass explicit dirs and may not want config

    return Path(VAULT_INDEX_DIR)


def default_root() -> Path:
    from config import VAULT_BASE

    return Path(VAULT_BASE)


def db_path(index_dir: Path | None = None) -> Path:
    return Path(index_dir or default_index_dir()) / DB_NAME


def _uri(path: Path, mode: str) -> str:
    return f"{path.resolve().as_uri()}?mode={mode}"


def connect_ro(index_dir: Path | None = None) -> sqlite3.Connection:
    p = db_path(index_dir)
    if not p.exists():
        raise IndexMissing(f"Índice não encontrado em {p}. Rode: python -m vaultindex build")
    con = sqlite3.connect(_uri(p, "ro"), uri=True)
    con.row_factory = sqlite3.Row
    version = _meta_value(con, "schema_version")
    if version is not None and int(version) != SCHEMA_VERSION:
        con.close()
        raise SchemaMismatch(f"índice em schema {version}, código espera {SCHEMA_VERSION}; rode build --full")
    return con


def _meta_value(con: sqlite3.Connection, key: str):
    try:
        row = con.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    except sqlite3.OperationalError:
        return None
    return row[0] if row else None


# ── lock ──────────────────────────────────────────────────────────────────────


def _pid_alive(pid: int) -> bool:
    if os.name == "nt":
        # os.kill(pid, 0) TERMINATES the process on Windows; ask tasklist instead.
        try:
            out = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True, timeout=20
            ).stdout
        except Exception:
            return True  # cannot tell -> assume alive, refuse to steal the lock
        return str(pid) in out
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


class _Lock:
    def __init__(self, path: Path):
        self.path = path

    def __enter__(self):
        for _attempt in range(2):
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode())
                os.close(fd)
                return self
            except FileExistsError:
                try:
                    pid = int(self.path.read_text().strip() or 0) or None
                except (OSError, ValueError):
                    pid = None
                if pid and _pid_alive(pid):  # own PID included: re-entry is a bug, not a case
                    raise IndexLocked(pid) from None
                # orphan lock (dead PID or unreadable): remove and retry once
                try:
                    self.path.unlink()
                except OSError:
                    pass
        raise IndexLocked(None)

    def __exit__(self, *exc):
        try:
            self.path.unlink()
        except OSError:
            pass
        return False


# ── schema ────────────────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY,
    rel_path TEXT NOT NULL UNIQUE,
    stem TEXT NOT NULL,
    title TEXT NOT NULL,
    type TEXT,
    date TEXT,
    date_source TEXT NOT NULL,
    tags TEXT NOT NULL DEFAULT '[]',
    folder TEXT NOT NULL,
    sensitive INTEGER NOT NULL DEFAULT 0,
    pinned INTEGER NOT NULL DEFAULT 0,
    has_frontmatter INTEGER NOT NULL DEFAULT 0,
    sha256 TEXT NOT NULL,
    mtime REAL NOT NULL,
    size INTEGER NOT NULL,
    indexed_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS notes_stem ON notes (stem);
CREATE INDEX IF NOT EXISTS notes_type ON notes (type);
CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY,
    note_id INTEGER NOT NULL REFERENCES notes (id) ON DELETE CASCADE,
    ord INTEGER NOT NULL,
    heading TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL,
    text TEXT NOT NULL,
    char_start INTEGER NOT NULL,
    char_end INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS chunks_note ON chunks (note_id);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5 (
    text, title, heading,
    content='chunks', content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);
CREATE TABLE IF NOT EXISTS links (
    id INTEGER PRIMARY KEY,
    from_note INTEGER NOT NULL REFERENCES notes (id) ON DELETE CASCADE,
    to_title TEXT NOT NULL,
    to_note INTEGER,
    kind TEXT NOT NULL DEFAULT 'wikilink'
);
CREATE INDEX IF NOT EXISTS links_from ON links (from_note);
CREATE INDEX IF NOT EXISTS links_to ON links (to_note);
CREATE TABLE IF NOT EXISTS embeddings (
    chunk_id INTEGER PRIMARY KEY REFERENCES chunks (id) ON DELETE CASCADE,
    model TEXT NOT NULL,
    dim INTEGER NOT NULL,
    vec BLOB NOT NULL
);
"""


# ── writer ────────────────────────────────────────────────────────────────────


@dataclass
class BuildReport:
    root: str
    index_dir: str
    full: bool
    started_at: str
    seconds: float = 0.0
    scanned: int = 0
    added: int = 0
    updated: int = 0
    unchanged: int = 0
    removed: int = 0
    notes: int = 0
    chunks: int = 0
    links: int = 0
    links_resolved: int = 0
    sensitive_notes: int = 0
    no_frontmatter: int = 0
    embeddings_stale_chunks: int = 0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


class IndexWriter:
    """The only thing that writes to the index. Use as a context manager."""

    def __init__(self, index_dir: Path | None = None, *, full: bool = False):
        self.index_dir = Path(index_dir or default_index_dir())
        self.full = full
        self.con: sqlite3.Connection | None = None
        self._lock: _Lock | None = None
        if "PYTEST_CURRENT_TEST" in os.environ:
            # Guard at the source (ARCHITECTURE pattern 10): a test never writes the real index.
            try:
                real = default_index_dir().resolve()
            except Exception:
                real = None
            if real is not None and self.index_dir.resolve() == real:
                raise RuntimeError("teste tentando escrever no índice real; passe index_dir=tmp_path")

    def __enter__(self):
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self._lock = _Lock(self.index_dir / LOCK_NAME).__enter__()
        p = db_path(self.index_dir)
        if self.full:
            for suffix in ("", "-wal", "-shm"):
                try:
                    Path(str(p) + suffix).unlink()
                except FileNotFoundError:
                    pass
        self.con = sqlite3.connect(p)
        self.con.row_factory = sqlite3.Row
        self.con.execute("PRAGMA journal_mode=WAL")
        self.con.execute("PRAGMA foreign_keys=ON")
        version = _meta_value(self.con, "schema_version")
        if version is not None and int(version) != SCHEMA_VERSION:
            self.con.close()
            self._lock.__exit__(None, None, None)
            raise SchemaMismatch(f"índice em schema {version}, código espera {SCHEMA_VERSION}; rode build --full")
        self.con.executescript(_SCHEMA)
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.con is not None:
            if exc_type is None:
                self.con.commit()
            else:
                self.con.rollback()
            self.con.close()
        if self._lock is not None:
            self._lock.__exit__(exc_type, exc, tb)
        return False

    # -- per note -------------------------------------------------------------

    def _delete_note(self, note_id: int) -> None:
        # FTS5 external-content tables do not see the cascade: tell the index first.
        rows = self.con.execute("SELECT id, text, title, heading FROM chunks WHERE note_id = ?", (note_id,)).fetchall()
        self.con.executemany(
            "INSERT INTO chunks_fts (chunks_fts, rowid, text, title, heading) VALUES ('delete', ?, ?, ?, ?)",
            [(r["id"], r["text"], r["title"], r["heading"]) for r in rows],
        )
        self.con.execute("DELETE FROM notes WHERE id = ?", (note_id,))

    def _insert_note(self, note: Note, indexed_at: str) -> int:
        cur = self.con.execute(
            """INSERT INTO notes (rel_path, stem, title, type, date, date_source, tags, folder, sensitive,
                                  pinned, has_frontmatter, sha256, mtime, size, indexed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                note.rel_path,
                note.stem,
                note.title,
                note.type,
                note.date,
                note.date_source,
                json.dumps(note.tags, ensure_ascii=False),
                note.folder,
                int(note.sensitive),
                int(note.pinned),
                int(note.has_frontmatter),
                note.sha256,
                note.mtime,
                note.size,
                indexed_at,
            ),
        )
        note_id = cur.lastrowid
        for c in note.chunks:
            heading = c.heading or ""
            cur = self.con.execute(
                "INSERT INTO chunks (note_id, ord, heading, title, text, char_start, char_end) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (note_id, c.ord, heading, note.title, c.text, c.char_start, c.char_end),
            )
            self.con.execute(
                "INSERT INTO chunks_fts (rowid, text, title, heading) VALUES (?, ?, ?, ?)",
                (cur.lastrowid, c.text, note.title, heading),
            )
        self.con.executemany(
            "INSERT INTO links (from_note, to_title, kind) VALUES (?, ?, ?)",
            [(note_id, link.target, link.kind) for link in note.links],
        )
        return note_id

    def _resolve_links(self) -> None:
        # Obsidian resolves [[Name]] by file name and [[folder/Name]] by path; mirror both.
        # Python dict lookups: a correlated UPDATE over 4,500 links x 1,149 notes was the slow
        # (and, in SQLite, not even valid) way to say the same thing.
        by_stem: dict[str, list[tuple[int, str]]] = {}
        by_path: dict[str, int] = {}
        for r in self.con.execute("SELECT id, stem, rel_path FROM notes"):
            by_stem.setdefault(r["stem"].lower(), []).append((r["id"], r["rel_path"]))
            by_path[r["rel_path"].lower()] = r["id"]
        updates: list[tuple[int | None, int]] = []
        for r in self.con.execute("SELECT id, to_title FROM links"):
            title = r["to_title"].lower()
            target: int | None = None
            hits = by_stem.get(title)
            if hits:
                target = min(hits, key=lambda h: (len(h[1]), h[1]))[0]  # Obsidian: shortest path wins
            elif title + ".md" in by_path:
                target = by_path[title + ".md"]
            elif "/" in title:
                suffix = "/" + title + ".md"
                cands = sorted(path for path in by_path if path.endswith(suffix))
                if cands:
                    target = by_path[cands[0]]
            updates.append((target, r["id"]))
        self.con.executemany("UPDATE links SET to_note = ? WHERE id = ?", updates)

    # -- the build --------------------------------------------------------------

    def build(self, root: Path) -> BuildReport:
        root = Path(root)
        t0 = time.monotonic()
        indexed_at = datetime.now().isoformat(timespec="seconds")
        report = BuildReport(root=str(root), index_dir=str(self.index_dir), full=self.full, started_at=indexed_at)
        if not root.is_dir():
            raise FileNotFoundError(f"raiz do vault não existe: {root}")

        existing = {
            r["rel_path"]: (r["id"], r["sha256"], r["mtime"], r["size"])
            for r in self.con.execute("SELECT id, rel_path, sha256, mtime, size FROM notes")
        }
        seen: set[str] = set()
        self.con.execute("BEGIN")
        for path in iter_note_paths(root):
            rel = path.relative_to(root).as_posix()
            seen.add(rel)
            report.scanned += 1
            st = path.stat()
            prev = existing.get(rel)
            if prev and not self.full and prev[2] == st.st_mtime and prev[3] == st.st_size:
                report.unchanged += 1  # mtime+size untouched: skip the read entirely
                continue
            raw = path.read_bytes()
            if prev and not self.full and prev[1] == sha256_bytes(raw):
                # touched by sync, same bytes: refresh mtime so the shortcut works next time
                self.con.execute("UPDATE notes SET mtime = ?, size = ? WHERE id = ?", (st.st_mtime, st.st_size, prev[0]))
                report.unchanged += 1
                continue
            try:
                note = parse_note(path, root, raw=raw)
            except Exception as e:  # one broken note must not sink the build
                report.warnings.append(f"{rel}: {type(e).__name__}: {e}")
                continue
            if prev:
                self._delete_note(prev[0])
                report.updated += 1
            else:
                report.added += 1
            self._insert_note(note, indexed_at)
        for rel, (note_id, *_rest) in existing.items():
            if rel not in seen:
                self._delete_note(note_id)
                report.removed += 1
        self._resolve_links()

        report.notes = self.con.execute("SELECT count(*) FROM notes").fetchone()[0]
        report.chunks = self.con.execute("SELECT count(*) FROM chunks").fetchone()[0]
        report.links = self.con.execute("SELECT count(*) FROM links").fetchone()[0]
        report.links_resolved = self.con.execute("SELECT count(*) FROM links WHERE to_note IS NOT NULL").fetchone()[0]
        report.sensitive_notes = self.con.execute("SELECT count(*) FROM notes WHERE sensitive = 1").fetchone()[0]
        report.no_frontmatter = self.con.execute("SELECT count(*) FROM notes WHERE has_frontmatter = 0").fetchone()[0]
        report.embeddings_stale_chunks = self.con.execute(
            "SELECT count(*) FROM chunks c LEFT JOIN embeddings e ON e.chunk_id = c.id WHERE e.chunk_id IS NULL"
        ).fetchone()[0]
        report.seconds = round(time.monotonic() - t0, 2)
        meta = {
            "schema_version": str(SCHEMA_VERSION),
            "corpus_root": str(root),
            "last_build": indexed_at,
            "last_build_seconds": str(report.seconds),
            "notes": str(report.notes),
            "chunks": str(report.chunks),
        }
        self.con.executemany("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", list(meta.items()))
        self.con.execute("COMMIT")
        return report


# ── public API ────────────────────────────────────────────────────────────────


def build(root: Path | None = None, index_dir: Path | None = None, *, full: bool = False) -> BuildReport:
    """Index the vault at `root` into `index_dir`. Incremental unless full=True."""
    root = Path(root or default_root())
    with IndexWriter(index_dir, full=full) as w:
        return w.build(root)


def stats(index_dir: Path | None = None) -> dict:
    con = connect_ro(index_dir)
    try:
        meta = {r["key"]: r["value"] for r in con.execute("SELECT key, value FROM meta")}
        by_type = {
            r["type"] or "(sem type)": r["n"]
            for r in con.execute("SELECT type, count(*) AS n FROM notes GROUP BY type ORDER BY n DESC")
        }
        out = {
            "index_dir": str(Path(index_dir or default_index_dir())),
            "db_bytes": db_path(index_dir).stat().st_size,
            "meta": meta,
            "notes": con.execute("SELECT count(*) FROM notes").fetchone()[0],
            "chunks": con.execute("SELECT count(*) FROM chunks").fetchone()[0],
            "links": con.execute("SELECT count(*) FROM links").fetchone()[0],
            "links_resolved": con.execute("SELECT count(*) FROM links WHERE to_note IS NOT NULL").fetchone()[0],
            "sensitive_notes": con.execute("SELECT count(*) FROM notes WHERE sensitive = 1").fetchone()[0],
            "no_frontmatter": con.execute("SELECT count(*) FROM notes WHERE has_frontmatter = 0").fetchone()[0],
            "embeddings": con.execute("SELECT count(*) FROM embeddings").fetchone()[0],
            "by_type": by_type,
        }
        return out
    finally:
        con.close()


@dataclass
class CheckReport:
    root: str
    index_dir: str
    corpus_files: int
    indexed_files: int
    changed: list[str] = field(default_factory=list)
    missing_in_index: list[str] = field(default_factory=list)
    extra_in_index: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not (self.changed or self.missing_in_index or self.extra_in_index)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["ok"] = self.ok
        return d


def check(root: Path | None = None, index_dir: Path | None = None) -> CheckReport:
    """Independent reader: hash every corpus file and compare with what the index says.

    Deliberately does NOT reuse the mtime shortcut the writer uses; this is the other
    side of the pair, and it has to disagree when the writer is wrong.
    """
    root = Path(root or default_root())
    con = connect_ro(index_dir)
    try:
        indexed = {r["rel_path"]: r["sha256"] for r in con.execute("SELECT rel_path, sha256 FROM notes")}
    finally:
        con.close()
    report = CheckReport(str(root), str(Path(index_dir or default_index_dir())), 0, len(indexed))
    seen: set[str] = set()
    for path in iter_note_paths(root):
        rel = path.relative_to(root).as_posix()
        seen.add(rel)
        report.corpus_files += 1
        sha = file_sha256(path)
        if rel not in indexed:
            report.missing_in_index.append(rel)
        elif indexed[rel] != sha:
            report.changed.append(rel)
    report.extra_in_index = sorted(set(indexed) - seen)
    return report
