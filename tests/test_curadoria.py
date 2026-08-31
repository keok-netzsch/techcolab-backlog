"""Fatia acionavel do backlog (agent/curadoria.py).

"Quero ver tudo do backlog assim, mas tambem nao quero que seja poluido" — as
duas metades brigam, e o que as concilia e o TETO com truncagem reportada. Lista
que corta em silencio faz o teto virar mentira.
"""

import os
import sys
from datetime import date, timedelta
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent import curadoria  # noqa: E402


def _idea(id_, status="backlog", title=None, due=None, dias_parada=0, bug=False):
    return SimpleNamespace(
        id=id_, title=title or f"Ideia {id_}", status=status,
        due_date=due, is_bug=bug,
        updated_at=(date.today() - timedelta(days=dias_parada)).isoformat(),
    )


def test_curadoria_vem_primeiro():
    """'em analise' e o unico grupo literalmente parado esperando ele."""
    linhas = curadoria.coletar([
        _idea("idea-001", due=(date.today() - timedelta(days=3)).isoformat()),
        _idea("idea-002", status="em análise"),
    ])
    assert linhas[0]["id"] == "idea-002"
    assert linhas[0]["grupo"] == "curadoria"


def test_item_aparece_uma_vez_so():
    """Em analise E vencida continua sendo UMA linha para ele fechar."""
    i = _idea("idea-003", status="em análise",
              due=(date.today() - timedelta(days=9)).isoformat())
    linhas = curadoria.coletar([i])
    assert len([l for l in linhas if l["id"] == "idea-003"]) == 1


def test_teto_corta_mas_avisa_quanto_ficou_de_fora():
    ideas = [_idea(f"idea-{n:03d}", status="em análise") for n in range(20)]
    linhas = curadoria.coletar(ideas, limite=5)
    reais = [l for l in linhas if l["grupo"] != "_truncado"]
    trunc = [l for l in linhas if l["grupo"] == "_truncado"]
    assert len(reais) == 5
    assert trunc and "15" in trunc[0]["porque"], "truncagem tem que dizer quantos"


def test_sem_truncagem_nao_inventa_linha():
    linhas = curadoria.coletar([_idea("idea-001", status="em análise")], limite=5)
    assert all(l["grupo"] != "_truncado" for l in linhas)


def test_backlog_saudavel_devolve_lista_vazia():
    """Ideia ativa, no prazo e mexida ontem nao pede acao nenhuma — o painel tem
    que poder ficar vazio, senao vira ruido diario."""
    assert curadoria.coletar([_idea("idea-001", dias_parada=1)]) == []


def test_cada_linha_carrega_as_acoes_do_widget():
    linhas = curadoria.coletar([_idea("idea-001", status="em análise")])
    assert "aprovar" in linhas[0]["acoes"] and "rejeitar" in linhas[0]["acoes"]
