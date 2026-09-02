"""Contrato de extracao (2026-08-31): compromissos e oportunidades das conversas.

A rotina das 09:00 extrai to-dos e oportunidades de cada transcricao roteada.
O que valida aqui nao e a extracao em si (e trabalho de leitura, humano+IA) -
e que as INSTRUCOES que a listagem do route.py carrega apontam para sintaxes
que os consumidores de verdade aceitam:

- a linha de compromisso tem que casar com os regexes do process.py dashboard
  (senao o monitor das 08:45 nunca ve o item - invisivel, nao errado);
- o status de oportunidade tem que existir no schema do backlog (senao o
  create_idea recusa e a oportunidade se perde no meio da rotina).

Instrucao que ensina sintaxe que ninguem parseia e pior que instrucao nenhuma.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "call-recorder"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import process  # noqa: E402
import route  # noqa: E402

from backlog.schema import VALID_STATUSES  # noqa: E402

# A linha-exemplo que o contrato ensina, escrita por extenso.
EXEMPLO = "- [ ] (Ana Leite) revisar politica de export @2026-09-05"


def test_linha_exemplo_casa_com_o_dashboard():
    m = process._TASK_RE.match(EXEMPLO)
    assert m, "a sintaxe ensinada pelo contrato nem entra no coletor"
    body = m.group(1)
    om = process._OWNER_RE.match(body)
    assert om and om.group("owner") == "Ana Leite"
    dm = process._DUE_RE.search(body)
    assert dm and dm.group(1) == "2026-09-05"


def test_linha_sem_dono_e_sem_data_e_invisivel_de_proposito():
    # O contrato avisa isso explicitamente; se o filtro do dashboard mudar,
    # o aviso vira mentira e este teste cobra a atualizacao.
    body = process._TASK_RE.match("- [ ] linha solta de checklist").group(1)
    assert process._OWNER_RE.match(body) is None
    assert process._DUE_RE.search(body) is None


def test_status_de_curadoria_existe_no_schema():
    assert "em análise" in VALID_STATUSES


def test_contrato_viaja_na_listagem_do_route():
    # O texto tem que ensinar as tres partes: sintaxe do compromisso, status
    # de curadoria e a ordem de cruzar antes de criar.
    c = route.EXTRACT_CONTRACT
    assert "- [ ] (Dono)" in c and "@YYYY-MM-DD" in c
    assert "em analise" in c
    assert "Action-Dashboard" in c


def test_contrato_ensina_a_mesma_sintaxe_que_o_exemplo_valida():
    # O EXEMPLO acima e a versao concreta do gabarito do contrato. Se um dos
    # dois mudar sozinho, este teste denuncia a divergencia.
    assert "'- [ ] (Dono) texto @YYYY-MM-DD'" in route.EXTRACT_CONTRACT
