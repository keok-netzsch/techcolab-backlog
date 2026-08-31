"""Contrato do formato de transcript — o lado PRODUTOR.

Desde 2026-08-29 (P1 do PM review) o Team Memory Agent parseia os transcripts
das Daily BIZ com a regex abaixo (copiada do tma_capture.py dele, verbatim).
Este teste existe para que uma mudanca de formato AQUI quebre AQUI, no pytest
que roda antes de todo commit - e nao dali a uma semana, em silencio, no
registro semanal do time.

Se este teste quebrar de proposito (mudanca de formato deliberada): coordenar
com o TMA ANTES - ~/TeamMemoryAgent/bin/tma_capture.py aponta para o path
absoluto dos jobs e nao tem como saber que o formato mudou.
"""

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "call-recorder"))

# Verbatim do consumidor (tma_capture.py). NAO "melhorar" aqui: se o TMA mudar,
# muda-se aqui junto; se aqui mudar sozinho, o teste deixa de proteger nada.
TMA_LINE = re.compile(r'^\[\s*[\d.]+s\]\s*([^:]{1,40}):\s*(.*)$')


def _dual_line(t, label, text):
    # Copia exata do f-string de record.py:529 - o formato que _transcribe_dual
    # escreve. Se record.py mudar o formato, este helper fica errado e os
    # asserts de round-trip abaixo pegam, porque comparam com o arquivo real.
    return f"[{t:05.1f}s] {label}: {text}"


def test_linha_dual_casa_e_extrai_o_falante():
    import record
    for label in record.SPEAKER_LABELS:
        m = TMA_LINE.match(_dual_line(12.4, label, "vamos fechar o escopo"))
        assert m, f"linha com falante {label!r} nao casa com a regex do TMA"
        assert m.group(1) == label


def test_formato_real_do_record_e_o_mesmo_do_helper():
    # O helper acima precisa ser copia fiel do record.py, senao o teste valida
    # um formato que ninguem escreve. Extrai o f-string do fonte e compara.
    import inspect
    import record
    src = inspect.getsource(record)
    assert 'f"[{t:05.1f}s] {label}: {text}"' in src, (
        "record.py mudou o f-string da linha dual - atualize _dual_line E "
        "coordene com o TMA (tma_capture.py parseia esse formato)")


def test_timestamp_acima_de_999s_continua_casando():
    # 05.1f para de padronizar largura acima de 999.9s (call de 17+ min chega
    # la facil) - o TMA aceita porque a regex nao fixa largura. Garantir.
    assert TMA_LINE.match(_dual_line(1234.5, "Kelvin", "ok"))


def test_dois_pontos_no_texto_nao_engana_o_parser():
    m = TMA_LINE.match(_dual_line(100.0, "Kelvin", "o ponto e: prazo"))
    assert m.group(1) == "Kelvin"
    assert m.group(2) == "o ponto e: prazo"


def test_linha_legada_1_canal_nao_vira_falante_fantasma():
    # Arquivo pre-26/08 nao tem rotulo. O TMA aceita o legado por outro caminho;
    # o que NAO pode acontecer e a linha sem falante casar como se tivesse um.
    assert TMA_LINE.match("[012.4s] entao vamos fechar o escopo") is None
