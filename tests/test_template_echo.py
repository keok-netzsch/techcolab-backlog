"""Bloco que e so o gabarito do prompt nao pode virar registro sobre a pessoa.

`[resumo PDI]` e `[resumo OKR]` sao literais do TEMPLATE em process.py. O prompt
pede blocos "para cada categoria COM conteudo", mas quando nao ha o que dizer o
modelo devolve o marcador em vez de omitir a categoria - e o pipeline gravava
`## Atualizacao <data>` com corpo vazio no PDI da pessoa. Aconteceu 2x no PDI da
Ana (visto em 31/08). Secao datada e vazia parece registro e nao diz nada.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "call-recorder"))

import process  # noqa: E402


def test_gabarito_puro_e_eco():
    assert process._is_template_echo("## Atualizacao 2026-08-27\n[resumo PDI]")
    assert process._is_template_echo("[resumo OKR]")
    assert process._is_template_echo("## Atualizacao 2026-08-27\n[contexto relevante]")
    assert process._is_template_echo("   \n\n  ")


def test_conteudo_de_verdade_nao_e_eco():
    assert not process._is_template_echo(
        "## Atualizacao 2026-08-27\nAna concluiu a documentacao de export.")
    # cita o marcador MAS tem conteudo — o criterio e "sobrou texto", nao
    # "aparece a palavra"
    assert not process._is_template_echo(
        "## Atualizacao 2026-08-27\n[resumo PDI] ainda pendente de revisao com ela")


def test_bloco_eco_nao_chega_ao_arquivo_nem_ao_review(tmp_path, monkeypatch):
    monkeypatch.setattr(process, "_stage_for_review",
                        lambda *a, **k: (_ for _ in ()).throw(
                            AssertionError("eco nao pode nem ser parqueado")))
    pessoa = tmp_path / "Ana-Leite"
    pessoa.mkdir()
    resposta = (
        "### BLOCO PDI\n~~~markdown\n## Atualizacao 2026-08-27\n[resumo PDI]\n~~~\n"
    )
    saved = process._parse_and_save(
        resposta, pessoa, {"PDI": "PDI.md"}, {"PDI": "append"}, date="2026-08-27")
    assert saved == 0
    assert not (pessoa / "PDI.md").exists()


def test_bloco_com_conteudo_continua_passando(tmp_path, monkeypatch):
    vistos = []
    monkeypatch.setattr(process, "_stage_for_review",
                        lambda base, bt, tf, c, date=None: vistos.append((bt, c)))
    pessoa = tmp_path / "Ana-Leite"
    pessoa.mkdir()
    resposta = ("### BLOCO PDI\n~~~markdown\n## Atualizacao 2026-08-27\n"
                "Ana priorizou o documento de export.\n~~~\n")
    assert process._parse_and_save(
        resposta, pessoa, {"PDI": "PDI.md"}, {"PDI": "append"}, date="2026-08-27") == 1
    assert vistos and "export" in vistos[0][1]
