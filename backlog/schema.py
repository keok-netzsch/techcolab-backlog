"""
backlog/schema.py — Idea dataclass and valid enum values.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


VALID_IMPACTS = ["alta", "média", "baixa"]
VALID_EFFORTS = ["alto", "médio", "baixo"]
VALID_AREAS = [
    "produto",
    "dados",
    "automação",
    "desenvolvimento",
    "gestão",
    "comunicação",
    "governança",
    "planejamento",
    "negócio",
    "infraestrutura",
    "IA",
]

VALID_STATUSES = [
    "backlog",
    "em análise",
    "análise - aprovado",
    "análise - rejeitado",
    "aguardando desenvolvimento",
    "em desenvolvimento",
    "em validação",
    "concluído",
    "descartado",
]

VALID_PRIORITIES = ["alta", "média", "baixa"]


@dataclass
class Idea:
    id: str                              # e.g. "idea-001"
    title: str
    status: str = "backlog"
    priority: str = "média"
    area: Optional[str] = None
    origin: Optional[str] = None         # relative path of source note
    created_at: date = field(default_factory=date.today)
    updated_at: date = field(default_factory=date.today)
    due_date: Optional[date] = None
    impacto: Optional[str] = None
    esforco: Optional[str] = None
    description: Optional[str] = None
    todos: list[dict] = field(default_factory=list)  # [{"text": str, "done": bool, "due_date": Optional[str]}]
    notes: Optional[str] = None          # free-form observations
    claude_tips: Optional[str] = None    # markdown bullets generated via Ollama
    agente_autorizado: bool = False      # pre-approves todos in the daily report

    def to_frontmatter(self) -> dict:
        return {
            "id": self.id,
            "titulo": self.title,
            "status": self.status,
            "prioridade": self.priority,
            "area": self.area or "",
            "origem": self.origin or "",
            "criado_em": str(self.created_at),
            "atualizado_em": str(self.updated_at),
            "due_date": str(self.due_date) if self.due_date else "",
            "impacto": self.impacto or "",
            "esforco": self.esforco or "",
            "agente_autorizado": self.agente_autorizado,
        }
