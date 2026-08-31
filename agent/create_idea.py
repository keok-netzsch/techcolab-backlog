"""
agent/create_idea.py — Create a backlog idea from the command line.

The counterpart to update_status.py: that one moves an existing item, this one
brings a new item into existence. Written for the "push, not pull" capture flow
(vault/backlog.md, 2026-08-19): ideas are born in a chat, not inside the app, so
any Claude Code session must be able to file one correctly without hand-writing
YAML frontmatter and getting the schema subtly wrong.

Runs identically under both CLI accounts (`claude`, Pro OAuth, and `claude-api`,
NETZSCH gateway): pure stdlib plus this repo's own store, no LLM call and no
auth-dependent behaviour. It also does not care about the caller's working
directory — paths resolve from __file__ and TECHCOLAB_VAULT — so a session
running inside the Obsidian vault can invoke it by absolute path.

Usage (flags):
    python agent/create_idea.py --title "Titulo da ideia" \
        --description "..." \
        --todo "Primeiro passo" --todo "Segundo passo @2026-09-01" \
        --area business --priority alta

Usage (JSON — preferred when the text has accents, quotes or line breaks):
    python agent/create_idea.py --json payload.json
    python agent/create_idea.py --json -        # reads stdin

Exit codes: 0 = created, 1 = validation error, 2 = duplicate title.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from backlog.schema import (
    VALID_AREAS,
    VALID_EFFORTS,
    VALID_IMPACTS,
    VALID_PRIORITIES,
    VALID_STATUSES,
)
from backlog.index import generate_index
from backlog.store import BacklogStore, _parse_todos
from config import BACKLOG_DIR, BACKLOG_INDEX

EXIT_INVALID = 1
EXIT_DUPLICATE = 2

_KNOWN_FIELDS = {
    "title", "description", "todos", "notes", "area", "priority", "status",
    "origin", "impacto", "esforco", "due_date", "okr_ref", "sprint",
    "is_bug", "agente_autorizado", "blocked_by", "id",
}


class ValidationError(ValueError):
    """Raised when the caller's payload does not satisfy the backlog schema."""


# -- Field normalisation ------------------------------------------------------

def _require_single_line(value: str, field: str) -> str:
    if "\n" in value or "\r" in value:
        raise ValidationError(f"{field} must be a single line (no line breaks)")
    return value.strip()


def _check_enum(value, field: str, allowed: list[str]):
    """Return the value unchanged if valid; None/empty passes through as None."""
    if value is None or value == "":
        return None
    if value not in allowed:
        raise ValidationError(
            f"invalid {field}: {value!r}. Valid values: {', '.join(allowed)}"
        )
    return value


def _check_date(value, field: str) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError:
        raise ValidationError(f"invalid {field}: {value!r}. Expected YYYY-MM-DD")


def _parse_todo_line(raw: str) -> dict:
    """
    Turn one caller-supplied to-do string into a store-shaped dict.

    Parsing goes through the store's own _parse_todos so the accepted grammar
    can never drift from what the store writes back out: optional @YYYY-MM-DD
    (due), ~YYYY-MM-DD (completed), {auto} and {bug} suffixes.
    """
    text = _require_single_line(str(raw), "todo")
    if not text:
        raise ValidationError("todo entries cannot be empty")
    parsed = _parse_todos(f"- [ ] {text}")
    if not parsed:
        raise ValidationError(f"could not parse todo: {raw!r}")
    return parsed[0]


def build_payload(raw: dict) -> dict:
    """
    Validate and normalise a raw payload into kwargs for BacklogStore.create().

    Both input modes (flags and --json) funnel through here, so there is exactly
    one definition of what a well-formed idea is.
    """
    unknown = set(raw) - _KNOWN_FIELDS
    if unknown:
        raise ValidationError(f"unknown field(s): {', '.join(sorted(unknown))}")

    title = _require_single_line(str(raw.get("title") or ""), "title")
    if not title:
        raise ValidationError("title is required")

    todos_raw = raw.get("todos") or []
    if isinstance(todos_raw, str):
        todos_raw = [todos_raw]
    todos = [_parse_todo_line(t) for t in todos_raw]

    blocked_by = raw.get("blocked_by") or []
    if isinstance(blocked_by, str):
        blocked_by = [blocked_by]

    payload = {
        "title": title,
        "description": raw.get("description") or None,
        "notes": raw.get("notes") or None,
        "todos": todos,
        "area": _check_enum(raw.get("area"), "area", VALID_AREAS),
        "priority": _check_enum(raw.get("priority"), "priority", VALID_PRIORITIES) or "média",
        "status": _check_enum(raw.get("status"), "status", VALID_STATUSES) or "backlog",
        "impacto": _check_enum(raw.get("impacto"), "impacto", VALID_IMPACTS),
        "esforco": _check_enum(raw.get("esforco"), "esforco", VALID_EFFORTS),
        "origin": raw.get("origin") or None,
        "okr_ref": raw.get("okr_ref") or None,
        "sprint": raw.get("sprint") or None,
        "is_bug": bool(raw.get("is_bug", False)),
        "agente_autorizado": bool(raw.get("agente_autorizado", False)),
        "blocked_by": [str(b).strip() for b in blocked_by if str(b).strip()],
    }

    due = _check_date(raw.get("due_date"), "due_date")
    if due:
        payload["due_date"] = due
    if raw.get("id"):
        payload["id"] = _require_single_line(str(raw["id"]), "id")
    return payload


# -- Duplicate guard ----------------------------------------------------------

def find_duplicate(store: BacklogStore, title: str):
    """Return an existing Idea with the same title (case/space-insensitive)."""
    needle = " ".join(title.split()).casefold()
    for idea in store.load_all():
        if " ".join((idea.title or "").split()).casefold() == needle:
            return idea
    return None


# -- Entry point --------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="create_idea.py",
        description="Create a backlog idea (idea-NNN.md) in the vault.",
    )
    p.add_argument("--json", dest="json_source",
                   help="Path to a JSON payload, or '-' to read stdin")
    p.add_argument("--title")
    p.add_argument("--description")
    p.add_argument("--notes")
    p.add_argument("--todo", action="append", dest="todos", default=None,
                   help="Repeatable. Supports @YYYY-MM-DD, {auto} and {bug} suffixes")
    p.add_argument("--area", choices=VALID_AREAS)
    p.add_argument("--priority", choices=VALID_PRIORITIES)
    p.add_argument("--status", choices=VALID_STATUSES)
    p.add_argument("--origin", help="Relative path of the source note in the vault")
    p.add_argument("--impacto", choices=VALID_IMPACTS)
    p.add_argument("--esforco", choices=VALID_EFFORTS)
    p.add_argument("--due-date", dest="due_date")
    p.add_argument("--okr-ref", dest="okr_ref")
    p.add_argument("--sprint")
    p.add_argument("--blocked-by", action="append", dest="blocked_by", default=None)
    p.add_argument("--bug", dest="is_bug", action="store_true")
    p.add_argument("--auto", dest="agente_autorizado", action="store_true",
                   help="Pre-approve this item's to-dos in the daily report")
    p.add_argument("--id", help="Force a specific id instead of the next free one")
    p.add_argument("--allow-duplicate", action="store_true",
                   help="Create even if an idea with the same title exists")
    p.add_argument("--dry-run", action="store_true",
                   help="Validate and print what would be written, without writing")
    return p


def _payload_from_args(args) -> dict:
    if args.json_source:
        text = (sys.stdin.read() if args.json_source == "-"
                else Path(args.json_source).read_text(encoding="utf-8"))
        try:
            raw = json.loads(text)
        except json.JSONDecodeError as e:
            raise ValidationError(f"invalid JSON payload: {e}")
        if not isinstance(raw, dict):
            raise ValidationError("JSON payload must be an object, not a list")
        return raw

    fields = ("title", "description", "notes", "todos", "area", "priority",
              "status", "origin", "impacto", "esforco", "due_date", "okr_ref",
              "sprint", "blocked_by", "id")
    raw = {f: getattr(args, f) for f in fields if getattr(args, f) is not None}
    if args.is_bug:
        raw["is_bug"] = True
    if args.agente_autorizado:
        raw["agente_autorizado"] = True
    return raw


def _force_utf8_output() -> None:
    """
    Print UTF-8 regardless of the console code page.

    The caller is another Claude Code session reading this stdout, and the
    Windows console defaults to cp850/cp1252 — without this, every accented
    title comes back mangled in the session's transcript even though the file
    on disk is written correctly.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def main(argv=None) -> int:
    _force_utf8_output()
    args = _build_parser().parse_args(argv)

    try:
        payload = build_payload(_payload_from_args(args))
    except ValidationError as e:
        print(f"[ERROR] {e}")
        return EXIT_INVALID

    store = BacklogStore(BACKLOG_DIR)

    if not args.allow_duplicate:
        existing = find_duplicate(store, payload["title"])
        if existing:
            print(f"[ERROR] An idea with this title already exists: {existing.id}")
            print("        Update it with agent/update_status.py, or pass "
                  "--allow-duplicate to create anyway.")
            return EXIT_DUPLICATE

    if args.dry_run:
        print(f"[DRY-RUN] Would create: {payload['title']}")
        for key, value in sorted(payload.items()):
            if key != "title" and value not in (None, [], False):
                print(f"          {key}: {value}")
        return 0

    idea = store.create(**payload)
    path = store._path(idea.id)
    # Same reason as in update_status.py: the app also refreshes the index, but
    # capture happens through this CLI and must not wait for the app to be opened.
    # Best-effort, never fatal.
    try:
        generate_index(store.load_all(), Path(BACKLOG_INDEX))
    except Exception as e:  # noqa: BLE001
        print(f"[WARN] _index.md not regenerated: {e}")
    print(f"[OK] {idea.id} created - status '{idea.status}', priority '{idea.priority}'")
    print(f"[OK] {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
