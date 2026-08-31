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


@pytest.fixture(autouse=True)
def _no_real_ledger(monkeypatch):
    """O staging registra a proposta no ledger de pendencias do Kelvin. Em teste isso
    escreveria pendencia de verdade no vault dele — aconteceu (P-013/P-014, 31/08).
    O gate e o objeto do teste; o ledger tem os seus."""
    monkeypatch.setattr(process, "_register_pending", lambda *a, **k: None)


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


# ── O gate tem que valer para o dashboard tambem ─────────────────────────────

def test_draft_nao_aprovado_nao_vira_tarefa_no_dashboard(tmp_path):
    """A proposta parqueada nao pode ser colhida como compromisso.

    Sem isto o gate fecha so a porta da frente: o bloco nao chega ao OKR.md, mas
    o dashboard varre TODO .md do vault e colheria a mesma acao inventada direto
    do rascunho - foi assim que a acao fantasma da "Daniela" (2026-06-03) chegou
    ao Action-Dashboard e ao lembrete diario. Proposta nao e compromisso ate ser
    aprovada e aplicada.
    """
    rev = tmp_path / "Team" / "Ana-Leite" / "_review"
    rev.mkdir(parents=True)
    (rev / "2026-06-03-PDI.md").write_text(
        "---\nstatus: draft\nblock: PDI\n---\n\n"
        "- [ ] (Daniela) Estruturar objetivo do projeto ENH @2026-06-30\n",
        encoding="utf-8")

    assert process._collect_open_tasks(tmp_path, process.DASHBOARD_FILE) == []


def test_a_mesma_acao_aprovada_no_arquivo_real_e_colhida(tmp_path):
    """Controle do teste acima: o filtro exclui o diretorio de propostas, nao a
    sintaxe. Aprovado e aplicado, o item aparece normalmente."""
    pessoa = tmp_path / "Team" / "Ana-Leite"
    pessoa.mkdir(parents=True)
    (pessoa / "PDI.md").write_text(
        "- [ ] (Ana Leite) Estruturar objetivo do projeto ENH @2026-06-30\n",
        encoding="utf-8")

    achadas = process._collect_open_tasks(tmp_path, process.DASHBOARD_FILE)
    assert len(achadas) == 1
    assert achadas[0]["owner"] == "Ana Leite"


# ── Aprovar sem tocar no Obsidian (regra do Kelvin, 2026-08-31) ───────────────
# "EU nao quero fazer nada direto no obsidian" — o vault e camada de registro,
# nao de interacao. Entao aprovar nao pode exigir editar frontmatter: e uma acao,
# chamavel do app, de uma sessao do Claude ou do terminal.

def test_aprovar_por_id_sem_editar_arquivo(person, monkeypatch):
    monkeypatch.setattr(process, "VAULT", str(person.parent.parent))
    process._parse_and_save(RESPONSE, person, process.SECTION_MAP,
                            process.SECTION_MODE, date="2026-06-03")

    res = process.cmd_review(approve="Ana-Leite/2026-06-03-PDI")

    assert res["applied"] == 1
    assert "Modelo pumps" in (person / "PDI.md").read_text(encoding="utf-8")
    assert (person / process.REVIEW_DIRNAME / "_applied" / "2026-06-03-PDI.md").exists()


def test_aprovar_uma_nao_arrasta_as_outras(person, monkeypatch):
    """Aprovar o PDI nao pode aplicar o OKR de carona."""
    monkeypatch.setattr(process, "VAULT", str(person.parent.parent))
    process._parse_and_save(RESPONSE, person, process.SECTION_MAP,
                            process.SECTION_MODE, date="2026-06-03")

    process.cmd_review(approve="Ana-Leite/2026-06-03-PDI")

    assert "Reduzir demandas" not in (person / "OKR.md").read_text(encoding="utf-8")
    assert (person / process.REVIEW_DIRNAME / "2026-06-03-OKR.md").exists()


def test_descartar_guarda_em_vez_de_apagar(person, monkeypatch):
    """Descartar nao destroi evidencia: o texto do modelo fica em _rejected/."""
    monkeypatch.setattr(process, "VAULT", str(person.parent.parent))
    process._parse_and_save(RESPONSE, person, process.SECTION_MAP,
                            process.SECTION_MODE, date="2026-06-03")

    process.cmd_review(reject="Ana-Leite/2026-06-03-PDI")

    assert not (person / process.REVIEW_DIRNAME / "2026-06-03-PDI.md").exists()
    guardado = person / process.REVIEW_DIRNAME / "_rejected" / "2026-06-03-PDI.md"
    assert guardado.exists() and "Daniela" in guardado.read_text(encoding="utf-8")
    assert "Daniela" not in (person / "PDI.md").read_text(encoding="utf-8")


def test_id_desconhecido_nao_aplica_nada(person, monkeypatch):
    monkeypatch.setattr(process, "VAULT", str(person.parent.parent))
    process._parse_and_save(RESPONSE, person, process.SECTION_MAP,
                            process.SECTION_MODE, date="2026-06-03")

    res = process.cmd_review(approve="Ana-Leite/nao-existe")

    assert res["applied"] == 0
    assert "Modelo pumps" not in (person / "PDI.md").read_text(encoding="utf-8")
