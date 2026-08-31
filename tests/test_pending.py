"""Ledger de pendencias (agent/pending.py) - registro unico do que espera o Kelvin."""

import importlib
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _mod(tmp_path, monkeypatch):
    import agent.pending as pending
    importlib.reload(pending)
    monkeypatch.setattr(pending, "STORE", tmp_path / "pendencias.json")
    monkeypatch.setattr(pending, "VIEW", tmp_path / "Pendencias.md")
    return pending


def test_add_list_resolve_roundtrip(tmp_path, monkeypatch):
    p = _mod(tmp_path, monkeypatch)
    assert p.main(["add", "--tipo", "decisao", "--texto", "Aprovar rascunho W35",
                   "--origem", "TMA handoff"]) == 0
    assert p.main(["add", "--tipo", "graduacao", "--texto", "Nota X para o central"]) == 0
    data = json.loads((tmp_path / "pendencias.json").read_text(encoding="utf-8"))
    assert [i["id"] for i in data["itens"]] == ["P-001", "P-002"]

    assert p.main(["resolve", "P-001", "--como", "aprovado em conversa"]) == 0
    data = json.loads((tmp_path / "pendencias.json").read_text(encoding="utf-8"))
    assert data["itens"][0]["resolucao"] == "aprovado em conversa"
    assert data["itens"][0]["resolvida_em"]


def test_view_mostra_abertas_e_historico(tmp_path, monkeypatch):
    # A dor original tem duas metades: "o que esta na lista" E "o que ja foi
    # resolvido para eu consultar". A visao precisa das duas secoes.
    p = _mod(tmp_path, monkeypatch)
    p.main(["add", "--tipo", "decisao", "--texto", "Aberta ainda"])
    p.main(["add", "--tipo", "verificacao", "--texto", "Ja fechada"])
    p.main(["resolve", "P-002", "--como", "conferido no app"])
    md = (tmp_path / "Pendencias.md").read_text(encoding="utf-8")
    assert "## Abertas (1)" in md and "Aberta ainda" in md
    assert "## Resolvidas (1)" in md and "conferido no app" in md


def test_dedup_por_texto_entre_sessoes(tmp_path, monkeypatch):
    # O cenario que motivou o ledger: duas sessoes registram a mesma pendencia.
    # Nao pode virar duas linhas para o Kelvin fechar.
    p = _mod(tmp_path, monkeypatch)
    assert p.main(["add", "--tipo", "decisao", "--texto", "Reter audio por 7 dias?"]) == 0
    assert p.main(["add", "--tipo", "decisao", "--texto", "reter  audio por 7 DIAS?"]) == 2
    data = json.loads((tmp_path / "pendencias.json").read_text(encoding="utf-8"))
    assert len(data["itens"]) == 1


def test_resolvida_pode_ser_reaberta_como_nova(tmp_path, monkeypatch):
    # Dedup vale so contra ABERTAS: pendencia resolvida que volta e um fato novo.
    p = _mod(tmp_path, monkeypatch)
    p.main(["add", "--tipo", "decisao", "--texto", "Mesma coisa"])
    p.main(["resolve", "P-001"])
    assert p.main(["add", "--tipo", "decisao", "--texto", "Mesma coisa"]) == 0


def test_tipo_invalido_recusado(tmp_path, monkeypatch):
    p = _mod(tmp_path, monkeypatch)
    assert p.main(["add", "--tipo", "tarefa", "--texto", "x"]) == 1
    assert not (tmp_path / "pendencias.json").exists()


def test_resolve_id_inexistente_e_dupla_resolucao(tmp_path, monkeypatch):
    p = _mod(tmp_path, monkeypatch)
    assert p.main(["resolve", "P-999"]) == 1
    p.main(["add", "--tipo", "decisao", "--texto", "y"])
    p.main(["resolve", "P-001"])
    assert p.main(["resolve", "P-001"]) == 2
