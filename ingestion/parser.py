"""
ingestion/parser.py — Reads raw note files from the notes/ directory.

Returns a list of RawNote objects: file path + text content.
Files already tagged with INGESTED_TAG are skipped.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from config import VAULT_NOTES_DIR, INGESTED_TAG, MIN_NOTE_LENGTH


@dataclass
class RawNote:
    path: Path
    content: str

    @property
    def relative_path(self) -> str:
        try:
            return str(self.path.relative_to(self.path.parent.parent))
        except ValueError:
            return str(self.path)


def load_notes(notes_dir: Path = VAULT_NOTES_DIR) -> list[RawNote]:
    """
    Scan notes_dir recursively for .md files.
    Skips files that are already marked as ingested.
    Skips files below MIN_NOTE_LENGTH.
    """
    notes_dir = Path(notes_dir)
    if not notes_dir.exists():
        raise FileNotFoundError(f"Notes directory not found: {notes_dir}")

    raw_notes = []
    for path in sorted(notes_dir.rglob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")

        if INGESTED_TAG in text:
            continue

        # Strip whitespace-only files and very short files
        stripped = text.strip()
        if len(stripped) < MIN_NOTE_LENGTH:
            continue

        raw_notes.append(RawNote(path=path, content=stripped))

    return raw_notes
