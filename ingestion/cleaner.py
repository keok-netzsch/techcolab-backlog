"""
ingestion/cleaner.py — Post-ingestion cleanup of source note files.

Strategy:
  - Append INGESTED_TAG to notes that were fully processed.
  - Consolidate multiple claude.md files into one.

We do NOT delete content from notes — the user decides what to prune manually
after reviewing the backlog. The tag is sufficient to prevent re-ingestion.
"""

from __future__ import annotations

from pathlib import Path

from config import CLAUDE_MD, INGESTED_TAG, VAULT_ROOT


def mark_as_ingested(note_path: Path) -> None:
    """Append INGESTED_TAG to the note so it won't be picked up again."""
    text = note_path.read_text(encoding="utf-8")
    if INGESTED_TAG not in text:
        note_path.write_text(text.rstrip() + f"\n\n{INGESTED_TAG}\n", encoding="utf-8")


def consolidate_claude_md() -> bool:
    """
    Find all claude.md files under the vault root.
    If more than one exists, merge them into CLAUDE_MD and remove duplicates.
    Returns True if a merge was performed.
    """
    candidates = sorted(VAULT_ROOT.rglob("claude.md"))

    if len(candidates) <= 1:
        return False  # nothing to do

    primary = CLAUDE_MD  # canonical destination

    merged_parts = []
    for path in candidates:
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            continue
        merged_parts.append(f"<!-- source: {path.relative_to(VAULT_ROOT)} -->\n{text}")

    merged = "\n\n---\n\n".join(merged_parts)
    primary.parent.mkdir(parents=True, exist_ok=True)
    primary.write_text(merged + "\n", encoding="utf-8")

    # Remove secondary files (keep only the primary)
    for path in candidates:
        if path.resolve() != primary.resolve():
            path.unlink()

    return True
