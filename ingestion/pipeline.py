"""
ingestion/pipeline.py — Orchestrates the full ingestion flow:
  1. Consolidate claude.md (if duplicates exist)
  2. Load raw notes from notes/
  3. Extract ideas via Claude API
  4. Save ideas to backlog/
  5. Mark notes as ingested
  6. Regenerate _index.md
"""

from __future__ import annotations

from pathlib import Path

from config import VAULT_NOTES_DIR, BACKLOG_DIR, BACKLOG_INDEX
from ingestion.parser import load_notes
from ingestion.extractor import extract_ideas_from_note, build_client
from ingestion.cleaner import mark_as_ingested, consolidate_claude_md
from backlog.store import BacklogStore
from backlog.index import generate_index


def run_ingestion(dry_run: bool = False) -> dict:
    results = {"created": 0, "skipped": 0, "cleaned": 0}

    # Step 1: Consolidate claude.md
    merged = consolidate_claude_md()
    if merged:
        print("[cleaner] Merged multiple claude.md files into one.")

    # Step 2: Load notes
    notes = load_notes(Path(VAULT_NOTES_DIR))
    if not notes:
        print("[parser] No unprocessed notes found.")
        return results

    print(f"[parser] Found {len(notes)} note(s) to process.")

    if dry_run:
        # In dry-run mode, validate parsing only — no API calls, no writes.
        for note in notes:
            preview = note.content[:120].replace("\n", " ")
            print(f"\n[dry-run] {note.relative_path} ({len(note.content)} chars)")
            print(f"  preview: {preview}...")
        results["created"] = len(notes)
        return results

    # Step 3-5: Extract + save + mark
    client = build_client()
    store = BacklogStore(Path(BACKLOG_DIR))

    for note in notes:
        print(f"\n[extractor] Processing: {note.relative_path}")
        try:
            extracted = extract_ideas_from_note(note, client)
        except Exception as e:
            print(f"  [ERROR] {e}")
            results["skipped"] += 1
            continue

        if not extracted:
            print(f"  -> No ideas found. Skipping.")
            results["skipped"] += 1
            continue

        print(f"  -> {len(extracted)} idea(s) extracted.")

        if not dry_run:
            for raw in extracted:
                idea = store.create(
                    title=raw.get("titulo", "Sem titulo"),
                    description=raw.get("descricao", ""),
                    area=raw.get("area"),
                    priority=raw.get("prioridade", "media"),
                    origin=note.relative_path,
                    todos=[{"text": t, "done": False} for t in raw.get("todos", [])],
                )
                print(f"  -> Saved: [{idea.id}] {idea.title}")
                results["created"] += 1

            mark_as_ingested(note.path)
            results["cleaned"] += 1
        else:
            for raw in extracted:
                print(f"  [dry-run] Would create: {raw.get('titulo', '?')}")
            results["created"] += len(extracted)

    # Step 6: Regenerate index
    if not dry_run:
        all_ideas = store.load_all()
        generate_index(all_ideas, Path(BACKLOG_INDEX))
        print(f"\n[index] _index.md updated ({len(all_ideas)} ideas total).")

    return results
