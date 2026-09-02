"""Fatia acionável do backlog — o que espera decisão do Kelvin, pronta para o widget.

Por que existe (pedido dele, 2026-08-31): *"Quero ver tudo do backlog assim, de
alguma forma, mas também não quero que seja poluído."*

As duas metades desse pedido brigam entre si, e a saída é não misturar objetos:

- **Pendências** (`pending.py`) têm que poder chegar a zero. São o que trava ele.
- **Backlog** são ~34 ideias que nunca zeram. É inventário, não fila.

Jogar as 34 no mesmo painel mata o painel — vira lista que ele para de ler, que é
exatamente o modo de falha dos 1.986 checkboxes do relatório antigo (32 aprovações,
1,6%). Então esta fatia mostra só o que **pede uma ação dele**, com teto:

1. Curadoria — ideia em `em análise`, o estágio que a extração de calls produz e
   que só ele resolve (aprovar/rejeitar).
2. Bug aberto, vencida, parada ≥14 dias — a seleção já existe e é reusada de
   `weekly_brief.collect_decisions`, ranqueada por quanto custa o silêncio.

Não reimplementa a seleção: se o critério de "parada" mudar lá, muda aqui junto.

Uso:
    python agent/curadoria.py            # listagem humana
    python agent/curadoria.py --json     # para o widget
    python agent/curadoria.py --limite 20
"""

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from agent.weekly_brief import collect_decisions  # noqa: E402

TETO_PADRAO = 12
CURADORIA = "em análise"


def _dias_parada(idea) -> int:
    try:
        d = str(getattr(idea, "updated_at", "") or "")[:10]
        return (date.today() - datetime.strptime(d, "%Y-%m-%d").date()).days
    except (ValueError, TypeError):
        return 0


def coletar(ideas: list, limite: int = TETO_PADRAO) -> list[dict]:
    """Curadoria primeiro, depois o ranking do weekly_brief."""
    linhas: list[dict] = []

    # 1. Curadoria — literalmente parada esperando ele decidir.
    for i in ideas:
        if (i.status or "").startswith("em an"):   # ASCII: ver nota em todo-body.ps1
            linhas.append({
                "id": i.id,
                "titulo": i.title,
                "grupo": "curadoria",
                "porque": "aguardando sua curadoria",
                "dias": _dias_parada(i),
                "acoes": ["aprovar", "rejeitar", "adiar"],
            })

    ja = {linha["id"] for linha in linhas}

    # 2. Bug / vencida / parada — seleção reusada, não reimplementada.
    for d in collect_decisions(ideas, limit=None):
        if d["id"] in ja:
            continue
        grupo = ("bug" if d["rank"] == 0 else
                 "vencida" if "due" in d["why"] else "parada")
        linhas.append({
            "id": d["id"],
            "titulo": d["title"],
            "grupo": grupo,
            "porque": d["why"],
            "dias": 0,
            "acoes": ["reativar", "descartar", "adiar"],
        })

    ordem = {"curadoria": 0, "bug": 1, "vencida": 2, "parada": 3}
    linhas.sort(key=lambda linha: (ordem.get(linha["grupo"], 9), linha["id"]))
    total = len(linhas)
    linhas = linhas[:limite]
    # Truncagem sempre reportada. Lista que corta em silêncio faz o teto virar
    # mentira: ele acha que viu tudo o que pedia ação.
    if total > limite:
        linhas.append({"id": "", "titulo": "", "grupo": "_truncado",
                       "porque": f"mais {total - limite} item(ns) fora do teto de {limite}",
                       "dias": 0, "acoes": []})
    return linhas


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Fatia acionável do backlog")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--limite", type=int, default=TETO_PADRAO)
    args = ap.parse_args(argv)

    from backlog.store import BacklogStore
    from config import BACKLOG_DIR
    linhas = coletar(BacklogStore(BACKLOG_DIR).load_all(), limite=args.limite)

    if args.json:
        print(json.dumps(linhas, ensure_ascii=False))
        return 0
    if not linhas:
        print("Backlog sem nada pedindo ação sua.")
        return 0
    for linha in linhas:
        if linha["grupo"] == "_truncado":
            print(f"    ... {linha['porque']}")
            continue
        print(f"[{linha['grupo']:9s}] {linha['id']}  {linha['titulo'][:58]:60s} {linha['porque']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
