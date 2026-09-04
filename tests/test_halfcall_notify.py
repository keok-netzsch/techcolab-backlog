"""O aviso de meia conversa tem que chegar ao Kelvin NO DIA da call.

Companheiro de `test_captura_meia_conversa.py`, que trava a DETECCAO. Este trava a
ENTREGA, que e a metade que faltava.

Em 03/09 a deteccao existia em dois lugares e funcionou nos dois: o
`*** ALERTA: canal 1 sem fala ***` do `capture_multi` (record.log, sem leitor) e o
gate do relatorio das 07:00. O Kelvin soube em 04/09, um dia depois, e so porque
perguntou. Duas calls tinham ido para o disco com o canal do interlocutor em
silencio digital.

O que este arquivo protege:
  - o aviso aparece para gravacao recente meia-conversa
  - o aviso NAO repete a mesma gravacao a cada call seguinte
  - o aviso e silencioso quando esta tudo certo (senao para de ser lido)
  - a regra de "meia conversa" continua vindo de `transcript_quality.canal_mudo`,
    nao de uma segunda copia que pode divergir
"""
import json
import sys
import time
from pathlib import Path

import pytest

CR = Path(__file__).parent.parent / "call-recorder"
if str(CR) not in sys.path:
    sys.path.insert(0, str(CR))

import halfcall_notify as hn  # noqa: E402


def _sidecar(tmp_path: Path, stem: str, kelvin, interlocutor, idade_h=0.0,
             classified=False):
    nome = f"{stem}.pending.json" + (".classified" if classified else "")
    p = tmp_path / nome
    p.write_text(json.dumps({
        "wav": f"{stem}.wav",
        "source": "autocapture",
        "duration_s": 2917,
        "channel_profile": {
            "Kelvin": {"active_pct": kelvin, "dynamic_db": 40.0},
            "Interlocutor": {"active_pct": interlocutor, "dynamic_db": 40.0},
        },
    }), encoding="utf-8")
    if idade_h:
        antigo = time.time() - idade_h * 3600
        import os
        os.utime(p, (antigo, antigo))
    return p


# ── O caso real: a call do Genesis, 03/09 09:34 ───────────────────────────────

def test_gravacao_meia_conversa_recente_vira_aviso(tmp_path):
    _sidecar(tmp_path, "2026-09-03_09-34_auto", 4.9, 0.0)
    achados = hn.pendentes(rdir=tmp_path)
    assert [s for s, _ in achados] == ["2026-09-03_09-34_auto"]
    assert "interlocutor" in achados[0][1].lower()


def test_corpo_diz_que_nao_da_para_recuperar(tmp_path):
    """O texto tem que fechar a duvida que ele teve em 04/09.

    A primeira pergunta dele foi "sera que o audio existe no wav e so nao foi
    transcrito?". Se a caixa nao responder isso, ele vai perguntar de novo.
    """
    _sidecar(tmp_path, "2026-09-03_09-34_auto", 4.9, 0.0)
    texto = hn.corpo(hn.pendentes(rdir=tmp_path))
    assert "METADE DA CONVERSA" in texto
    assert "2026-09-03_09-34_auto" in texto
    assert "recuperar" in texto


def test_call_sadia_e_silenciosa(tmp_path):
    """Caixa que abre em call boa deixa de ser lida."""
    _sidecar(tmp_path, "2026-09-03_15-38_auto", 1.4, 27.0)
    assert hn.pendentes(rdir=tmp_path) == []
    assert hn.corpo([]) == ""


# ── Nao repetir: o modo de falha que mata lembrete ────────────────────────────

def test_gravacao_ja_anunciada_nao_volta(tmp_path):
    """Sem isto, a mesma call reapareceria ao fim de toda call das proximas 24h."""
    _sidecar(tmp_path, "2026-09-03_09-34_auto", 4.9, 0.0)
    achados = hn.pendentes(rdir=tmp_path)
    assert achados

    hn.marcar([s for s, _ in achados], rdir=tmp_path)
    assert hn.pendentes(rdir=tmp_path) == []


def test_ler_nao_gasta_o_anuncio(tmp_path):
    """`pendentes()` so le. Quem marca e `marcar()`, chamado pelo autocapture.

    Custo real, 04/09: a primeira versao marcava dentro do `main()`. Um
    `notify.ps1 -Profile capture-half-call -WhatIf`, que existe justamente para
    ensaiar sem abrir janela, consumiu o anuncio da call do Genesis — o disparo
    real seguinte teria ficado mudo por causa de um teste.
    """
    _sidecar(tmp_path, "2026-09-03_08-53_auto", 30.0, 0.0)
    assert hn.pendentes(rdir=tmp_path)
    assert hn.pendentes(rdir=tmp_path)          # de novo, ainda la
    assert not list(tmp_path.glob("*" + hn.MARCA))


def test_main_nao_marca(tmp_path, monkeypatch, capsys):
    """A mesma garantia no ponto que o notify.ps1 chama de verdade."""
    _sidecar(tmp_path, "2026-09-03_09-34_auto", 4.9, 0.0)
    monkeypatch.setattr(hn, "RECORDINGS", tmp_path)
    assert hn.main([]) == 0
    assert "METADE DA CONVERSA" in capsys.readouterr().out
    assert not list(tmp_path.glob("*" + hn.MARCA))


def test_gravacao_velha_nao_entra(tmp_path):
    """Janela de 24h: o disparo e por call, nao um resumo do mes."""
    _sidecar(tmp_path, "2026-08-27_14-20_auto", 78.4, 0.0, idade_h=200)
    assert hn.pendentes(rdir=tmp_path) == []


# ── Bordas que nao podem virar alarme ─────────────────────────────────────────

def test_sidecar_classified_tambem_conta(tmp_path):
    """O classify renomeia o sidecar; o aviso tem que seguir o arquivo."""
    _sidecar(tmp_path, "2026-09-01_07-55_auto", 86.1, 0.0, classified=True)
    assert [s for s, _ in hn.pendentes(rdir=tmp_path)] == ["2026-09-01_07-55_auto"]


def test_os_dois_sidecars_da_mesma_call_contam_uma_vez(tmp_path):
    """`.pending.json` e `.pending.json.classified` convivem na pasta real."""
    _sidecar(tmp_path, "2026-09-03_09-34_auto", 4.9, 0.0)
    _sidecar(tmp_path, "2026-09-03_09-34_auto", 4.9, 0.0, classified=True)
    assert len(hn.pendentes(rdir=tmp_path)) == 1


def test_pasta_inexistente_nao_derruba(tmp_path):
    assert hn.pendentes(rdir=tmp_path / "nao-existe") == []


def test_sidecar_ilegivel_nao_derruba(tmp_path):
    (tmp_path / "2026-09-03_09-34_auto.pending.json").write_text("{ truncado",
                                                                 encoding="utf-8")
    assert hn.pendentes(rdir=tmp_path) == []


def test_regra_vem_do_transcript_quality(tmp_path, monkeypatch):
    """Uma regra, nao duas.

    Se alguem reimplementar "meia conversa" aqui dentro, este teste passa a
    falhar — que e o ponto. Duas copias divergem, e a que fica errada e sempre a
    que ninguem roda.
    """
    import transcript_quality as tq

    chamadas = []
    real = tq.canal_mudo
    monkeypatch.setattr(tq, "canal_mudo",
                        lambda base, rdir=None: (chamadas.append(base),
                                                 real(base, rdir=rdir))[1])
    _sidecar(tmp_path, "2026-09-03_09-34_auto", 4.9, 0.0)
    hn.pendentes(rdir=tmp_path)
    assert chamadas == ["2026-09-03_09-34_auto"]


# ── O perfil existe no motor unico (padrao 8: nao e o sexto script de toast) ──

def test_perfil_registrado_no_notify_config():
    cfg = json.loads((Path(__file__).parent.parent / "scripts" /
                      "notify-config.json").read_text(encoding="utf-8"))
    p = cfg["profiles"]["capture-half-call"]
    assert p["mode"] == "messagebox"        # Focus Assist engole balloon
    assert p["messageScript"] == "scripts/notify-body/capture-half-call-body.ps1"
    assert (Path(__file__).parent.parent / p["messageScript"]).exists()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
