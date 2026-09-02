"""Nota revisada a mao nao e sobrescrita por reprocessamento.

Em 2026-09-02 regenerei as notas de 27/08 de Pedro-Klein, Pedro-Hennig e Ana-Leite
a partir de transcricao limpa. A premissa era "entrada melhor, nota melhor". Foi
regressao nas tres:

  - Pedro-Klein: a correcao de 31/08 dizia que a licenca ja tinha sido tratada e
    que "o item anterior atribuia isso ao Kelvin - nao era dele nem estava em
    aberto". A regeneracao recolocou `(Kelvin) Confirmar a licenca`.
  - Pedro-Hennig: perdeu a nota de que a linha do NEM passando ao Matheus e
    contexto, e inventou `(Kelvin) Coordenar a decisao do NBSB sobre a transicao
    do Sergera` - dois nomes que nao existem.
  - Ana-Leite: trocou dois itens concretos por itens vagos e gravou os
    placeholders do prompt (`[contexto relevante]`) dentro da nota.

O modelo re-derivando do zero nao sabe o que ja foi julgado errado. Por isso a
trava e sobre EDICAO HUMANA, nao sobre qualidade da entrada.

Regra: nota com `gerado-hash` cujo corpo ainda casa com o hash pode ser
reescrita (ninguem tocou). Corpo divergente, ou nota antiga sem a marca, exige
`--force` explicito.
"""
import sys
from pathlib import Path

CR = Path(__file__).resolve().parent.parent / "call-recorder"
sys.path.insert(0, str(CR))

import process  # noqa: E402


def _nota(tmp_path, corpo, com_hash=True):
    p = tmp_path / "2026-08-27_1on1_Pedro-Klein.md"
    fm = ["---", "date: 2026-08-27", "person: Pedro Klein", "type: 1on1-session"]
    if com_hash:
        fm.append(f"{process.GERADO_HASH}: {process._body_hash(corpo)}")
    fm.append("---")
    p.write_text("\n".join(fm) + "\n\n" + corpo, encoding="utf-8")
    return p


def test_nota_intacta_pode_ser_reescrita(tmp_path):
    p = _nota(tmp_path, "## 2026-08-27\n\n- item gerado pelo modelo")
    assert process.guard_sobrescrita(p) is True


def test_nota_editada_a_mao_e_protegida(tmp_path):
    """O caso real: alguem acrescentou a correcao depois de gerada."""
    corpo = "## 2026-08-27\n\n- [ ] (Pedro) Levar o feedback do MyNet"
    p = _nota(tmp_path, corpo)
    p.write_text(p.read_text(encoding="utf-8")
                 + "\n\n> A licenca ja foi tratada com o Azon nesta call."
                 + "\n> O item anterior atribuia isso ao Kelvin - nao era dele.",
                 encoding="utf-8")
    assert process.guard_sobrescrita(p) is False


def test_force_sobrescreve_mesmo_editada(tmp_path):
    corpo = "## 2026-08-27\n\n- item"
    p = _nota(tmp_path, corpo)
    p.write_text(p.read_text(encoding="utf-8") + "\n> correcao humana",
                 encoding="utf-8")
    assert process.guard_sobrescrita(p, force=True) is True


def test_nota_antiga_sem_marca_e_tratada_como_editada(tmp_path):
    """As tres notas de 31/08 nao tinham `gerado-hash`. O default seguro e recusar:
    sem a marca nao da para distinguir 'gerada e intacta' de 'revisada a mao'."""
    p = _nota(tmp_path, "## 2026-08-27\n\n- item", com_hash=False)
    assert process.guard_sobrescrita(p) is False


def test_nota_que_nao_existe_pode_ser_criada(tmp_path):
    """Roteamento novo nao pode ser travado - a maioria das fatias cria arquivo novo."""
    assert process.guard_sobrescrita(tmp_path / "nao-existe.md") is True


def test_hash_ignora_espaco_no_fim(tmp_path):
    """Editor que apara ou acrescenta linha em branco no fim nao e edicao de
    conteudo, e nao pode disparar a trava."""
    corpo = "## 2026-08-27\n\n- item"
    p = _nota(tmp_path, corpo)
    p.write_text(p.read_text(encoding="utf-8") + "\n\n\n", encoding="utf-8")
    assert process.guard_sobrescrita(p) is True
