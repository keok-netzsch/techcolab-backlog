"""Resumo de contexto da call (P-012) — e a fronteira que ele NAO pode cruzar.

Kelvin autorizou "ampliar, a menos que haja algum risco ou problema". Ha: o
resumo precisa do transcript COMPLETO (com a fala do interlocutor) e hoje so a
fala dele deixa a maquina. `maybe_run_coach` dispara por IDIOMA, nunca por tipo
de call, e ha 1:1 do time na fila - um 1:1 em ingles mandaria fala de
PDI/carreira de outra pessoa para o gateway.

Por isso o resumo e gerado LOCALMENTE. Estes testes travam a fronteira.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "call-recorder"))

import coach  # noqa: E402
import coach_llm  # noqa: E402

DUAL = ("[001.0s] Kelvin: so the export policy needs a decision\n"
        "[012.0s] Interlocutor: my concern is the PDI of one person here\n")


def test_contexto_vai_para_o_ollama_e_nunca_para_o_gateway(monkeypatch):
    vistos = {}

    def fake(prompt, purpose="coach", **kw):
        vistos["purpose"] = purpose
        vistos["prompt"] = prompt
        return "Conversa sobre a politica de export; Kelvin conduziu a decisao."

    monkeypatch.setattr(coach_llm, "generate", fake)
    out = coach._context_summary(DUAL)

    assert "export" in out
    # purpose fora da allowlist => coach_llm.active_provider devolve "ollama"
    assert vistos["purpose"] == "transcript"
    assert vistos["purpose"] not in coach_llm.REMOTE_ALLOWED, (
        "o resumo usa a fala do interlocutor - o purpose TEM que ser um que a "
        "allowlist force para local")
    assert coach_llm.active_provider(vistos["purpose"]) == "ollama"


def test_o_prompt_do_contexto_ve_os_dois_lados(monkeypatch):
    vistos = {}
    monkeypatch.setattr(coach_llm, "generate",
                        lambda prompt, purpose="coach", **kw: vistos.setdefault("p", prompt) and "" or "ok")
    coach._context_summary(DUAL)
    assert "Interlocutor" in vistos["p"], "sem o outro lado nao ha contexto"


def test_falha_do_contexto_nao_derruba_o_relatorio(monkeypatch, capsys):
    def explode(*a, **k):
        raise RuntimeError("ollama fora do ar")
    monkeypatch.setattr(coach_llm, "generate", explode)
    assert coach._context_summary(DUAL) == ""
    assert "contexto nao gerado" in capsys.readouterr().out


def test_transcricao_vazia_nao_chama_modelo(monkeypatch):
    monkeypatch.setattr(coach_llm, "generate",
                        lambda *a, **k: (_ for _ in ()).throw(
                            AssertionError("nao devia chamar")))
    assert coach._context_summary("   ") == ""


def test_contexto_aparece_antes_da_avaliacao_na_nota():
    ev = {"overall": 8, "level": "C1", "summary": "Solid.", "scores": {},
          "errors": [], "improvement_tips": [], "strengths": [],
          "vocabulary_suggestions": []}
    from datetime import datetime
    md = coach._render_session(ev, "[0.0s] Kelvin: hi", "", datetime(2026, 8, 31),
                               contexto="Call sobre a politica de export.")
    assert "**Contexto da call:** Call sobre a politica de export." in md
    assert md.index("Contexto da call") < md.index("Solid."), \
        "o contexto tem que vir ANTES do veredito - e ele que da sentido ao resto"
