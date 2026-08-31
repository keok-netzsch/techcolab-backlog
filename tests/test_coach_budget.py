"""Orcamento de avaliacao do coach — decisao do Kelvin 31/08: "sim. cubra 100%".

O corte de 5.000 chars foi dimensionado para o qwen2.5-coder local de 7B. Com o
claude-sonnet-5 pelo gateway ele fazia 20 sessoes serem avaliadas parcialmente:
no Jour Fixe com o Alberto foram 24.339 chars de fala do Kelvin, ~20% avaliado.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "call-recorder"))

import coach  # noqa: E402


def test_call_longa_real_cabe_inteira_no_gateway(monkeypatch):
    import coach_llm
    monkeypatch.setattr(coach_llm, "active_provider", lambda p: "gateway")
    # tamanho real medido no Jour Fixe com o Alberto
    t = "\n".join(f"[{i}.0s] Kelvin: linha {i}" for i in range(900))
    assert len(t) > 24_000
    assert coach._sample_excerpt(t) == t, "call longa nao pode mais ser amostrada"


def test_fallback_local_continua_amostrando(monkeypatch):
    """Cair no Ollama com 120k chars trocaria degradacao por travamento."""
    import coach_llm
    monkeypatch.setattr(coach_llm, "active_provider", lambda p: "ollama")
    t = "x" * 30_000
    out = coach._sample_excerpt(t)
    assert len(out) < len(t)
    assert "[... middle of transcript ...]" in out


def test_orcamento_segue_o_provedor(monkeypatch):
    import coach_llm
    monkeypatch.setattr(coach_llm, "active_provider", lambda p: "gateway")
    assert coach._budget_chars() == 120_000
    monkeypatch.setattr(coach_llm, "active_provider", lambda p: "ollama")
    assert coach._budget_chars() == 5_000


def test_corte_avisa_em_vez_de_silenciar(monkeypatch, capsys):
    import coach_llm
    monkeypatch.setattr(coach_llm, "active_provider", lambda p: "ollama")
    coach._sample_excerpt("y" * 20_000)
    assert "AMOSTRA" in capsys.readouterr().out


def test_transcricao_curta_passa_inteira_em_qualquer_provedor(monkeypatch):
    import coach_llm
    for prov in ("gateway", "ollama"):
        monkeypatch.setattr(coach_llm, "active_provider", lambda p, _p=prov: _p)
        t = "[0.0s] Kelvin: short one"
        assert coach._sample_excerpt(t) == t
