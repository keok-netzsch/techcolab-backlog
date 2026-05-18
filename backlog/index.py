"""
backlog/index.py — Generates _index.md as a Kanban-style overview of all ideas.
"""

from pathlib import Path
from datetime import date

from backlog.schema import Idea, VALID_STATUSES


def generate_index(ideas: list[Idea], output_path: Path) -> None:
    lines = [
        f"# Backlog de Ideias — TechColab D&A",
        f"_Atualizado em: {date.today()}_",
        f"_Total: {len(ideas)} ideias_",
        "",
    ]

    by_status: dict[str, list[Idea]] = {s: [] for s in VALID_STATUSES}
    for idea in ideas:
        bucket = by_status.get(idea.status, by_status["backlog"])
        bucket.append(idea)

    for status in VALID_STATUSES:
        group = by_status[status]
        lines.append(f"## {status.title()} ({len(group)})")
        if not group:
            lines.append("_nenhuma ideia_")
        else:
            for idea in group:
                priority_icon = {"alta": "🔴", "média": "🟡", "baixa": "🟢"}.get(idea.priority, "⚪")
                lines.append(f"- {priority_icon} [[{idea.id}]] — {idea.title}")
        lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
