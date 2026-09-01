"""
agent/update_status.py — Update a backlog item's status from the command line.

Called by Claude Code (Phase 2) to track execution progress automatically.

Usage:
    python agent/update_status.py <idea_id> <new_status>

Example:
    python agent/update_status.py idea-017 "em desenvolvimento"
    python agent/update_status.py idea-017 "em validação"
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from backlog.daily_log import log_entry
from backlog.index import generate_index
from backlog.schema import VALID_STATUSES
from backlog.store import BacklogStore
from config import BACKLOG_DIR, BACKLOG_INDEX


def update_status(idea_id: str, new_status: str) -> None:
    if new_status not in VALID_STATUSES:
        print(f"[ERROR] Invalid status: '{new_status}'")
        print(f"Valid statuses: {', '.join(VALID_STATUSES)}")
        sys.exit(1)

    store = BacklogStore(BACKLOG_DIR)
    idea = store.load_by_id(idea_id)

    if not idea:
        print(f"[ERROR] Idea not found: {idea_id}")
        sys.exit(1)

    old_status = idea.status
    idea.status = new_status
    # auto_advance=False: this IS the explicit decision, the store must not second-guess it.
    store.save(idea, auto_advance=False)
    # Regenerate the vault index here because the CLI must not depend on the app:
    # the Streamlit app also refreshes _index.md, but only when someone opens it,
    # and this CLI is how status actually changes day-to-day - the index was 10
    # days stale on 2026-08-31 for exactly that reason. Best-effort: a broken
    # index must never fail a status change.
    try:
        generate_index(store.load_all(), Path(BACKLOG_INDEX))
    except Exception as e:  # noqa: BLE001
        print(f"[WARN] _index.md not regenerated: {e}")
    # Record it in the daily note, for the same reason as the index: log_entry was
    # only ever called from inside the Streamlit app, so every change made through
    # this CLI left no trace in Daily/ — which is what feeds the Weekly Brief
    # page's "Developments" section. Best-effort, never fatal.
    try:
        if new_status == "concluído":
            log_entry("concluida", idea)
        else:
            log_entry("alterada", idea, f"status: {old_status} -> {new_status}")
    except Exception as e:  # noqa: BLE001
        print(f"[WARN] daily note not updated: {e}")
    print(f"[OK] {idea_id}: '{old_status}' -> '{new_status}'")


def main():
    if len(sys.argv) != 3:
        print("Usage: python agent/update_status.py <idea_id> <new_status>")
        print(f"Valid statuses: {', '.join(VALID_STATUSES)}")
        sys.exit(1)

    update_status(sys.argv[1], sys.argv[2])


if __name__ == "__main__":
    main()
