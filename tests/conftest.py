"""Shared pytest configuration — sys.path, e o vault real fora do alcance dos testes."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "daily_path_real: o teste verifica o proprio calculo do caminho da nota "
        "diaria, entao a isolacao autouse do conftest sairia do caminho dele")


@pytest.fixture(autouse=True)
def _daily_note_isolada(tmp_path, monkeypatch, request):
    """Nenhum teste escreve na nota diaria do vault de verdade.

    Descoberto em 2026-09-02: as 131 linhas do `## Backlog` da daily daquele dia
    eram TODAS de teste (`idea-001`, `idea-002`), e o mesmo tinha acontecido em
    01/09. A fixture `cli` do test_create_idea isolava `BACKLOG_DIR` mas nao o
    `log_entry`, que resolve o caminho por `config.VAULT_BASE` — entao cada rodada
    da suite carimbava ~10 linhas no registro real do Kelvin.

    Autouse e no conftest de proposito. Isolar caso a caso ja falhou uma vez: quem
    escrever o proximo teste que chame `log_entry` nao vai lembrar da fixture, e o
    vazamento e silencioso — o teste passa e o vault suja.
    """
    if request.node.get_closest_marker("daily_path_real"):
        yield
        return

    try:
        from backlog import daily_log
    except Exception:
        yield
        return

    # Patch em `daily_note_path`, nao no wrapper `_daily_note_path`: e o
    # chokepoint por onde escrita E leitura passam. Patchear so o wrapper deixava
    # aberto quem chamasse a funcao de baixo direto.
    from datetime import date as _date

    destino = tmp_path / "vault-de-teste" / "Daily"

    def _isolado(d=None, para_escrita=False):
        d = d or _date.today()
        return destino / f"{d.year:04d}" / f"{d.month:02d}" / f"{d.isoformat()}.md"

    monkeypatch.setattr(daily_log, "daily_note_path", _isolado)
    monkeypatch.setattr(daily_log, "_daily_note_path",
                        lambda today=None: _isolado(today, para_escrita=True))
    yield
