"""As regras de pontuacao tem que CHEGAR no prompt.

Ate 2026-09-02 `rubric` e `type_guidance` eram montados no `_evaluate` e nunca
injetados na f-string do prompt: so o `context_block` entrava. O coach avaliava
sem as regras que o proprio arquivo define, e ninguem via, porque o unico sinal
era um F841 do ruff dentro dos 73 erros que derrubavam o CI antes do pytest.

Estes testes travam a ligacao. Nao julgam o conteudo da rubrica, so que ela
chega ao modelo.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "call-recorder"))

import coach  # noqa: E402
import coach_llm  # noqa: E402

TRANSCRIPT = (
    "[001.0s] Kelvin: so the export policy needs a decision this week\n"
    "[012.0s] Interlocutor: agreed, I will check with the data owners\n"
    "[025.0s] Kelvin: we should align the baseline before the steering committee\n"
)


def _captura_prompt(monkeypatch, topic_type=""):
    """Roda _evaluate sem chamar LLM nenhum e devolve o prompt montado."""
    visto = {}

    def _fake(prompt, **kwargs):
        visto["prompt"] = prompt
        return {"scores": {"grammar": 8, "vocabulary": 8, "fluency": 8,
                           "structure": 8, "register": 8},
                "overall": 8, "level": "C1", "level_confidence": "medium",
                "summary": "ok", "errors": [], "refinements": [],
                "strengths": [], "improvement_tips": [],
                "vocabulary_suggestions": []}

    monkeypatch.setattr(coach_llm, "generate_json", _fake)
    coach._evaluate(TRANSCRIPT, "export policy", topic_type)
    return visto["prompt"]


def test_regras_de_pontuacao_chegam_no_prompt(monkeypatch):
    prompt = _captura_prompt(monkeypatch)
    assert "SCORING RULES (apply strictly before grading)" in prompt
    # uma linha de cada dimensao, para o bloco nao entrar pela metade
    assert "Grammar: evaluate patterns only" in prompt
    assert "Register: most reliable score" in prompt


def test_guia_do_tipo_de_call_chega_no_prompt(monkeypatch):
    prompt = _captura_prompt(monkeypatch, topic_type="meeting")
    assert "RECORDING TYPE (meeting)" in prompt
    assert "short reactive turns are normal" in prompt


def test_tipo_desconhecido_nao_deixa_cabecalho_orfao(monkeypatch):
    prompt = _captura_prompt(monkeypatch, topic_type="nao-existe")
    assert "RECORDING TYPE" not in prompt
    # a rubrica geral continua valendo mesmo sem guia de tipo
    assert "SCORING RULES (apply strictly before grading)" in prompt
