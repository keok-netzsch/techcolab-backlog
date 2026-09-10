"""O consolidado semanal de ingles nunca pode sair da maquina.

`agent/english_coach.py` varre `Team/`, `Stakeholders/`, `Areas/English-Learning/`
e tambem `Inbox/`. O Inbox e a pasta que `note` e `capture` mantem local porque e
onde cai conteudo pessoal do Kelvin, e porque o gateway e logado pelo empregador
(ADR 2026-08-31-sistema-de-estudo-mdm.md, decisao 4).

Ate 2026-09-10 a garantia era acidental: o modulo falava com o Ollama por URL fixa,
entao nao existia caminho para o gateway. Isso nao e o mesmo que o caminho ser
RECUSADO — uma edicao futura trocando o provedor pareceria so uma mudanca de
infraestrutura. Estes testes existem para que essa edicao quebre aqui, no pytest.

Espelha tests/test_coach_context.py, que faz o mesmo pelo resumo de contexto.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "call-recorder"))

import coach_llm  # noqa: E402
from agent import english_coach  # noqa: E402


def test_o_proposito_do_semanal_nao_esta_na_allowlist():
    assert english_coach.COACH_PURPOSE not in coach_llm.REMOTE_ALLOWED


def test_o_proposito_resolve_para_ollama_mesmo_com_chave(monkeypatch):
    # Com a chave presente, `coach` iria ao gateway. Este nao pode ir.
    monkeypatch.setenv("NETZSCH_LLM_API_KEY", "sk-teste-nao-usada")
    monkeypatch.delenv("COACH_LLM", raising=False)
    assert coach_llm.active_provider("coach") == "gateway"
    assert coach_llm.active_provider(english_coach.COACH_PURPOSE) == "ollama"


def test_generate_recusa_o_gateway_mesmo_se_alguem_forcar(monkeypatch):
    # Defesa de dentro: nem forcando o provedor o proposito consegue sair.
    monkeypatch.setattr(coach_llm, "active_provider", lambda _p: "gateway")
    try:
        coach_llm.generate("x", purpose=english_coach.COACH_PURPOSE)
    except coach_llm.ProviderError:
        return
    raise AssertionError("o consolidado semanal chegou ao gateway")


def test_o_modulo_nao_fala_com_o_ollama_por_fora():
    # Se voltar a montar o POST na mao, os testes acima param de significar algo:
    # a chamada real passaria ao lado da allowlist que eles verificam.
    fonte = Path(english_coach.__file__).read_text(encoding="utf-8")
    corpo = "\n".join(
        ln for ln in fonte.splitlines()
        if not ln.lstrip().startswith("#") and not ln.lstrip().startswith('"')
    )
    assert "requests.post" not in corpo
    assert "coach_llm.generate" in corpo


def test_o_inbox_continua_na_varredura():
    # O outro jeito de "resolver" isso seria tirar o Inbox do escopo, o que
    # silenciosamente pararia de avaliar as notas em ingles. A escolha registrada
    # foi manter o Inbox e travar a saida.
    assert any(p.name == "Inbox" for p in english_coach.SCAN_DIRS_ABS)
