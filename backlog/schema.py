"""
backlog/schema.py — Idea dataclass and valid enum values.
"""

from dataclasses import dataclass, field
from datetime import date

VALID_IMPACTS = ["alta", "média", "baixa"]
VALID_EFFORTS = ["alto", "médio", "baixo"]
VALID_AREAS = [
    "produto",
    "dados & IA",
    "automação",
    "gestão",
    "governança",
    "infraestrutura",
    "comunicação",
    "business",
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
    area: str | None = None
    origin: str | None = None         # relative path of source note
    created_at: date = field(default_factory=date.today)
    updated_at: date = field(default_factory=date.today)
    due_date: date | None = None
    impacto: str | None = None
    esforco: str | None = None
    description: str | None = None
    todos: list[dict] = field(default_factory=list)  # [{"text": str, "done": bool, "due_date": Optional[str]}]
    notes: str | None = None          # free-form observations
    claude_tips: str | None = None    # markdown bullets generated via Ollama
    agente_autorizado: bool = False      # pre-approves todos in the daily report
    is_bug: bool = False                 # marks this idea as a bug/issue

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
            "is_bug": self.is_bug,
        }
