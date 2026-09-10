"""O relatorio das 07:00 tem que enxergar tarefa agendada que falhou.

A `TechColab English Coach` ficou 10 dias com resultado 1 no Agendador, falhando
toda segunda por ReadTimeout, e nada olhava para isso. Consertar o timeout resolve
aquela falha; o que impede a proxima e o sinal chegar ao Kelvin.

Estes testes cobrem os dois lados que costumam quebrar em separado: o gate precisa
ACUSAR falha de verdade, e precisa NAO acusar o que e normal — um aviso que dispara
todo dia e um aviso que ele desliga.
"""

import json

from agent import daily_report


def _fake_powershell(monkeypatch, linhas):
    """Substitui a chamada do PowerShell pela saida que ela produziria.

    `_check_scheduled_tasks` faz `import subprocess` dentro da funcao, entao quem
    manda e o modulo global, nao um atributo de daily_report.
    """
    import subprocess

    class _Res:
        stdout = json.dumps(linhas)

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Res())


def test_acusa_a_tarefa_que_falhou(monkeypatch):
    _fake_powershell(monkeypatch, [
        {"TaskName": "TechColab English Coach", "LastTaskResult": 1},
        {"TaskName": "TechColab Backlog Agent", "LastTaskResult": 0},
    ])
    ruins = daily_report._check_scheduled_tasks(
        ("TechColab English Coach", "TechColab Backlog Agent"))
    assert [r[0] for r in ruins] == ["TechColab English Coach"]
    assert ruins[0][1] == 1


def test_rodando_agora_e_nunca_rodou_nao_sao_falha(monkeypatch):
    # 267009 = em execucao, 267011 = ainda nao rodou. Tratar como falha faria o
    # aviso disparar em toda manha em que a fila ainda estivesse rodando.
    _fake_powershell(monkeypatch, [
        {"TaskName": "CallRecorder-Queue", "LastTaskResult": 267009},
        {"TaskName": "TeamMemoryAgent-Health", "LastTaskResult": 267011},
    ])
    assert daily_report._check_scheduled_tasks(
        ("CallRecorder-Queue", "TeamMemoryAgent-Health")) == []


def test_terminada_por_limite_de_tempo_e_falha(monkeypatch):
    # 267014 parece benigno e nao e: a tarefa foi cortada no meio do trabalho.
    _fake_powershell(monkeypatch, [
        {"TaskName": "TechColab Vault Index", "LastTaskResult": 267014},
    ])
    ruins = daily_report._check_scheduled_tasks(("TechColab Vault Index",))
    assert len(ruins) == 1
    assert "limite de tempo" in ruins[0][2]


def test_tarefa_que_sumiu_do_agendador_e_falha(monkeypatch):
    # Depois de reinstalar a maquina, tarefa que nao foi reimportada some calada.
    _fake_powershell(monkeypatch, [{"TaskName": "Outra", "LastTaskResult": 0}])
    ruins = daily_report._check_scheduled_tasks(("TechColab Backlog Agent",))
    assert ruins == [("TechColab Backlog Agent", None, "tarefa nao existe no Agendador")]


def test_os_lembretes_graficos_ficam_de_fora_da_lista():
    # Eles devolvem codigo nao-zero quando a caixa e fechada no X, o que e rotina.
    # Um gate que acusa todo dia nao acusa nada.
    for nome in ("CDMP Daily Study Reminder", "TechColab Todo Reminder",
                 "study-notify-diario", "D&A Vault - Morning Reminder"):
        assert nome not in daily_report.TAREFAS_QUE_DEVEM_PASSAR


def test_falha_do_powershell_nao_derruba_o_relatorio(monkeypatch):
    import subprocess

    def _boom(*a, **k):
        raise OSError("powershell nao encontrado")

    monkeypatch.setattr(subprocess, "run", _boom)
    assert daily_report._check_scheduled_tasks(("TechColab Backlog Agent",)) == []
