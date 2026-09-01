"""
backlog/daily_log.py — Appends timestamped backlog entries to the vault's daily note.

Target: <vault>/Daily/YYYY-MM-DD.md, under the "## 🗂️ Backlog" section.

Until 2026-08-26 this wrote to <vault>/Log/diario-YYYY-MM-DD.md (its own file,
frontmatter `type: daily-log`). That parallel diary was retired in the Toolkit 2.0
review (idea-067): the vault's Daily/ note is the single canonical daily record,
and `daily-log` was already deprecated by the 2026-07-29 type-taxonomy ADR.
Historical diario files were archived under Log/archive/.

The MCP server (techcolab-vault-mcp/vault_io.py) mirrors this exact behaviour —
keep the two in sync when changing the format.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from config import VAULT_BASE, VAULT_ROOT

_ACTION_LABEL = {
    "criada": "CRIADA",
    "alterada": "ALTERADA",
    "concluida": "CONCLUÍDA",
    "todo_concluido": "TO-DO",
}

BACKLOG_SECTION = "## 🗂️ Backlog"


def _daily_note_path(today: date | None = None) -> Path:
    # VAULT_BASE, not VAULT_ROOT. In this repo's config.py VAULT_ROOT is the app's
    # working area (<vault>/App/Personal toolkit) and VAULT_BASE is the vault top.
    # Daily/ is a vault-root folder (CLAUDE.md says so explicitly, and the vault MCP
    # server resolves it that way), so VAULT_ROOT here was writing to a second,
    # unread <vault>/App/Personal toolkit/Daily/. That is why "diario unico" from
    # Toolkit 2.0 Pacote 2 never actually landed in the daily note.
    d = today or date.today()
    daily_dir = Path(VAULT_BASE) / "Daily"
    daily_dir.mkdir(parents=True, exist_ok=True)
    return daily_dir / f"{d.isoformat()}.md"


def _legacy_log_path(d: date) -> Path:
    """Retired location (pre-2026-08-26), still read so history survives.

    The 25 historical files were moved to Log/archive/ on 2026-08-26; the
    flat Log/ path is still checked first in case anything lands there.
    """
    log_dir = Path(VAULT_ROOT) / "Log"
    flat = log_dir / f"diario-{d.isoformat()}.md"
    if flat.exists():
        return flat
    return log_dir / "archive" / f"diario-{d.isoformat()}.md"


def read_log_lines(d: date) -> list[str]:
    """Return the backlog activity lines logged on `d`, from either location.

    Reads the Daily/ note's Backlog section first; falls back to the retired
    diario file. Single reader for every consumer (views, reports) so the
    two-location logic lives in exactly one place.
    """
    note = Path(VAULT_ROOT) / "Daily" / f"{d.isoformat()}.md"
    if note.exists():
        text = note.read_text(encoding="utf-8", errors="replace")
        if BACKLOG_SECTION in text:
            start = text.index(BACKLOG_SECTION) + len(BACKLOG_SECTION)
            nxt = text.find("\n## ", start)
            block = text[start:nxt if nxt != -1 else len(text)]
            return [ln.strip() for ln in block.splitlines() if ln.strip().startswith("- ")]

    legacy = _legacy_log_path(d)
    if legacy.exists():
        text = legacy.read_text(encoding="utf-8", errors="replace")
        return [ln.strip() for ln in text.splitlines() if ln.strip().startswith("- ")]

    return []


def _minimal_daily_note(d: date) -> str:
    """Skeleton compatible with the vault's daily-note template (type: daily).

    Only the essentials — the obsidian-daily flow fleshes out the other
    sections when Kelvin opens the day.
    """
    weekday = d.strftime("%A, %B %d, %Y")
    return (
        f"---\ndate: {d.isoformat()}\ntype: daily\ntags: [daily, log]\n"
        f"ai-first: true\n---\n\n"
        f"# {weekday}\n\n"
        f"{BACKLOG_SECTION}\n"
    )


def log_entry(action: str, idea, detail: str = "") -> None:
    """
    Append one timestamped entry to today's daily note, under "## 🗂️ Backlog".

    action  : "criada" | "alterada" | "concluida" | "todo_concluido"
    idea    : Idea object
    detail  : optional context string
    """
    today = date.today()
    path = _daily_note_path(today)

    now = datetime.now().strftime("%H:%M")
    label = _ACTION_LABEL.get(action, action.upper())
    line = f"- {now} `{label}` [{idea.id}] {idea.title}"
    if detail:
        line += f" — {detail}"

    if not path.exists():
        path.write_text(_minimal_daily_note(today) + line + "\n", encoding="utf-8")
        return

    text = path.read_text(encoding="utf-8")
    if BACKLOG_SECTION in text:
        # Insert at the end of the Backlog section (before the next "## " or EOF)
        start = text.index(BACKLOG_SECTION) + len(BACKLOG_SECTION)
        next_sec = text.find("\n## ", start)
        insert_at = next_sec if next_sec != -1 else len(text)
        block = text[start:insert_at].rstrip()
        new_block = f"{block}\n{line}" if block else f"\n{line}"
        # Keep the blank line that separates this section from the next one;
        # without it the following "## " header gets glued to the last entry.
        sep = "\n\n" if next_sec != -1 else "\n"
        text = text[:start] + new_block + sep + text[insert_at:].lstrip("\n")
    else:
        # Section missing from an existing note: append it at the end
        text = text.rstrip() + f"\n\n{BACKLOG_SECTION}\n{line}\n"

    path.write_text(text, encoding="utf-8")
