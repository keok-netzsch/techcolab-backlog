"""
agent/weekly_brief.py — the decision loop of Toolkit 2.0 (idea-066).

Replaces the daily report's "Proposed actions" checkbox list, which over 86
reports produced 1,986 checkboxes and collected 32 approvals (1.6%, none in
the final two weeks). The failure was the mechanism, not the analysis: it
asked Kelvin to open a file, tick boxes, and wait for the next cycle.

This brief instead:
  - surfaces at most MAX_ITEMS decisions per week, never an inventory;
  - phrases each one as a question with two concrete options;
  - is answered in conversation ("descarta A, reativa C"), which the caller
    turns into `update_status.py` / MCP calls.

It is generated on the first run of each ISO week — not tied to Monday, so a
week that starts on a holiday still gets its brief on the first day Kelvin's
machine runs the agent. Re-running the same week is a no-op unless --force.

Usage:
    python agent/weekly_brief.py [--force] [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from agent.agent_io import force_utf8_stdio, safe_print
from backlog.store import BacklogStore
from config import BACKLOG_DIR, VAULT_ROOT

force_utf8_stdio()

BRIEFS_DIR = VAULT_ROOT / "weekly-briefs"
MAX_ITEMS = 5
STALE_DAYS = 14  # matches daily_report.STALE_DAYS
CLOSED = {"concluído", "descartado", "análise - rejeitado"}

# Labels are English per the repo-wide UI rule; idea titles stay as written.
STATUS_LABEL = {
    "backlog": "Backlog",
    "em análise": "Under review",
    "análise - aprovado": "Approved",
    "análise - rejeitado": "Rejected",
    "aguardando desenvolvimento": "Waiting",
    "em desenvolvimento": "In development",
    "em validação": "In validation",
    "concluído": "Done",
    "descartado": "Discarded",
}


# ── Week helpers ──────────────────────────────────────────────────────────────

def week_id(d: date | None = None) -> str:
    """ISO week label, e.g. '2026-W35'."""
    d = d or date.today()
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def brief_path(d: date | None = None) -> Path:
    return BRIEFS_DIR / f"brief-{week_id(d)}.md"


def _days_since_update(idea) -> int:
    raw = getattr(idea, "updated_at", None) or getattr(idea, "created_at", None)
    if not raw:
        return 0
    try:
        s = str(raw)[:10]
        return (date.today() - datetime.strptime(s, "%Y-%m-%d").date()).days
    except (ValueError, TypeError):
        return 0


# ── Item collection ───────────────────────────────────────────────────────────

def collect_decisions(ideas: list, limit: int | None = MAX_ITEMS) -> list[dict]:
    """Build the ranked list of decisions worth Kelvin's attention.

    Ranked by how costly silence is: something overdue or broken outranks
    something merely idle. Returns at most `limit` items (None = no cap,
    used to count how many were truncated).
    """
    active = [i for i in ideas if i.status not in CLOSED]
    today = date.today()
    items: list[dict] = []

    # 1. Open bugs — a known defect nobody scheduled
    for i in active:
        if getattr(i, "is_bug", False):
            items.append({
                "rank": 0,
                "id": i.id,
                "title": i.title,
                "why": f"open bug, sitting in {STATUS_LABEL.get(i.status, i.status)}",
                "question": "fix this week, or drop it from the backlog?",
                "options": ("fix", "drop"),
            })

    # 2. Overdue — a date Kelvin set and passed
    for i in active:
        if i.due_date and str(i.due_date) < today.isoformat():
            days = (today - datetime.strptime(str(i.due_date)[:10], "%Y-%m-%d").date()).days
            items.append({
                "rank": 1,
                "id": i.id,
                "title": i.title,
                "why": f"due {i.due_date}, {days} days past",
                "question": "new date, or drop the date and let it float?",
                "options": ("new date", "drop date"),
            })

    # 3. Stale — moving nowhere for two weeks or more
    for i in active:
        days = _days_since_update(i)
        if days >= STALE_DAYS:
            items.append({
                "rank": 2 if days < 60 else 1,  # very old outranks merely stale
                "id": i.id,
                "title": i.title,
                "why": f"untouched for {days} days, still {STATUS_LABEL.get(i.status, i.status)}",
                "question": "discard it, or commit to a next step?",
                "options": ("discard", "reactivate"),
            })

    # Deduplicate: one line per idea, keeping its most urgent reason
    seen: dict[str, dict] = {}
    for it in items:
        cur = seen.get(it["id"])
        if cur is None or it["rank"] < cur["rank"]:
            seen[it["id"]] = it

    ordered = sorted(seen.values(), key=lambda x: (x["rank"], x["id"]))
    return ordered if limit is None else ordered[:limit]


# ── Rendering ─────────────────────────────────────────────────────────────────

def build_brief(decisions: list[dict], total_active: int, dropped: int = 0) -> str:
    wid = week_id()
    letters = "ABCDE"
    lines = [
        "---",
        f"date: {date.today().isoformat()}",
        f"week: {wid}",
        "type: session",
        "tags: [agent, weekly-brief]",
        "ai-first: true",
        "---",
        "",
        f"> **For future Claude:** Weekly decision brief for {wid}. Each item is a "
        "question for Kelvin, answered in conversation — never a task to execute on "
        "your own. When he answers (e.g. \"discard A, reactivate C\"), apply it with "
        "`python agent/update_status.py <idea_id> \"<status>\"` or the "
        "`techcolab-vault` MCP tools, then say what you changed.",
        "",
        f"# Weekly Brief — {wid}",
        "",
    ]

    if not decisions:
        lines += [
            "Nothing needs a decision this week — no open bugs, nothing overdue, "
            f"nothing stale. {total_active} active items, all moving.",
            "",
        ]
        return "\n".join(lines)

    lines += [
        f"{len(decisions)} decision(s). Answer by letter — \"discard A, reactivate C\".",
        "",
    ]

    for n, d in enumerate(decisions):
        letter = letters[n] if n < len(letters) else str(n + 1)
        opt_a, opt_b = d["options"]
        lines += [
            f"### {letter}. `{d['id']}` — {d['title']}",
            "",
            f"- **Why it's here:** {d['why']}",
            f"- **Decision:** {d['question']}  _({opt_a} / {opt_b})_",
            "",
        ]

    if dropped:
        lines += [
            f"> {dropped} further item(s) would qualify but were not listed — this brief "
            f"caps at {MAX_ITEMS} so it stays answerable. They return next week if still open.",
            "",
        ]

    lines += [
        "---",
        f"*{total_active} active backlog items. Generated {date.today().isoformat()}.*",
    ]
    return "\n".join(lines)


# ── Entry point ───────────────────────────────────────────────────────────────

def generate(force: bool = False, dry_run: bool = False) -> tuple[bool, Path]:
    """Write this week's brief. Returns (written, path)."""
    path = brief_path()
    if path.exists() and not force:
        return False, path

    store = BacklogStore(BACKLOG_DIR)
    ideas = store.load_all()

    shown = collect_decisions(ideas, limit=MAX_ITEMS)
    # No silent truncation: say how many qualified but did not fit.
    dropped = max(0, len(collect_decisions(ideas, limit=None)) - len(shown))
    active = len([i for i in ideas if i.status not in CLOSED])

    text = build_brief(shown, active, dropped)

    if dry_run:
        safe_print(text)
        return False, path

    BRIEFS_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True, path


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate the weekly decision brief.")
    ap.add_argument("--force", action="store_true", help="Regenerate even if this week's brief exists.")
    ap.add_argument("--dry-run", action="store_true", help="Print the brief without writing it.")
    args = ap.parse_args()

    try:
        written, path = generate(force=args.force, dry_run=args.dry_run)
    except Exception as e:  # noqa: BLE001 — scheduled task must surface the reason
        safe_print(f"[brief] FAILED: {e}")
        return 1

    if args.dry_run:
        return 0
    if written:
        safe_print(f"[brief] Written: {path}")
    else:
        safe_print(f"[brief] Already exists for {week_id()}, skipping: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
