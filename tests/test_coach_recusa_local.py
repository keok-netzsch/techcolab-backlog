"""Avaliacao vinda do modelo local nao vira nota.

Em 2026-09-02 o Kelvin abriu o Streamlit e viu, numa call 100% em ingles com o
Stefan, um relatorio dizendo "Kelvin's Italian is generally understandable", com
"Top issue: Pronunciation - moin, moin -> bonjour, bonjour". A nota B1 entrou no
`progress.md` e no grafico de evolucao.

O caminho: o gateway devolveu HTTP 504 tres vezes, o `coach_llm` caiu para o
`qwen2.5-coder` local e o modelo de CODIGO de 7B inventou a avaliacao. O guarda
que existia so recusava quando o `level` vinha malformado — e nao veio: o
fallback devolveu `level: A2`, formato impecavel, conteudo fantasia.

Nota errada e pior que nota nenhuma aqui, porque `_last_level()` ancora as
sessoes seguintes na anterior: um B1 falso rebaixa o teto de todas as proximas.
"""
import re
import sys
from pathlib import Path

CR = Path(__file__).resolve().parent.parent / "call-recorder"
sys.path.insert(0, str(CR))

FONTE = (CR / "coach.py").read_text(encoding="utf-8")


def _bloco_degradado() -> str:
    i = FONTE.index("if coach_llm.last_run_degraded():")
    return FONTE[i:FONTE.index("prev_level = _last_level()", i)]


def test_run_degradado_sai_sem_gravar():
    assert "sys.exit(0)" in _bloco_degradado()


def test_run_degradado_nao_grava_com_confianca_baixa():
    """A regressao exata: marcar `level_confidence = low` e seguir gravando.
    O arquivo saia com um aviso que ninguem le e a nota entrava no progress."""
    bloco = _bloco_degradado()
    assert 'ev["level_confidence"] = "low"' not in bloco
    assert 'ev["degraded"] = True' not in bloco


def test_recusa_acontece_antes_de_qualquer_escrita():
    """Ordem importa: o `sys.exit` tem que vir antes de `_append_progress` e de
    `_consolidar_no_dia`, senao o guarda existe e nao protege nada."""
    saida = FONTE.index("sys.exit(0)", FONTE.index("if coach_llm.last_run_degraded():"))
    for escritor in ("_append_progress(", "_consolidar_no_dia(", "_update_index("):
        chamada = FONTE.index(escritor, FONTE.index("def main():"))
        assert saida < chamada, escritor


def test_o_comando_para_repetir_aparece_na_mensagem():
    """Recusar sem dizer o que fazer transforma o guarda em beco sem saida."""
    bloco = _bloco_degradado()
    assert "coach.py --transcript" in bloco
    assert "{args.transcript}" in bloco


def test_portao_de_idioma_continua_recusando_do_mesmo_jeito():
    """As duas recusas seguem o mesmo principio e nao podem divergir: recusar
    nunca pode parecer nota baixa."""
    assert re.search(r"Sessao NAO avaliada.*\n.*sys\.exit\(0\)",
                     FONTE.replace("\r", ""), re.M) or \
        FONTE.count("Sessao NAO avaliada") >= 2
