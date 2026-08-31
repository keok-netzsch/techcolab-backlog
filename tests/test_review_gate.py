"""O gate de aprovacao dos blocos canonicos (PDI/OKR/Overview).

Existe por um incidente real: em 2026-06-03 o modelo local escreveu, direto no PDI,
OKR, Overview e 1on1 da Ana, um objetivo cujo responsavel era uma "Daniela" que nao
existe no time — extraida de uma transcricao sobre o projeto ENH. Ninguem revisou
porque nao havia onde revisar.

Estes testes travam as tres propriedades que impedem isso de voltar:
  1. bloco canonico do modelo NAO chega ao arquivo real
  2. `1on1.md` continua direto (e log de sessao, nao afirmacao sobre a pessoa)
  3. so o que um humano marcou `approved` e aplicado — silencio nao e consentimento
"""
import sys
from pathlib import Path

import pytest

CR = Path(__file__).resolve().parent.parent / "call-recorder"
sys.path.insert(0, str(CR))

import process  # noqa: E402


RESPONSE = """### BLOCO 1on1
~~~markdown
## 2026-06-03

**Topics:**
- Projeto ENH
~~~

### BLOCO PDI
~~~markdown
**PDI:** Modelo pumps no projeto ENH.

**Responsavel:** Daniela
~~~

### BLOCO OKR
~~~markdown
**OKR:** Reduzir demandas abertas.
~~~
"""


@pytest.fixture
def person(tmp_path):
    p = tmp_path / "Team" / "Ana-Leite"
    p.mkdir(parents=True)
    (p / "1on1.md").write_text("# 1on1\n", encoding="utf-8")
    (p / "PDI.md").write_text("# PDI\n", encoding="utf-8")
    (p / "OKR.md").write_text("# OKR\n", encoding="utf-8")
    return p


def test_canonical_blocks_never_reach_the_real_file(person):
    process._parse_and_save(RESPONSE, person, process.SECTION_MAP,
                            process.SECTION_MODE, date="2026-06-03")
    assert "Daniela" not in (person / "PDI.md").read_text(encoding="utf-8")
    assert "Reduzir demandas" not in (person / "OKR.md").read_text(encoding="utf-8")


def test_the_proposal_is_parked_for_review(person):
    process._parse_and_save(RESPONSE, person, process.SECTION_MAP,
                            process.SECTION_MODE, date="2026-06-03")
    staged = sorted((person / process.REVIEW_DIRNAME).glob("*.md"))
    assert [f.name for f in staged] == ["2026-06-03-OKR.md", "2026-06-03-PDI.md"]
    pdi = (person / process.REVIEW_DIRNAME / "2026-06-03-PDI.md").read_text(encoding="utf-8")
    assert "status: draft" in pdi
    assert "target: PDI.md" in pdi
    assert "Daniela" in pdi          # o conteudo nao se perde, so nao vira fato


def test_session_log_is_not_gated(person):
    process._parse_and_save(RESPONSE, person, process.SECTION_MAP,
                            process.SECTION_MODE, date="2026-06-03")
    assert "Projeto ENH" in (person / "1on1.md").read_text(encoding="utf-8")


def test_draft_is_not_applied(person, monkeypatch):
    monkeypatch.setattr(process, "VAULT", str(person.parent.parent))
    process._parse_and_save(RESPONSE, person, process.SECTION_MAP,
                            process.SECTION_MODE, date="2026-06-03")
    res = process.cmd_review(apply=True)
    assert res["applied"] == 0
    assert "Daniela" not in (person / "PDI.md").read_text(encoding="utf-8")


def test_approved_is_applied_and_archived(person, monkeypatch):
    monkeypatch.setattr(process, "VAULT", str(person.parent.parent))
    process._parse_and_save(RESPONSE, person, process.SECTION_MAP,
                            process.SECTION_MODE, date="2026-06-03")
    f = person / process.REVIEW_DIRNAME / "2026-06-03-PDI.md"
    f.write_text(f.read_text(encoding="utf-8").replace("status: draft", "status: approved"),
                 encoding="utf-8")

    res = process.cmd_review(apply=True)
    assert res["applied"] == 1
    assert "Modelo pumps" in (person / "PDI.md").read_text(encoding="utf-8")
    assert not f.exists()                                   # saiu da fila
    assert (person / process.REVIEW_DIRNAME / "_applied" / f.name).exists()


def test_human_edit_survives_approval(person, monkeypatch):
    """O ponto do gate: o que o humano deixou no arquivo e o que entra."""
    monkeypatch.setattr(process, "VAULT", str(person.parent.parent))
    process._parse_and_save(RESPONSE, person, process.SECTION_MAP,
                            process.SECTION_MODE, date="2026-06-03")
    f = person / process.REVIEW_DIRNAME / "2026-06-03-PDI.md"
    t = f.read_text(encoding="utf-8").replace("status: draft", "status: approved")
    t = t.replace("**Responsavel:** Daniela", "**Responsavel:** Ana Leite")
    f.write_text(t, encoding="utf-8")

    process.cmd_review(apply=True)
    pdi = (person / "PDI.md").read_text(encoding="utf-8")
    assert "Ana Leite" in pdi
    assert "Daniela" not in pdi
