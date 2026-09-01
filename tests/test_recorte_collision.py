"""Duas fatias da mesma call, para a mesma pessoa, no mesmo dia.

Roteamento por assunto (2026-08-28) permite N destinos por gravacao. O que ninguem
tinha exercitado e o caso em que **dois desses destinos sao a mesma pessoa**: um
Jour Fixe que cobre GPTW, ServiceNow e os pesos dos OKRs sao tres notas, nao uma.

Em 2026-09-01 o roteamento aprovado pelo Kelvin tinha 21 destinos entre 8 pessoas.
Doze deles colidiam: `_strip_dated_1on1` apagava TODA secao `## {data}` antes de
escrever, e a nota standalone era `write_text` num nome que so tinha data + pessoa.
Resultado: a segunda fatia apagava a primeira, em silencio, e o dia terminava com
uma nota onde o roteamento tinha produzido tres. Nove notas perdidas sem uma linha
de erro.

Estes testes travam as quatro superficies onde a colisao acontecia:
  1. a secao datada em `1on1.md`
  2. a nota standalone em `1on1/`
  3. a proposta parkeada no gate (`_review/`)
  4. a pendencia que aponta para a proposta (texto duplicado e recusado com exit 2)
"""
import sys
from pathlib import Path

import pytest

CR = Path(__file__).resolve().parent.parent / "call-recorder"
sys.path.insert(0, str(CR))

import process  # noqa: E402

# Capturado no import, ANTES da fixture autouse abaixo troca-lo por um no-op: o
# teste da pendencia precisa exercitar a funcao de verdade.
_REAL_REGISTER_PENDING = process._register_pending


@pytest.fixture(autouse=True)
def _no_real_ledger(monkeypatch):
    """Mesma razao do test_review_gate: o staging registra pendencia de verdade no
    ledger do Kelvin. Ja aconteceu (P-013/P-014, 31/08)."""
    monkeypatch.setattr(process, "_register_pending", lambda *a, **k: None)


# ── 1. a secao datada em 1on1.md ─────────────────────────────────────────────

def test_strip_sem_recorte_nao_apaga_irmao_rotulado(tmp_path):
    """O caso que custou as nove notas: gravar a fatia 2 nao pode apagar a fatia 1."""
    p = tmp_path / "1on1.md"
    p.write_text(
        "## 2026-08-27 — GPTW\n\n- A\n\n---\n\n"
        "## 2026-08-27\n\n- avulsa\n\n---\n",
        encoding="utf-8",
    )
    process._strip_dated_1on1(p, "2026-08-27")
    t = p.read_text(encoding="utf-8")
    assert "## 2026-08-27 — GPTW" in t   # o irmao rotulado sobrevive
    assert "- A" in t
    assert "- avulsa" not in t           # so a secao nua saiu


def test_strip_com_recorte_apaga_so_aquele_rotulo(tmp_path):
    p = tmp_path / "1on1.md"
    p.write_text(
        "## 2026-08-27 — GPTW\n\n- A\n\n---\n\n"
        "## 2026-08-27 — ServiceNow SPM\n\n- B\n\n---\n\n"
        "## 2026-08-27\n\n- C\n\n---\n",
        encoding="utf-8",
    )
    process._strip_dated_1on1(p, "2026-08-27", recorte="GPTW")
    t = p.read_text(encoding="utf-8")
    assert "- A" not in t                        # alvo removido
    assert "## 2026-08-27 — ServiceNow SPM" in t  # irmao preservado
    assert "- C" in t                             # secao nua preservada


def test_strip_com_recorte_e_idempotente(tmp_path):
    """Reprocessar a MESMA fatia continua substituindo, nao empilhando."""
    p = tmp_path / "1on1.md"
    p.write_text("## 2026-08-27 — GPTW\n\n- v1\n\n---\n", encoding="utf-8")
    process._strip_dated_1on1(p, "2026-08-27", recorte="GPTW")
    assert "- v1" not in p.read_text(encoding="utf-8")


def test_reuniao_estruturada_continua_idempotente(tmp_path):
    """O template estruturado ja escrevia `## {data} — Reuniao estruturada`. Com o
    strip agora exato, ele so continua substituivel se passar o mesmo rotulo."""
    p = tmp_path / "1on1.md"
    heading = process.dated_heading("2026-08-27", "Reunião estruturada")
    p.write_text(f"{heading}\n\n- v1\n\n---\n", encoding="utf-8")
    process._strip_dated_1on1(p, "2026-08-27", recorte="Reunião estruturada")
    assert "- v1" not in p.read_text(encoding="utf-8")


def test_fallback_carrega_o_rotulo(tmp_path):
    """Falha de estruturacao de uma fatia nao pode aterrissar na secao de outra."""
    p = tmp_path / "1on1.md"
    p.write_text("---\n---\n", encoding="utf-8")
    process._fallback_1on1(p, "2026-08-27", recorte="GPTW")
    t = p.read_text(encoding="utf-8")
    assert "## 2026-08-27 — GPTW" in t
    assert "<!-- unparsed -->" in t


# ── 2. a nota standalone ─────────────────────────────────────────────────────

def test_duas_fatias_geram_duas_notas_standalone(tmp_path, monkeypatch):
    person = tmp_path / "Team" / "Alberto-Reuters"
    person.mkdir(parents=True)
    (person / "1on1.md").write_text("# 1on1\n", encoding="utf-8")
    src = tmp_path / "t.txt"
    src.write_text("[000.0s] Kelvin: conteudo real da fatia\n", encoding="utf-8")

    monkeypatch.setattr(process, "VAULT", str(tmp_path))
    monkeypatch.setattr(
        process, "_ollama_generate",
        lambda *a, **k: "### BLOCO 1on1\n~~~markdown\n## x\n\n**Topics:**\n- t\n~~~\n")

    process.cmd_transcript("Alberto-Reuters", str(src), "2026-08-27",
                           recorte="GPTW")
    process.cmd_transcript("Alberto-Reuters", str(src), "2026-08-27",
                           recorte="ServiceNow SPM")

    notas = sorted(f.name for f in (person / "1on1").glob("*.md"))
    assert notas == [
        "2026-08-27_1on1_Alberto-Reuters.gptw.md",
        "2026-08-27_1on1_Alberto-Reuters.servicenow-spm.md",
    ]


def test_sem_recorte_o_nome_da_nota_nao_muda(tmp_path, monkeypatch):
    """Call nao fatiada continua no nome historico — nada de migrar o passado."""
    person = tmp_path / "Team" / "Ana-Leite"
    person.mkdir(parents=True)
    (person / "1on1.md").write_text("# 1on1\n", encoding="utf-8")
    src = tmp_path / "t.txt"
    src.write_text("[000.0s] Kelvin: conteudo\n", encoding="utf-8")

    monkeypatch.setattr(process, "VAULT", str(tmp_path))
    monkeypatch.setattr(process, "_ollama_generate", lambda *a, **k: "sem bloco")

    process.cmd_transcript("Ana-Leite", str(src), "2026-08-28")
    assert (person / "1on1" / "2026-08-28_1on1_Ana-Leite.md").exists()


# ── 3. a proposta no gate ────────────────────────────────────────────────────

RESPONSE = """### BLOCO PDI
~~~markdown
**PDI:** algo proposto pelo modelo.
~~~
"""


def test_duas_fatias_geram_duas_propostas_no_gate(tmp_path):
    person = tmp_path / "Team" / "Lucas-Shizuno"
    person.mkdir(parents=True)
    process._parse_and_save(RESPONSE, person, process.SECTION_MAP,
                            process.SECTION_MODE, date="2026-08-28",
                            recorte="movimentacao para data scientist")
    process._parse_and_save(RESPONSE, person, process.SECTION_MAP,
                            process.SECTION_MODE, date="2026-08-28",
                            recorte="posicao do Stefan")
    staged = sorted(f.name for f in (person / process.REVIEW_DIRNAME).glob("*.md"))
    assert len(staged) == 2, staged
    assert staged == [
        "2026-08-28-movimentacao-para-data-scientist-PDI.md",
        "2026-08-28-posicao-do-stefan-PDI.md",
    ]


def test_sem_recorte_o_nome_da_proposta_nao_muda(tmp_path):
    person = tmp_path / "Team" / "Ana-Leite"
    person.mkdir(parents=True)
    process._parse_and_save(RESPONSE, person, process.SECTION_MAP,
                            process.SECTION_MODE, date="2026-06-03")
    assert (person / process.REVIEW_DIRNAME / "2026-06-03-PDI.md").exists()


# ── 4. a pendencia que aponta para a proposta ────────────────────────────────

def test_pendencias_de_fatias_diferentes_nao_sao_texto_duplicado(monkeypatch):
    """`pending.py add` recusa texto duplicado (exit 2), em silencio porque a
    chamada e capture_output. Sem o recorte no texto, a segunda proposta ficava
    orfa: parkeada no gate e sem nada apontando para ela no chat."""
    textos = []

    class _Run:
        returncode = 0

    def _fake_run(args, **kw):
        textos.append(args[args.index("--texto") + 1])
        return _Run()

    import subprocess
    monkeypatch.setattr(subprocess, "run", _fake_run)

    _REAL_REGISTER_PENDING("Lucas-Shizuno", "PDI", "2026-08-28",
                           recorte="movimentacao para data scientist")
    _REAL_REGISTER_PENDING("Lucas-Shizuno", "PDI", "2026-08-28",
                           recorte="posicao do Stefan")
    assert len(set(textos)) == 2, textos


# ── slug compartilhado com route.py ──────────────────────────────────────────

def test_route_nao_tem_mais_slug_proprio():
    """A fatia do transcript e a nota tem que cair no mesmo slug, senao a nota
    deixa de apontar para o texto que a produziu. `route.py` importa `process`
    dentro da funcao, entao a checagem e sobre o modulo nao redefinir o seu."""
    import route
    assert not hasattr(route, "_slug")
    assert "proc.slugify(" in Path(route.__file__).read_text(encoding="utf-8")
    assert process.slugify("ServiceNow SPM") == "servicenow-spm"
