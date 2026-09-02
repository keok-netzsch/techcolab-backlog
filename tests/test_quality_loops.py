"""O gate passou a olhar laco ENTRE linhas, alfabeto e linha vazia.

Ate 2026-09-02 o `transcript_quality.py` so via repeticao DENTRO de uma linha e
fronteira de janela de 30s. Consequencia medida: a call `2026-08-28_09-56`
(Hernan + Stefan) passou com **0 suspeitas** carregando ~21 linhas de
"o que / e / o que / e" no fim, e a call do OKR 05 passou com 26 linhas em
cirilico dentro.

O risco do conserto e o oposto: contar repeticao no arquivo inteiro marcaria
"Sim." x30 de um dialogo normal e todo arquivo viraria AVISO. O discriminador
foi medido nos arquivos reais em 02/09:

    laco de decoder      gap mediano 0,80-1,00s
    "Boa tarde." x5      gap mediano 3,00s   (gente entrando na call)
    "Obrigado." x9       gap mediano 2,00s   (encerramento)

Por isso `LOOP_MAX_GAP = 1.5`. Estes testes travam os dois lados: o laco tem que
ser pego, e a saudacao NAO pode ser.

O que o gate continua sem pegar, de propositoo: TRADUCAO. Quando o Whisper decide
um idioma so para o arquivo inteiro e traduz a parte em ingles, a saida e
portugues legitimo e nenhum teste textual distingue. Isso se conserta na
transcricao, nao aqui.
"""
import sys
from pathlib import Path

CR = Path(__file__).resolve().parent.parent / "call-recorder"
sys.path.insert(0, str(CR))

import transcript_quality as tq  # noqa: E402


def _txt(linhas):
    return "\n".join(f"[{t:06.1f}s] {sp}: {corpo}" for t, sp, corpo in linhas)


def test_laco_do_decoder_e_pego():
    linhas = [(3030.0 + i, "Interlocutor", "o que" if i % 2 == 0 else "e")
              for i in range(21)]
    rep = tq.scan(_txt(linhas))
    assert not rep["ok"]
    assert len(rep["suspect"]) == 21
    assert "laco entre linhas" in next(iter(rep["motivos"].values()))


def test_saudacao_de_gente_entrando_nao_e_laco():
    """O caso real de 2026-08-28_14-40 (anuncio do PLR): 8 linhas, gap de 3s."""
    linhas = [(21.6, "Interlocutor", "Boa tarde."),
              (72.0, "Interlocutor", "Boa tarde."),
              (75.0, "Interlocutor", "Boa tarde."),
              (78.0, "Interlocutor", "Boa tarde."),
              (81.0, "Interlocutor", "Boa tarde."),
              (84.0, "Interlocutor", "Bom dia, time."),
              (87.0, "Interlocutor", "Boa tarde.")]
    assert tq.loop_runs(tq.parse(_txt(linhas))) == []


def test_agradecimento_no_encerramento_nao_e_laco():
    """2026-08-11_12-27: 9 linhas de "Obrigado." com gap de 2s."""
    linhas = [(2934.8 + 2 * i, "Interlocutor", "Obrigado.") for i in range(9)]
    assert tq.loop_runs(tq.parse(_txt(linhas))) == []


def test_dialogo_normal_com_muito_sim_nao_dispara():
    """Contagem global marcaria isso; o corte consecutivo+gap nao."""
    linhas = []
    for i in range(30):
        linhas.append((i * 20.0, "Kelvin", "Sim."))
        linhas.append((i * 20.0 + 8, "Interlocutor",
                       f"Entao o ponto numero {i} e esse aqui, veja bem."))
    rep = tq.scan(_txt(linhas))
    assert rep["ok"], rep["motivos"]


def test_alfabeto_nao_latino_e_pego():
    """A call do OKR 05 saiu com a fala do Kelvin em cirilico.

    O cirilico vai como escape numerico de proposito: assim este arquivo fica
    ASCII. Com o caractere literal, o teste passa a medir a codificacao com que
    o arquivo foi gravado em vez de medir o detector - foi o que aconteceu na
    primeira versao, que falhou por corrupcao na gravacao, nao por bug.
    """
    cir1 = "\u043f\u0440\u0438\u0432\u0435\u0442"
    cir2 = "\u0437\u043d\u0430\u044e"
    linhas = [(10.0, "Kelvin", "Tudo bem, vamos comecar."),
              (12.0, "Kelvin", cir1),
              (14.0, "Kelvin", cir2)]
    rep = tq.scan(_txt(linhas))
    assert not rep["ok"]
    assert sum(1 for m in rep["motivos"].values()
               if m == "alfabeto nao-latino") == 2


def test_linha_so_com_pontuacao_e_pega_mesmo_espacada():
    """2026-08-27_08-01: "..." aparece a cada 5-6s, fora do corte de gap."""
    linhas = [(460.0, "Kelvin", "..."), (484.0, "Kelvin", "..."),
              (503.0, "Kelvin", "..."), (520.0, "Kelvin", "Isso ai faz sentido.")]
    rep = tq.scan(_txt(linhas))
    assert len(rep["suspect"]) == 3
    assert all(m == "linha sem conteudo" for k, m in rep["motivos"].items())


def test_transcricao_limpa_continua_limpa():
    linhas = [(10.0, "Kelvin", "Bom dia, vamos falar do OKR do Daniel."),
              (18.0, "Interlocutor", "Claro, eu preparei os numeros da comunidade."),
              (31.0, "Kelvin", "Quantas sessoes fecharam no trimestre?"),
              (40.0, "Interlocutor", "Foram dez, com media de quarenta pessoas.")]
    assert tq.scan(_txt(linhas))["ok"]
