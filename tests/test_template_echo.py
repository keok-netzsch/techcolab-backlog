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


def _stub_stage(vistos, base):
    """Duble de `_stage_for_review`.

    Desde 2026-09-02 a funcao real devolve o caminho da proposta, ou None quando o
    bloco esta vazio e nao vira proposta nenhuma — e `_parse_and_save` conta em
    cima disso. Um duble que devolve None (era o caso: `list.append` retorna None)
    faz o contador ficar em zero e o teste acusa uma regressao que nao existe.
    """
    def _f(_base, bt, _tf, c, **_k):
        vistos.append((bt, c))
        return base / "_review" / f"{bt}.md"
    return _f


def test_bloco_com_conteudo_continua_passando(tmp_path, monkeypatch):
    vistos = []
    monkeypatch.setattr(process, "_stage_for_review",
                        _stub_stage(vistos, tmp_path / "Ana-Leite"))
    pessoa = tmp_path / "Ana-Leite"
    pessoa.mkdir()
    resposta = ("### BLOCO PDI\n~~~markdown\n## Atualizacao 2026-08-27\n"
                "Ana priorizou o documento de export.\n~~~\n")
    assert process._parse_and_save(
        resposta, pessoa, {"PDI": "PDI.md"}, {"PDI": "append"}, date="2026-08-27") == 1
    assert vistos and "export" in vistos[0][1]


def test_bloco_vazio_nao_vira_proposta(tmp_path, monkeypatch):
    """O modelo dizendo "nao ha atualizacao" acertou; o erro era virar arquivo.

    Em 2026-09-02 foram 3 de 24 propostas numa leva so, cada uma gerando uma
    pendencia no ledger e exigindo uma decisao do Kelvin para escrever uma linha
    inutil dentro do PDI da pessoa.
    """
    vistos = []
    monkeypatch.setattr(process, "_stage_for_review",
                        _stub_stage(vistos, tmp_path / "Daniel-Lima"))
    pessoa = tmp_path / "Daniel-Lima"
    pessoa.mkdir()
    resposta = ("### BLOCO PDI\n~~~markdown\n## Atualizacao 2026-08-27\n"
                "Nao ha atualizacao especifica para o PDI nesta reuniao.\n~~~\n")
    assert process._parse_and_save(
        resposta, pessoa, {"PDI": "PDI.md"}, {"PDI": "append"},
        date="2026-08-27") == 0


def test_deteccao_de_bloco_vazio():
    vazio = "## Atualizacao 2026-08-27\nNao ha atualizacao para os OKRs nesta reuniao."
    cheio = ("## Atualizacao 2026-08-28\nAna trouxe reflexao sobre dificuldade em "
             "consolidar conhecimento tecnico para apresentacoes executivas.")
    assert process._bloco_vazio(vazio)
    assert process._bloco_vazio("## Atualizacao 2026-08-27\n")
    assert not process._bloco_vazio(cheio)
