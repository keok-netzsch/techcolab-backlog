"""English Coach: um relatorio por DIA, nao um por call.

Ate 2026-09-02 cada call virava um arquivo `{data}_{hora}_english-coach.md` e uma
linha no progress. So naquele dia foram 4 arquivos — o coach dispara por IDIOMA,
entao toda call em ingles gera um. Pedido do Kelvin: "prefiro que o english coach
gere um relatorio por dia ou semana, com tudo junto, ja que e assim".
"""
import datetime
import sys
from pathlib import Path

import pytest

CR = Path(__file__).resolve().parent.parent / "call-recorder"
sys.path.insert(0, str(CR))

import coach  # noqa: E402


def _md(level, overall, hora):
    return ("---\n"
            f"date: 2026-09-02\ntime: {hora}\ntype: english-coach-session\n"
            f"overall: {overall}\nlevel: {level}\ntags: [english-coach]\n---\n\n"
            "# English Coach Session — 2026-09-02\n\n"
            f"> resumo da call das {hora}\n")


@pytest.fixture
def sessoes(tmp_path, monkeypatch):
    monkeypatch.setattr(coach, "SESSIONS_DIR", tmp_path)
    return tmp_path


def test_duas_calls_no_mesmo_dia_dao_um_arquivo(sessoes):
    manha = datetime.datetime(2026, 9, 2, 11, 26)
    tarde = datetime.datetime(2026, 9, 2, 13, 53)

    f = coach._daily_session_file(manha)
    f.write_text(coach._consolidar_no_dia(f, _md("B1", 6, "11:26"), manha, 1),
                 encoding="utf-8")
    f.write_text(coach._consolidar_no_dia(f, _md("B2", 7, "13:53"), tarde, 2),
                 encoding="utf-8")

    assert len(list(sessoes.glob("*.md"))) == 1
    assert f.name == "2026-09-02_english-coach.md"

    txt = f.read_text(encoding="utf-8")
    assert "## Call 1 — 11:26" in txt
    assert "## Call 2 — 13:53" in txt
    assert "calls: 2" in txt


def test_frontmatter_do_dia_segue_a_call_mais_recente(sessoes):
    """`_level_history` le so os primeiros 600 chars.

    Se o frontmatter ficasse na primeira call, o dia inteiro ancoraria num nivel
    velho e o clamp de CEFR compararia contra o numero errado.
    """
    manha = datetime.datetime(2026, 9, 2, 11, 26)
    tarde = datetime.datetime(2026, 9, 2, 13, 53)

    f = coach._daily_session_file(manha)
    f.write_text(coach._consolidar_no_dia(f, _md("B1", 6, "11:26"), manha, 1),
                 encoding="utf-8")
    f.write_text(coach._consolidar_no_dia(f, _md("B2", 7, "13:53"), tarde, 2),
                 encoding="utf-8")

    frontmatter = f.read_text(encoding="utf-8").split("---")[1]
    assert "level: B2" in frontmatter
    assert "overall: 7" in frontmatter


def test_contagem_de_calls_do_dia(sessoes):
    hoje = datetime.datetime(2026, 9, 2, 11, 26)
    assert coach._calls_no_dia(hoje) == 1

    f = coach._daily_session_file(hoje)
    f.write_text(coach._consolidar_no_dia(f, _md("B1", 6, "11:26"), hoje, 1),
                 encoding="utf-8")
    assert coach._calls_no_dia(hoje) == 2


def test_dias_diferentes_continuam_em_arquivos_diferentes(sessoes):
    d1 = datetime.datetime(2026, 9, 2, 11, 26)
    d2 = datetime.datetime(2026, 9, 3, 9, 0)

    for dt in (d1, d2):
        f = coach._daily_session_file(dt)
        f.write_text(coach._consolidar_no_dia(f, _md("B2", 7, dt.strftime("%H:%M")), dt, 1),
                     encoding="utf-8")

    assert len(list(sessoes.glob("*.md"))) == 2


def test_progress_tem_uma_linha_por_dia(tmp_path, monkeypatch):
    """Um dia com 4 calls enchia o log com 4 linhas da mesma data — o grafico de
    evolucao passava a medir frequencia de reuniao, nao progresso."""
    monkeypatch.setattr(coach, "COACH_DIR", tmp_path)
    monkeypatch.setattr(coach, "PROGRESS_FILE", tmp_path / "progress.md")

    ev1 = {"overall": 6, "level": "B1", "scores": {d: 6 for d in coach.DIMENSIONS}}
    ev2 = {"overall": 7, "level": "B2", "scores": {d: 7 for d in coach.DIMENSIONS}}
    dia = datetime.datetime(2026, 9, 2, 11, 26)

    coach._append_progress(ev1, dia, "call 1", "")
    coach._append_progress(ev2, dia.replace(hour=13), "call 2", "")

    linhas = [ln for ln in coach.PROGRESS_FILE.read_text(encoding="utf-8").splitlines()
              if ln.startswith("| 2026-09-02 |")]
    assert len(linhas) == 1
    assert "B2" in linhas[0]          # a linha do dia e a da call mais recente


# ── A hora e a da CALL, nunca a do relogio ────────────────────────────────────
# Defeito achado no primeiro reprocessamento (2026-09-02): a secao saiu como
# `## Call 1 - 21:53`, hora em que o coach rodou. A call das 08:39 virou Call 1 e
# a das 08:03 iria como Call 2 — a ordem do dia virou a ordem da fila. E a fila
# noturna roda as 20:00 e vira a meia-noite: uma call de terca processada 00:10
# de quarta abriria o relatorio de quarta.

def test_hora_vem_do_nome_do_arquivo_automatico():
    assert coach._hora_da_call("transcripts/2026-09-02_08-39_auto.txt") == \
        datetime.datetime(2026, 9, 2, 8, 39)


def test_hora_vem_tambem_do_fluxo_manual():
    """`english-coach.ps1` grava `transcript_en_YYYY-MM-DD_HH-MM.txt` — a data nao
    fica no inicio do nome, entao `re.match` nao servia."""
    assert coach._hora_da_call("transcript_en_2026-08-30_14-05.txt") == \
        datetime.datetime(2026, 8, 30, 14, 5)


@pytest.mark.parametrize("nome", ["qualquer.txt", "", "2026-13-45_99-99_auto.txt"])
def test_nome_fora_do_padrao_cai_no_relogio(nome):
    """Devolver None e o contrato: quem chama usa `datetime.now()`, que era o
    comportamento antigo. Nome invalido nao pode derrubar o relatorio."""
    assert coach._hora_da_call(nome) is None


def test_duas_calls_do_mesmo_dia_ordenam_pela_hora_da_call(sessoes):
    """A regressao concreta: 08-03 e 08-39 processadas na ordem inversa."""
    manha = coach._hora_da_call("transcripts/2026-09-02_08-03_auto.txt")
    tarde = coach._hora_da_call("transcripts/2026-09-02_08-39_auto.txt")
    assert manha < tarde
    assert coach._daily_session_file(manha) == coach._daily_session_file(tarde)


# ── Ordem das calls no arquivo do dia ─────────────────────────────────────────
# `_calls_no_dia` conta secoes, e contagem e ordem de chegada — a ordem da fila.
# Em 02/09 a call das 08:39 foi processada primeiro e virou Call 1; a das 08:03
# entrou como Call 2. Corrigir so o horario do cabecalho deixou o rotulo certo e
# a posicao errada.

def _dia_com(hora):
    return ("---\n"
            "date: 2026-09-02\ntype: english-coach-session\noverall: 7\nlevel: B2\n---\n\n"
            "# English Coach — 2026-09-02\n\n"
            f"## Call 1 — {hora}\n\n> corpo da call das {hora}\n")


def test_call_mais_cedo_entra_antes_mesmo_processada_depois():
    atual = _dia_com("08:39")
    saida = coach._montar_dia(atual, "## Call X — 08:03\n\n> corpo da call das 08:03",
                              "08:03")
    cabecalhos = [l for l in saida.splitlines() if l.startswith("## Call ")]
    assert cabecalhos == ["## Call 1 — 08:03", "## Call 2 — 08:39"]


def test_corpo_acompanha_a_secao_na_reordenacao():
    """Renumerar sem levar o corpo junto trocaria a avaliacao de uma call pela
    da outra — pior que a ordem errada."""
    saida = coach._montar_dia(_dia_com("08:39"),
                              "## Call X — 08:03\n\n> corpo da call das 08:03", "08:03")
    bloco1 = saida.split("## Call 2")[0]
    assert "corpo da call das 08:03" in bloco1
    assert "corpo da call das 08:39" not in bloco1


def test_call_mais_tarde_vai_para_o_fim():
    saida = coach._montar_dia(_dia_com("08:03"),
                              "## Call X — 14:20\n\n> corpo da tarde", "14:20")
    assert [l for l in saida.splitlines() if l.startswith("## Call ")] == \
        ["## Call 1 — 08:03", "## Call 2 — 14:20"]


def test_frontmatter_do_dia_sobrevive():
    saida = coach._montar_dia(_dia_com("08:39"),
                              "## Call X — 08:03\n\n> corpo", "08:03")
    assert saida.startswith("---\ndate: 2026-09-02\n")
    assert "# English Coach — 2026-09-02" in saida


def test_tres_calls_ficam_em_ordem_e_numeradas_de_1_a_3():
    d = _dia_com("08:39")
    d = coach._montar_dia(d, "## Call X — 14:20\n\n> tarde", "14:20")
    d = coach._montar_dia(d, "## Call X — 08:03\n\n> manha", "08:03")
    assert [l for l in d.splitlines() if l.startswith("## Call ")] == \
        ["## Call 1 — 08:03", "## Call 2 — 08:39", "## Call 3 — 14:20"]
