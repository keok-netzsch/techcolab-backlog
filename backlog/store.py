"""
backlog/store.py — Reads and writes Idea objects as Markdown files with YAML frontmatter.

File format per idea:
---
id: idea-001
titulo: "Nome da ideia"
status: backlog
prioridade: média
area: ""
origem: "notes/arquivo.md"
criado_em: 2025-01-01
atualizado_em: 2025-01-01
due_date: ""
---

## Descrição
...

## To-dos
- [ ] Task 1
- [x] Task 2 @2026-06-01

## Notas
...
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import yaml

from backlog.schema import Idea

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
# Markers: [ ] = open, [>] = in progress, [x] = done
# Optional suffixes (in order): @YYYY-MM-DD (due), ~YYYY-MM-DD (completed_at), {auto} (agent-authorised)
_TODO_RE = re.compile(
    r"^- \[(x|>| )\] (.+?)(?:\s+@(\d{4}-\d{2}-\d{2}))?(?:\s+~(\d{4}-\d{2}-\d{2}))?(?:\s+(\{auto\}))?(?:\s+(\{bug\}))?$",
    re.MULTILINE,
)


def _parse_todos(text: str) -> list[dict]:
    results = []
    for m in _TODO_RE.finditer(text):
        marker = m.group(1)
        results.append({
            "done": marker == "x",
            "in_progress": marker == ">",
            "text": m.group(2).strip(),
            "due_date": m.group(3),
            "completed_at": m.group(4),
            "agente_autorizado": m.group(5) is not None,
            "is_bug": m.group(6) is not None,
        })
    return results


def _render_todos(todos: list[dict]) -> str:
    lines = []
    for t in todos:
        if t.get("done"):
            mark = "x"
        elif t.get("in_progress"):
            mark = ">"
        else:
            mark = " "
        line = f"- [{mark}] {t['text']}"
        if t.get("due_date"):
            line += f" @{t['due_date']}"
        if t.get("completed_at"):
            line += f" ~{t['completed_at']}"
        if t.get("agente_autorizado"):
            line += " {auto}"
        if t.get("is_bug"):
            line += " {bug}"
        lines.append(line)
    return "\n".join(lines)


def _extract_section(body: str, heading: str) -> str | None:
    """Extract content under a ## heading until the next ## or end of string."""
    pattern = re.compile(
        rf"^## {re.escape(heading)}\n(.*?)(?=^## |\Z)", re.MULTILINE | re.DOTALL
    )
    m = pattern.search(body)
    return m.group(1).strip() if m else None


def _parse_date(val) -> date | None:
    if isinstance(val, date):
        return val
    if isinstance(val, str) and val.strip():
        try:
            return date.fromisoformat(val.strip())
        except ValueError:
            pass
    return None


class BacklogStore:
    def __init__(self, directory: Path):
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, idea_id: str) -> Path:
        return self.dir / f"{idea_id}.md"

    def _next_id(self) -> str:
        existing = sorted(self.dir.glob("idea-*.md"))
        if not existing:
            return "idea-001"
        last = existing[-1].stem  # "idea-042"
        num = int(last.split("-")[1]) + 1
        return f"idea-{num:03d}"

    def save(self, idea: Idea) -> Path:
        idea.updated_at = date.today()
        # Auto-advance: if any todo is active/done and idea is still in backlog, move forward
        _STATUS_RANK = {"backlog": 0, "em desenvolvimento": 1, "em validação": 2, "concluído": 3, "arquivado": 4}
        if _STATUS_RANK.get(idea.status, 99) == 0 and any(
            t.get("in_progress") or t.get("done") for t in idea.todos
        ):
            idea.status = "em desenvolvimento"
        fm = yaml.dump(idea.to_frontmatter(), allow_unicode=True, default_flow_style=False).strip()

        todos_block = _render_todos(idea.todos) if idea.todos else "_nenhum_"
        body = f"---\n{fm}\n---\n\n"
        body += f"## Descricao\n{idea.description or '_sem descricao_'}\n\n"
        body += f"## To-dos\n{todos_block}\n\n"
        body += f"## Notas\n{idea.notes or '_sem notas_'}\n\n"
        body += f"## Claude Tips\n{idea.claude_tips or ''}\n"

        path = self._path(idea.id)
        path.write_text(body, encoding="utf-8")
        return path

    def load(self, path: Path) -> Idea | None:
        text = path.read_text(encoding="utf-8")
        fm_match = _FRONTMATTER_RE.match(text)
        if not fm_match:
            return None

        fm = yaml.safe_load(fm_match.group(1))
        body = text[fm_match.end():]

        # Support both "Descrição" (old) and "Descricao" (new ASCII-safe heading)
        description = _extract_section(body, "Descricao") or _extract_section(body, "Descrição")
        notes = _extract_section(body, "Notas")
        todos_raw = _extract_section(body, "To-dos") or ""
        todos = _parse_todos(todos_raw)
        claude_tips = _extract_section(body, "Claude Tips")

        return Idea(
            id=fm.get("id", path.stem),
            title=fm.get("titulo", ""),
            status=fm.get("status", "backlog"),
            priority=fm.get("prioridade", "média"),
            area=fm.get("area") or None,
            origin=fm.get("origem") or None,
            created_at=_parse_date(fm.get("criado_em")) or date.today(),
            updated_at=_parse_date(fm.get("atualizado_em")) or date.today(),
            due_date=_parse_date(fm.get("due_date")),
            impacto=fm.get("impacto") or None,
            esforco=fm.get("esforco") or None,
            description=description,
            todos=todos,
            notes=notes,
            claude_tips=claude_tips or None,
            agente_autorizado=bool(fm.get("agente_autorizado", False)),
            is_bug=bool(fm.get("is_bug", False)),
        )

    def load_by_id(self, idea_id: str) -> Idea | None:
        path = self._path(idea_id)
        if not path.exists():
            return None
        return self.load(path)

    def load_all(self) -> list[Idea]:
        ideas = []
        for p in sorted(self.dir.glob("idea-*.md")):
            idea = self.load(p)
            if idea:
                ideas.append(idea)
        return ideas

    def create(self, **kwargs) -> Idea:
        idea_id = kwargs.pop("id", self._next_id())
        idea = Idea(id=idea_id, **kwargs)
        self.save(idea)
        return idea
