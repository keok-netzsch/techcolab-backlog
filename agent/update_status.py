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

from backlog.schema import VALID_STATUSES
from backlog.store import BacklogStore
from config import BACKLOG_DIR


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
    store.save(idea)
    print(f"[OK] {idea_id}: '{old_status}' -> '{new_status}'")


def main():
    if len(sys.argv) != 3:
        print("Usage: python agent/update_status.py <idea_id> <new_status>")
        print(f"Valid statuses: {', '.join(VALID_STATUSES)}")
        sys.exit(1)

    update_status(sys.argv[1], sys.argv[2])


if __name__ == "__main__":
    main()
