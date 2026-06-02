import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from datetime import date

from backlog.store import BacklogStore
from config import BACKLOG_DIR

store = BacklogStore(Path(BACKLOG_DIR))
idea = store.load_by_id("idea-009")

implemented = [
    "Edicao de titulo",
    "Busca full-text",
    "Alertas de vencimento",
    "Botao Recarregar vault",
    "Exclusao de ideias pela interface",
    "Scoring de ideias",
    "Report de periodo",
    "Dashboard de metricas",
    "Deteccao de duplicatas",
    "Sugestao de prioridade",
    "Re-extracao",
    "Historico de alteracoes",
    "Kanban visual",
    "Bulk status update",
    "Legenda de icones",
]
today = str(date.today())
changed = 0
for t in idea.todos:
    for kw in implemented:
        if kw.lower() in t["text"].lower():
            if not t["done"]:
                t["done"] = True
                t["due_date"] = today
                changed += 1

store.save(idea)
print(f"Marcados: {changed}")
for t in idea.todos:
    mark = "x" if t["done"] else " "
    print(f"  [{mark}] {t['text'][:80]}")
