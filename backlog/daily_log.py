"""
backlog/daily_log.py — Appends timestamped entries to a daily log in the vault.

Log file: <vault>/backlog/diario-YYYY-MM-DD.md
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from config import VAULT_ROOT

_ACTION_LABEL = {
    "criada": "CRIADA",
    "alterada": "ALTERADA",
    "concluida": "CONCLUÍDA",
    "todo_concluido": "TO-DO",
}


def _log_path(today: date | None = None) -> Path:
    d = today or date.today()
    log_dir = Path(VAULT_ROOT) / "Log"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / f"diario-{d.isoformat()}.md"


def log_entry(action: str, idea, detail: str = "") -> None:
    """
    Append one timestamped entry to today's log.

    action  : "criada" | "alterada" | "concluida" | "todo_concluido"
    idea    : Idea object
    detail  : optional context string
    """
    path = _log_path()

    if not path.exists():
        today = date.today()
        header = (
            f"---\ndate: {today.isoformat()}\ntype: daily-log\n---\n\n"
            f"# Log do dia — {today.strftime('%d/%m/%Y')}\n\n"
        )
        path.write_text(header, encoding="utf-8")

    now = datetime.now().strftime("%H:%M")
    label = _ACTION_LABEL.get(action, action.upper())

    line = f"- {now} `{label}` [{idea.id}] {idea.title}"
    if detail:
        line += f" — {detail}"
    line += "\n"

    with path.open("a", encoding="utf-8") as f:
        f.write(line)
