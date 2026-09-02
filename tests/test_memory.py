"""Tests for Cross-Session Memory (idea-031): deterministic aggregation of context
across a person's 1:1 sessions and across people. No LLM involved."""
import sys
from pathlib import Path

CR_DIR = Path(__file__).resolve().parents[1] / "call-recorder"
sys.path.insert(0, str(CR_DIR))

import process  # noqa: E402

ONE_ON_ONE = """---
type: 1on1-log
---

## 2026-06-20

**Topics:**
- Carga de trabalho
- Projeto Docker

**Action items:**
- [ ] (Kelvin) Revisar projeto Docker
- [x] (Ana) Enviar documentacao

## 2026-05-10

**Topics:**
- Carga de trabalho
- Certificacao Alura

**Action items:**
- [ ] (Ana) Concluir Alura Python
- [ ] (Kelvin) Revisar projeto Docker
"""


def test_build_session_memory_parses_all_sessions_newest_first():
    sessions = process.build_session_memory(ONE_ON_ONE)
    assert [s["date"] for s in sessions] == ["2026-06-20", "2026-05-10"]
    assert "Carga de trabalho" in sessions[0]["topics"]
    assert {"text": "(Ana) Enviar documentacao", "done": True} in sessions[0]["actions"]


def test_build_session_memory_empty():
    assert process.build_session_memory("") == []
    assert process.build_session_memory("no dated sessions here") == []


def test_summarize_dedupes_open_actions_keeping_newest_date():
    mem = process.summarize_person_memory(process.build_session_memory(ONE_ON_ONE))
    open_texts = [a["text"] for a in mem["open_actions"]]
    # "(Kelvin) Revisar projeto Docker" appears in both sessions -> once, newest date
    assert open_texts.count("(Kelvin) Revisar projeto Docker") == 1
    docker = next(a for a in mem["open_actions"] if "Docker" in a["text"])
    assert docker["since"] == "2026-06-20"
    # done action excluded
    assert all("Enviar documentacao" not in t for t in open_texts)
    # still-open Alura action kept
    assert any("Alura" in t for t in open_texts)


def test_summarize_recurring_topics_and_span():
    mem = process.summarize_person_memory(process.build_session_memory(ONE_ON_ONE))
    recurring = [t["topic"] for t in mem["recurring_topics"]]
    assert "Carga de trabalho" in recurring          # in both sessions
    assert "Projeto Docker" not in recurring         # only once
    assert mem["session_count"] == 2
    assert mem["first_date"] == "2026-05-10"
    assert mem["last_date"] == "2026-06-20"


def test_cross_person_topics_flags_shared_only():
    ana = process.build_session_memory(
        "## 2026-06-01\n\n**Topics:**\n- MDM project\n- Carga de trabalho\n")
    pedro = process.build_session_memory(
        "## 2026-06-02\n\n**Topics:**\n- MDM project\n- Certificacao\n")
    shared = process.cross_person_topics({"Ana Leite": ana, "Pedro Klein": pedro})
    topics = {t["topic"]: t["people"] for t in shared}
    assert "MDM project" in topics
    assert topics["MDM project"] == ["Ana Leite", "Pedro Klein"]
    assert "Certificacao" not in topics              # only one person


def test_cmd_memory_person_writes_digest(tmp_path, monkeypatch):
    monkeypatch.setattr(process, "VAULT", str(tmp_path))
    p = tmp_path / "Team" / "Ana-Leite"
    p.mkdir(parents=True)
    (p / "1on1.md").write_text(ONE_ON_ONE, encoding="utf-8")

    out = process.cmd_memory(person_folder="Ana-Leite")

    assert out == str(p / "memory.md")
    md = (p / "memory.md").read_text(encoding="utf-8")
    assert "type: cross-session-memory" in md
    assert "## For future Claude" in md
    assert "Revisar projeto Docker" in md
    assert "Carga de trabalho (2x)" in md
    assert "since 2026-06-20" in md


def test_cmd_memory_all_writes_per_person_and_cross(tmp_path, monkeypatch):
    monkeypatch.setattr(process, "VAULT", str(tmp_path))
    for folder, topic in [("Ana-Leite", "MDM project"), ("Pedro-Klein", "MDM project")]:
        d = tmp_path / "Team" / folder
        d.mkdir(parents=True)
        (d / "1on1.md").write_text(
            f"## 2026-06-01\n\n**Topics:**\n- {topic}\n\n**Action items:**\n- [ ] (Kelvin) x\n",
            encoding="utf-8")

    out = process.cmd_memory()

    assert out == str(tmp_path / "Cross-Session-Memory.md")
    cross = Path(out).read_text(encoding="utf-8")
    assert "MDM project" in cross
    assert "Ana Leite" in cross and "Pedro Klein" in cross
    # per-person digests written too
    assert (tmp_path / "Team" / "Ana-Leite" / "memory.md").exists()
    assert (tmp_path / "Team" / "Pedro-Klein" / "memory.md").exists()


def test_duas_fatias_do_mesmo_dia_sao_uma_sessao():
    """Roteamento por assunto gera `## {data} — {recorte}` varias vezes no mesmo dia.

    Contando SECAO, uma call fatiada em tres virava "3 sessoes", e um topico
    citado uma vez em cada fatia aparecia como recorrente — o limiar de
    recorrencia e >= 2 sessoes e existe para pegar assunto que volta em dias
    diferentes, nao dentro da mesma call.

    Medido em 2026-09-02 na Weekly com a Ana: duas fatias, session_count=2 e
    "Power BI" reportado como recorrente a partir de uma conversa so.
    """
    import process

    txt = (
        "## 2026-09-02 — governanca de export\n\n"
        "**Topics:**\n- Power BI\n\n"
        "**Action items:**\n- [ ] (Ana) revisar politica\n\n---\n\n"
        "## 2026-09-02 — licenca e prioridades\n\n"
        "**Topics:**\n- Power BI\n\n"
        "**Action items:**\n- [ ] (Ana) finalizar ServiceNow\n"
    )
    sessoes = process.build_session_memory(txt)

    assert len(sessoes) == 1
    assert sessoes[0]["date"] == "2026-09-02"
    assert sessoes[0]["topics"] == ["Power BI"]          # deduplicado no dia
    assert len(sessoes[0]["actions"]) == 2               # as duas acoes sobrevivem

    resumo = process.summarize_person_memory(sessoes)
    assert resumo["session_count"] == 1


def test_dias_diferentes_continuam_sendo_sessoes_diferentes():
    """O conserto acima nao pode colapsar dias distintos."""
    import process

    txt = (
        "## 2026-09-02 — fatia A\n\n**Topics:**\n- Power BI\n\n---\n\n"
        "## 2026-08-28\n\n**Topics:**\n- Power BI\n"
    )
    sessoes = process.build_session_memory(txt)
    assert [s["date"] for s in sessoes] == ["2026-09-02", "2026-08-28"]

    recorrentes = process.summarize_person_memory(sessoes)["recurring_topics"]
    assert recorrentes == [{"topic": "Power BI", "count": 2}]
