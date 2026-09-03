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
import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _sonda_nao_vai_a_rede(monkeypatch):
    """`_context_summary` sonda o Ollama antes de gastar 300 s nele (2026-09-02).

    A sonda manda 3 palavras de verdade ao 11434. Dentro do teste isso e uma
    chamada de rede real: na maquina do Kelvin, com 528 MB livres, ela recusava e
    o teste passava a medir a RAM da maquina em vez do codigo. Aqui a sonda sempre
    libera; o caso do "nao pode servir" tem teste proprio, mais abaixo.
    """
    monkeypatch.setattr(coach, "_ollama_pode_servir", lambda *a, **k: (True, ""))

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


def test_sonda_recusando_pula_o_modelo_e_diz_por_que(monkeypatch, capsys):
    """Sem a sonda a chamada pendura 300 s. Com ela o relatorio sai na hora — e
    diz no corpo que faltou memoria, nao que a call era vazia. Voltar isso para
    string vazia esconderia a lacuna de quem le o arquivo semanas depois."""
    monkeypatch.setattr(coach, "_ollama_pode_servir",
                        lambda *a, **k: (False, "512 MB de RAM livre"))
    monkeypatch.setattr(coach_llm, "generate",
                        lambda *a, **k: (_ for _ in ()).throw(
                            AssertionError("nao devia nem tentar")))
    out = coach._context_summary(DUAL)
    assert "nao coube na memoria" in out
    assert "512 MB de RAM livre" in out
    assert "contexto pulado" in capsys.readouterr().out


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
