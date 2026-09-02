"""Tests for backlog/daily_log.py

Since 2026-08-26 (idea-067) entries go to the vault's canonical daily note
(`Daily/YYYY-MM-DD.md`, `type: daily`) under a "## 🗂️ Backlog" section, instead
of the retired parallel diary at `Log/diario-YYYY-MM-DD.md`.
"""

from datetime import date

import pytest

from backlog.schema import Idea


@pytest.fixture
def daily_dir(tmp_path, monkeypatch):
    """Redirect the daily note into a temp dir."""
    import backlog.daily_log as dl
    daily = tmp_path / "Daily"
    daily.mkdir()
    monkeypatch.setattr(
        dl, "_daily_note_path",
        lambda today=None: daily / f"{(today or date.today()).isoformat()}.md",
    )
    return daily


def _note(daily_dir):
    return (daily_dir / f"{date.today().isoformat()}.md").read_text(encoding="utf-8")


def _make_idea(**kwargs):
    defaults = dict(id="idea-001", title="Ideia de teste", status="backlog")
    defaults.update(kwargs)
    return Idea(**defaults)


def test_log_entry_creates_daily_note(daily_dir):
    from backlog.daily_log import log_entry
    log_entry("criada", _make_idea())
    files = list(daily_dir.iterdir())
    assert len(files) == 1
    assert files[0].name == f"{date.today().isoformat()}.md"


def test_new_note_uses_canonical_daily_type(daily_dir):
    """`daily`, not the deprecated `daily-log` (2026-07-29 type-taxonomy ADR)."""
    from backlog.daily_log import log_entry
    log_entry("criada", _make_idea())
    content = _note(daily_dir)
    assert "type: daily\n" in content
    assert "daily-log" not in content
    assert "## 🗂️ Backlog" in content


def test_log_entry_label_criada(daily_dir):
    from backlog.daily_log import log_entry
    log_entry("criada", _make_idea())
    content = _note(daily_dir)
    assert "`CRIADA`" in content
    assert "idea-001" in content
    assert "Ideia de teste" in content


def test_log_entry_label_concluida(daily_dir):
    from backlog.daily_log import log_entry
    log_entry("concluida", _make_idea(status="concluído"))
    assert "`CONCLUÍDA`" in _note(daily_dir)


def test_log_entry_label_todo(daily_dir):
    from backlog.daily_log import log_entry
    log_entry("todo_concluido", _make_idea(), "Revisar dados")
    content = _note(daily_dir)
    assert "`TO-DO`" in content
    assert "Revisar dados" in content


def test_log_entry_appends_multiple(daily_dir):
    from backlog.daily_log import log_entry
    idea = _make_idea()
    log_entry("criada", idea)
    log_entry("alterada", idea, "status: backlog -> em análise")
    content = _note(daily_dir)
    assert content.count("`CRIADA`") == 1
    assert content.count("`ALTERADA`") == 1
    assert content.count("## 🗂️ Backlog") == 1


def test_log_entry_detail_appended(daily_dir):
    from backlog.daily_log import log_entry
    log_entry("alterada", _make_idea(), "status: backlog -> em análise")
    assert "status: backlog -> em análise" in _note(daily_dir)


def test_entry_inserted_into_existing_backlog_section(daily_dir):
    """An existing note keeps its other sections, and the next header stays separated."""
    from backlog.daily_log import log_entry
    path = daily_dir / f"{date.today().isoformat()}.md"
    path.write_text(
        "---\ndate: 2026-08-26\ntype: daily\n---\n\n"
        "# Wednesday\n\n"
        "## 🎯 Foco de hoje\n- item de foco\n\n"
        "## 🗂️ Backlog\n- 09:00 `CRIADA` [idea-001] Anterior\n\n"
        "## ✅ Feito\n- algo feito\n",
        encoding="utf-8",
    )
    log_entry("concluida", _make_idea(id="idea-002", title="Nova"))
    content = _note(daily_dir)
    assert "- item de foco" in content
    assert "- algo feito" in content
    assert "[idea-001] Anterior" in content
    # new entry lands inside the Backlog section, above the next header
    backlog_part = content.split("## 🗂️ Backlog")[1].split("## ")[0]
    assert "[idea-002] Nova" in backlog_part
    # blank line preserved before the following section
    assert "\n\n## ✅ Feito" in content


@pytest.mark.daily_path_real
def test_read_log_lines_reads_new_and_legacy(tmp_path, monkeypatch):
    """One reader covers both locations, so history survives the move.

    Ate 2026-09-02 este teste patchava VAULT_ROOT e passava, enquanto o escritor
    ja usava VAULT_BASE — o teste media uma coisa e a producao fazia outra. Agora
    os dois saem de `_daily_note_path`, e o patch e no mesmo lugar que ela le.
    """
    import backlog.daily_log as dl
    monkeypatch.setattr(dl, "VAULT_BASE", tmp_path)
    monkeypatch.setattr(dl, "VAULT_ROOT", tmp_path)
    (tmp_path / "Daily").mkdir()
    (tmp_path / "Log").mkdir()

    new_day = date(2026, 8, 27)
    (tmp_path / "Daily" / f"{new_day.isoformat()}.md").write_text(
        "---\ntype: daily\n---\n\n# Thu\n\n"
        "## 🎯 Foco\n- nao e log\n\n"
        "## 🗂️ Backlog\n- 10:00 `CRIADA` [idea-100] Nova\n\n"
        "## ✅ Feito\n- tambem nao e log\n",
        encoding="utf-8",
    )
    old_day = date(2026, 5, 18)
    (tmp_path / "Log" / f"diario-{old_day.isoformat()}.md").write_text(
        "---\ntype: daily\n---\n\n# Log do dia — 18/05/2026\n\n"
        "- 11:43 `CRIADA` [idea-010] Antiga\n",
        encoding="utf-8",
    )

    new_lines = dl.read_log_lines(new_day)
    assert new_lines == ["- 10:00 `CRIADA` [idea-100] Nova"]
    # only the Backlog section — other sections must not leak in
    assert not any("nao e log" in ln for ln in new_lines)

    old_lines = dl.read_log_lines(old_day)
    assert old_lines == ["- 11:43 `CRIADA` [idea-010] Antiga"]

    assert dl.read_log_lines(date(2020, 1, 1)) == []


def test_section_created_when_missing_from_existing_note(daily_dir):
    from backlog.daily_log import log_entry
    path = daily_dir / f"{date.today().isoformat()}.md"
    path.write_text(
        "---\ndate: 2026-08-26\ntype: daily\n---\n\n# Wednesday\n\n"
        "## 🎯 Foco de hoje\n- so foco\n",
        encoding="utf-8",
    )
    log_entry("criada", _make_idea())
    content = _note(daily_dir)
    assert "- so foco" in content
    assert "## 🗂️ Backlog" in content
    assert "[idea-001]" in content


# ── Real path resolution ─────────────────────────────────────────────────────
# Every other test here monkeypatches _daily_note_path away, which is exactly how
# the wrong root survived: the function resolved to <vault>/App/Personal toolkit/
# Daily/ instead of the vault-root Daily/, so entries landed in a folder nothing
# reads and "diario unico" (Toolkit 2.0 Pacote 2) never actually happened.

@pytest.mark.daily_path_real
def test_daily_note_resolves_under_vault_base():
    from pathlib import Path

    from backlog.daily_log import _daily_note_path
    from config import VAULT_BASE, VAULT_ROOT

    # Hierarquia ano/mes desde 2026-09-02. O que este teste protege continua
    # sendo o mesmo: a nota mora sob VAULT_BASE, nunca sob VAULT_ROOT.
    resolved = _daily_note_path(date(2026, 9, 1))
    assert resolved == Path(VAULT_BASE) / "Daily" / "2026" / "09" / "2026-09-01.md"
    # VAULT_ROOT is the app's working area, one level deeper — never the daily note's home.
    assert Path(VAULT_ROOT) not in resolved.parents


def test_leitor_e_escritor_usam_o_mesmo_caminho(tmp_path, monkeypatch):
    """O defeito de 2026-09-02, travado.

    O escritor gravava em VAULT_BASE/Daily e o leitor procurava em
    VAULT_ROOT/Daily. Como VAULT_ROOT/Daily nao existia, toda leitura caia no
    fallback do diario legado — que parou de ser escrito em 26/08. Meeting Prep,
    dashboard e a aba Backlog ficaram uma semana sem atividade diaria, sem erro.

    Este teste escreve pelo caminho de producao e le pelo caminho de producao. Se
    os dois divergirem de novo, ele quebra aqui.
    """
    import backlog.daily_log as dl

    monkeypatch.setattr(dl, "VAULT_BASE", tmp_path)
    monkeypatch.setattr(dl, "VAULT_ROOT", tmp_path / "App" / "Personal toolkit")
    monkeypatch.setattr(dl, "_daily_note_path",
                        lambda today=None: tmp_path / "Daily" / f"{(today or date.today()).isoformat()}.md")

    dia = date(2026, 9, 2)
    caminho = dl._daily_note_path(dia)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text("---\ntype: daily\n---\n\n## 🗂️ Backlog\n"
                       "- 09:00 `CRIADA` [idea-200] Real\n", encoding="utf-8")

    assert dl.read_log_lines(dia) == ["- 09:00 `CRIADA` [idea-200] Real"]


def test_leitura_nao_cria_pasta(tmp_path, monkeypatch):
    """Ler nao pode ter efeito colateral: um dashboard abrindo nao cria Daily/."""
    import backlog.daily_log as dl

    monkeypatch.setattr(dl, "VAULT_BASE", tmp_path)
    monkeypatch.setattr(dl, "VAULT_ROOT", tmp_path)
    monkeypatch.setattr(dl, "_daily_note_path",
                        lambda today=None: tmp_path / "Daily" / f"{(today or date.today()).isoformat()}.md")

    assert dl.read_log_lines(date(2026, 9, 2)) == []
    assert not (tmp_path / "Daily").exists()


@pytest.mark.daily_path_real
def test_leitor_aceita_os_dois_formatos(tmp_path, monkeypatch):
    """Hierarquia ano/mes desde 2026-09-02, mas o formato plano nao pode sumir.

    O `Daily/` nao e escrito so por este repo: o techcolab-vault-mcp e a skill
    obsidian-second-brain gravam nele tambem, e skill reinstalada volta a gravar
    plano sem avisar. Leitor que so entende a hierarquia perderia essa nota em
    silencio — o mesmo defeito que custou uma semana de Meeting Prep vazio.
    """
    import backlog.daily_log as dl

    monkeypatch.setattr(dl, "VAULT_BASE", tmp_path)
    monkeypatch.setattr(dl, "VAULT_ROOT", tmp_path)

    cabecalho = "---\ntype: daily\n---\n\n## 🗂️ Backlog\n"

    hier = tmp_path / "Daily" / "2026" / "09" / "2026-09-02.md"
    hier.parent.mkdir(parents=True)
    hier.write_text(cabecalho + "- 09:00 `CRIADA` [idea-300] Na hierarquia\n",
                    encoding="utf-8")

    plana = tmp_path / "Daily" / "2026-09-03.md"
    plana.write_text(cabecalho + "- 10:00 `CRIADA` [idea-301] No formato plano\n",
                     encoding="utf-8")

    assert dl.read_log_lines(date(2026, 9, 2)) == ["- 09:00 `CRIADA` [idea-300] Na hierarquia"]
    assert dl.read_log_lines(date(2026, 9, 3)) == ["- 10:00 `CRIADA` [idea-301] No formato plano"]


@pytest.mark.daily_path_real
def test_nota_nova_nasce_na_hierarquia(tmp_path, monkeypatch):
    import backlog.daily_log as dl

    monkeypatch.setattr(dl, "VAULT_BASE", tmp_path)
    alvo = dl.daily_note_path(date(2026, 9, 4), para_escrita=True)
    assert alvo == tmp_path / "Daily" / "2026" / "09" / "2026-09-04.md"


@pytest.mark.daily_path_real
def test_nota_que_ja_existe_plana_nao_e_partida_em_duas(tmp_path, monkeypatch):
    """Se o dia ja tem nota plana, escrever continua nela.

    Senao o mesmo dia ficaria em dois arquivos — metade do registro em cada.
    """
    import backlog.daily_log as dl

    monkeypatch.setattr(dl, "VAULT_BASE", tmp_path)
    plana = tmp_path / "Daily" / "2026-09-05.md"
    plana.parent.mkdir(parents=True)
    plana.write_text("---\ntype: daily\n---\n", encoding="utf-8")

    assert dl.daily_note_path(date(2026, 9, 5), para_escrita=True) == plana
