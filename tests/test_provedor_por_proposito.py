"""Qual proposito pode sair da maquina, e qual nunca pode.

Ate 2026-09-02 o `process.py` chamava o Ollama direto, com `OLLAMA_URL` fixo no
topo do arquivo. O `CLAUDE.md` afirmava que "todo LLM passa pelo coach_llm.py" e
isso nunca foi verdade para ele: a allowlist governava o coach e mais nada, entao
a carga mais pesada da maquina - estruturar 1:1, stakeholder e agenda - nunca teve
escolha de provedor. Mudar `REMOTE_ALLOWED` nao movia um grama de trabalho.

Decisao do Kelvin em 2026-09-02 ("A parcial"): conteudo de time e de trabalho passa
a usar o gateway da NETZSCH; `note` e `capture` continuam locais.

O que estes testes travam e a FRONTEIRA, nao a conveniencia. Duas exclusoes que
parecem arbitrarias e nao sao:

  - `note` e `capture` sao o Inbox. Foi ali que caiu a fatia da call de 02/09 com
    o visto, o divorcio e a pensao do Kelvin, e a conversa com o RH sobre a ida
    para a Alemanha. O ADR 2026-08-31-sistema-de-estudo-mdm.md, decisao 4, diz:
    "conteudo da transicao nunca roda no gateway NETZSCH - a transicao nao e
    anunciada; o gateway e logado pelo empregador".
  - `transcript` e o purpose do resumo de contexto do coach, que dispara por
    IDIOMA e alcanca 1:1 do time. O 1:1 roteado usa `oneonone`, que e outro nome
    de proposito - reaproveitar `transcript` teria aberto aquela fronteira de lado.
"""
import sys
from pathlib import Path

CR = Path(__file__).resolve().parent.parent / "call-recorder"
sys.path.insert(0, str(CR))

import pytest  # noqa: E402

import coach_llm  # noqa: E402


PODEM_SAIR = ["coach", "coach-probe", "oneonone", "manager", "agenda"]
NUNCA_SAEM = ["note", "capture", "transcript", "diarize", "qualquer-coisa-nova"]


@pytest.mark.parametrize("purpose", PODEM_SAIR)
def test_proposito_de_trabalho_usa_gateway_quando_ha_chave(purpose, monkeypatch):
    monkeypatch.setenv("NETZSCH_LLM_API_KEY", "chave-de-teste")
    monkeypatch.delenv("COACH_LLM", raising=False)
    assert coach_llm.active_provider(purpose) == "gateway"


@pytest.mark.parametrize("purpose", NUNCA_SAEM)
def test_proposito_fora_da_allowlist_nunca_sai(purpose, monkeypatch):
    monkeypatch.setenv("NETZSCH_LLM_API_KEY", "chave-de-teste")
    monkeypatch.delenv("COACH_LLM", raising=False)
    assert coach_llm.active_provider(purpose) == "ollama"


def test_note_e_capture_estao_fora_por_causa_da_transicao():
    """Trava explicita: se alguem adicionar `note` ou `capture` a allowlist, este
    teste quebra e o ADR de 31/08 aparece no motivo."""
    assert "note" not in coach_llm.REMOTE_ALLOWED
    assert "capture" not in coach_llm.REMOTE_ALLOWED


def test_transcript_continua_local_para_o_resumo_do_coach():
    """`coach._context_summary` usa este purpose de proposito. Ver
    tests/test_coach_context.py."""
    assert "transcript" not in coach_llm.REMOTE_ALLOWED


def test_sem_chave_tudo_cai_para_local(monkeypatch):
    for nome in ("NETZSCH_LLM_API_KEY", "NETZSCH_GATEWAY_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(nome, raising=False)
    for purpose in PODEM_SAIR + NUNCA_SAEM:
        assert coach_llm.active_provider(purpose) == "ollama"


def test_variavel_de_ambiente_forca_local(monkeypatch):
    monkeypatch.setenv("NETZSCH_LLM_API_KEY", "chave-de-teste")
    monkeypatch.setenv("COACH_LLM", "ollama")
    for purpose in PODEM_SAIR:
        assert coach_llm.active_provider(purpose) == "ollama"


def test_generate_recusa_mesmo_se_o_provedor_for_forcado(monkeypatch):
    """Defesa em profundidade: se uma edicao futura fizer `active_provider`
    devolver gateway para um purpose proibido, `generate` ainda barra."""
    monkeypatch.setattr(coach_llm, "active_provider", lambda _p: "gateway")
    with pytest.raises(coach_llm.ProviderError):
        coach_llm.generate("x", purpose="note")


def test_process_usa_o_roteador_e_nao_o_ollama_direto():
    """A regressao que este teste impede: alguem trocar `_generate` de volta por
    `_ollama_generate` num dos sitios que hoje podem ir ao gateway."""
    fonte = (CR / "process.py").read_text(encoding="utf-8")
    for purpose in ("oneonone", "manager", "agenda"):
        assert f'purpose="{purpose}"' in fonte, purpose
    assert 'purpose="note"' in fonte
