"""Tests for agent/create_idea.py — the chat-to-backlog capture bridge."""

import json
from datetime import date

import pytest

from agent import create_idea as ci
from backlog.store import BacklogStore


@pytest.fixture
def store(tmp_path):
    """A BacklogStore pointed at a temp dir — never touches the real vault."""
    return BacklogStore(tmp_path / "backlog items")


@pytest.fixture
def cli(tmp_path, monkeypatch):
    """Run main() against a temp backlog dir."""
    backlog_dir = tmp_path / "backlog items"
    monkeypatch.setattr(ci, "BACKLOG_DIR", backlog_dir)
    return backlog_dir


# -- build_payload: defaults and required fields ------------------------------

def test_title_is_required():
    with pytest.raises(ci.ValidationError, match="title is required"):
        ci.build_payload({"description": "sem titulo"})


def test_defaults_are_schema_valid():
    p = ci.build_payload({"title": "Ideia nova"})
    assert p["status"] == "backlog"
    assert p["priority"] == "média"
    assert p["todos"] == []
    assert p["is_bug"] is False
    assert p["blocked_by"] == []


def test_title_is_stripped_and_single_line():
    assert ci.build_payload({"title": "  Ideia  "})["title"] == "Ideia"
    with pytest.raises(ci.ValidationError, match="single line"):
        ci.build_payload({"title": "linha 1\nlinha 2"})


def test_unknown_field_is_rejected():
    """Guards against a session inventing a frontmatter key by hand."""
    with pytest.raises(ci.ValidationError, match="unknown field"):
        ci.build_payload({"title": "X", "prioridade": "alta"})


# -- build_payload: enum validation -------------------------------------------

@pytest.mark.parametrize("field,bad", [
    ("status", "em progresso"),
    ("priority", "urgente"),
    ("area", "marketing"),
    ("impacto", "enorme"),
    ("esforco", "gigante"),
])
def test_invalid_enum_is_rejected(field, bad):
    with pytest.raises(ci.ValidationError, match=f"invalid {field}"):
        ci.build_payload({"title": "X", field: bad})


def test_valid_enums_pass_through():
    p = ci.build_payload({
        "title": "X", "status": "em análise", "priority": "alta",
        "area": "business", "impacto": "alta", "esforco": "baixo",
    })
    assert p["status"] == "em análise"
    assert p["area"] == "business"
    assert p["esforco"] == "baixo"


def test_empty_enum_becomes_none():
    p = ci.build_payload({"title": "X", "area": "", "impacto": ""})
    assert p["area"] is None
    assert p["impacto"] is None


# -- build_payload: dates and to-dos ------------------------------------------

def test_due_date_parsed():
    assert ci.build_payload({"title": "X", "due_date": "2026-09-01"})["due_date"] == date(2026, 9, 1)


def test_invalid_due_date_is_rejected():
    with pytest.raises(ci.ValidationError, match="invalid due_date"):
        ci.build_payload({"title": "X", "due_date": "01/09/2026"})


def test_todos_accept_store_suffixes():
    """The to-do grammar must match what store._render_todos writes back."""
    p = ci.build_payload({"title": "X", "todos": [
        "Passo simples",
        "Com prazo @2026-09-01",
        "Pre-aprovado {auto}",
        "Um bug {bug}",
    ]})
    assert p["todos"][0]["text"] == "Passo simples"
    assert p["todos"][1]["due_date"] == "2026-09-01"
    assert p["todos"][2]["agente_autorizado"] is True
    assert p["todos"][3]["is_bug"] is True
    assert all(t["done"] is False for t in p["todos"])


def test_single_todo_string_is_wrapped():
    assert len(ci.build_payload({"title": "X", "todos": "Um passo"})["todos"]) == 1


def test_empty_todo_is_rejected():
    with pytest.raises(ci.ValidationError, match="cannot be empty"):
        ci.build_payload({"title": "X", "todos": ["  "]})


def test_blocked_by_string_is_wrapped():
    assert ci.build_payload({"title": "X", "blocked_by": "idea-001"})["blocked_by"] == ["idea-001"]


# -- Duplicate guard ----------------------------------------------------------

def test_find_duplicate_ignores_case_and_spacing(store):
    store.create(title="Hunting List — roteiro de visita")
    assert ci.find_duplicate(store, "hunting list —  ROTEIRO de visita") is not None
    assert ci.find_duplicate(store, "Outra ideia") is None


# -- main(): end-to-end through the CLI ---------------------------------------

def test_cli_creates_a_loadable_idea(cli, capsys):
    assert ci.main(["--title", "Ponte de captura", "--description", "Corpo",
                    "--todo", "Primeiro passo", "--area", "produto",
                    "--priority", "alta"]) == 0

    idea = BacklogStore(cli).load_by_id("idea-001")
    assert idea is not None
    assert idea.title == "Ponte de captura"
    assert idea.description == "Corpo"
    assert idea.area == "produto"
    assert idea.priority == "alta"
    assert idea.todos[0]["text"] == "Primeiro passo"
    assert "idea-001" in capsys.readouterr().out


def test_cli_prints_the_file_path(cli, capsys):
    ci.main(["--title", "Mostra o caminho"])
    assert "idea-001.md" in capsys.readouterr().out


def test_cli_ids_increment(cli):
    ci.main(["--title", "Primeira"])
    ci.main(["--title", "Segunda"])
    assert {i.id for i in BacklogStore(cli).load_all()} == {"idea-001", "idea-002"}


def test_cli_rejects_duplicate_title(cli, capsys):
    ci.main(["--title", "Mesma ideia"])
    assert ci.main(["--title", "mesma ideia"]) == ci.EXIT_DUPLICATE
    assert "already exists" in capsys.readouterr().out
    assert len(BacklogStore(cli).load_all()) == 1


def test_cli_allow_duplicate_overrides(cli):
    ci.main(["--title", "Mesma ideia"])
    assert ci.main(["--title", "Mesma ideia", "--allow-duplicate"]) == 0
    assert len(BacklogStore(cli).load_all()) == 2


def test_cli_invalid_input_returns_error_code(cli, capsys):
    assert ci.main(["--title", "linha 1\nlinha 2"]) == ci.EXIT_INVALID
    assert "[ERROR]" in capsys.readouterr().out
    assert not list(cli.glob("idea-*.md"))


def test_cli_dry_run_writes_nothing(cli, capsys):
    assert ci.main(["--title", "Só um teste", "--dry-run"]) == 0
    assert "DRY-RUN" in capsys.readouterr().out
    assert not list(cli.glob("idea-*.md"))


def test_cli_json_payload_roundtrips_accents(cli, tmp_path):
    """The JSON path exists so PT-BR text survives without shell quoting."""
    payload = {
        "title": "Integração — validação de ação",
        "description": "Linha 1\nLinha 2 com acentuação",
        "todos": ["Revisar relatório @2026-09-30"],
        "status": "em análise",
        "area": "dados & IA",
        "origin": "Projects/BIA-004/nota.md",
    }
    f = tmp_path / "payload.json"
    f.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    assert ci.main(["--json", str(f)]) == 0
    idea = BacklogStore(cli).load_by_id("idea-001")
    assert idea.title == "Integração — validação de ação"
    assert "acentuação" in idea.description
    assert idea.status == "em análise"
    assert idea.area == "dados & IA"
    assert idea.origin == "Projects/BIA-004/nota.md"
    assert idea.todos[0]["due_date"] == "2026-09-30"


def test_cli_json_stdin(cli, monkeypatch, capsys):
    import io
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"title": "Via stdin"})))
    assert ci.main(["--json", "-"]) == 0
    assert BacklogStore(cli).load_by_id("idea-001").title == "Via stdin"


def test_cli_malformed_json_is_rejected(cli, tmp_path, capsys):
    f = tmp_path / "bad.json"
    f.write_text("{not json", encoding="utf-8")
    assert ci.main(["--json", str(f)]) == ci.EXIT_INVALID
    assert "invalid JSON" in capsys.readouterr().out


def test_cli_flags_bug_and_auto(cli):
    ci.main(["--title", "Um bug", "--bug", "--auto"])
    idea = BacklogStore(cli).load_by_id("idea-001")
    assert idea.is_bug is True
    assert idea.agente_autorizado is True
