"""Gravacao com um canal mudo tem que ser DETECTADA e ESCALADA.

Existe por causa de 2026-09-03. O `capture_multi` gritava
"*** ALERTA: canal 1 sem fala ***" no record.log desde 27/08, corretamente, a
cada ocorrencia. Nada consumia esse alerta: nem health check, nem notificacao,
nem gate. Sete gravacoes sairam pela metade em sete dias - uma de 115 min com a
Ana - e quatro viraram nota no vault com um lado so da conversa antes de alguem
olhar um log.

A licao que este arquivo trava nao e sobre COM nem sobre WASAPI, que sao a causa
daquela vez. E sobre a forma do defeito: **deteccao que nao escala e o mesmo que
nao detectar.** Se um dia a captura falhar por outro motivo, o sinal continua
chegando ao Kelvin.

O par oposto (canal contaminado, soma > 120%) ja tinha gate desde 02/09, e o
comentario do proprio `transcript_quality.py` registrava que a metade muda
ficara de fora. As duas falhas foram vistas no mesmo dia; so uma virou codigo.
"""
import json
import sys
from pathlib import Path

import pytest

CR = Path(__file__).parent.parent / "call-recorder"
if str(CR) not in sys.path:
    sys.path.insert(0, str(CR))

import transcript_quality as tq  # noqa: E402


def _sidecar(tmp_path: Path, stem: str, kelvin, interlocutor, classified=False):
    nome = f"{stem}.pending.json" + (".classified" if classified else "")
    (tmp_path / nome).write_text(json.dumps({
        "wav": f"{stem}.wav",
        "source": "autocapture",
        "duration_s": 1800,
        "channel_profile": {
            "Kelvin": {"active_pct": kelvin, "dynamic_db": 40.0},
            "Interlocutor": {"active_pct": interlocutor, "dynamic_db": 40.0},
        },
    }), encoding="utf-8")
    return tmp_path


# ── O caso real de 03/09 ───────────────────────────────────────────────────────

def test_interlocutor_zerado_e_meia_conversa(tmp_path):
    """O caso das 7: o lado do Kelvin gravou, o do outro voltou zerado."""
    _sidecar(tmp_path, "2026-09-03_07-59_auto", 61.8, 0.0)
    mudo, detalhe = tq.canal_mudo("2026-09-03_07-59_auto", rdir=tmp_path)
    assert mudo
    assert "interlocutor" in detalhe.lower()


def test_kelvin_zerado_tambem_conta(tmp_path):
    """A assimetria inversa e igualmente uma call pela metade."""
    _sidecar(tmp_path, "2026-09-03_10-00_auto", 0.0, 52.6)
    mudo, detalhe = tq.canal_mudo("2026-09-03_10-00_auto", rdir=tmp_path)
    assert mudo
    assert "Kelvin" in detalhe


def test_le_o_sidecar_depois_do_classify(tmp_path):
    """`classify.py` renomeia para `.classified` — o gate tem que seguir.

    Sem isto o gate silenciaria exatamente quando a gravacao avanca no pipeline,
    que e quando ela esta prestes a virar nota.
    """
    _sidecar(tmp_path, "2026-09-01_07-55_auto", 86.1, 0.0, classified=True)
    mudo, _ = tq.canal_mudo("2026-09-01_07-55_auto", rdir=tmp_path)
    assert mudo


# ── O que NAO pode acusar: gate que acusa tudo nao acusa nada ─────────────────

def test_call_normal_nao_acusa(tmp_path):
    _sidecar(tmp_path, "2026-09-02_16-04_auto", 6.1, 52.6)
    assert tq.canal_mudo("2026-09-02_16-04_auto", rdir=tmp_path)[0] is False


def test_call_contaminada_nao_e_meia_conversa(tmp_path):
    """Soma 133% e o defeito OPOSTO, e ja tem gate proprio.

    Um sinal que acusasse os dois casos com a mesma frase mandaria o Kelvin
    procurar o problema errado: contaminacao pede fone, canal mudo pede
    investigar a captura.
    """
    _sidecar(tmp_path, "2026-08-28_11-46_auto", 66.9, 66.5)
    assert tq.canal_mudo("2026-08-28_11-46_auto", rdir=tmp_path)[0] is False
    assert tq.contaminacao_de_canal("2026-08-28_11-46_auto", rdir=tmp_path)[0] == "grave"


def test_gravacao_vazia_nos_dois_canais_nao_acusa(tmp_path):
    """Silencio dos dois lados e call vazia, nao meia conversa.

    Acusar aqui encheria o relatorio de 07:00 com gravacao sem interesse, e um
    relatorio ruidoso deixa de ser lido — que e como este defeito sobreviveu.
    """
    _sidecar(tmp_path, "2026-09-03_08-53_auto", 0.0, 0.0)
    assert tq.canal_mudo("2026-09-03_08-53_auto", rdir=tmp_path)[0] is False


def test_sem_sidecar_nao_acusa(tmp_path):
    """Ausencia de dado nao e acusacao — mesma regra da contaminacao."""
    assert tq.canal_mudo("2026-01-01_00-00_auto", rdir=tmp_path)[0] is False


def test_sidecar_sem_channel_profile_nao_acusa(tmp_path):
    """Gravacao anterior ao channel_profile (as de 27/08) nao pode virar alarme."""
    (tmp_path / "2026-08-27_08-01_auto.pending.json").write_text(
        json.dumps({"wav": "x.wav", "duration_s": 700}), encoding="utf-8")
    assert tq.canal_mudo("2026-08-27_08-01_auto", rdir=tmp_path)[0] is False


def test_sidecar_ilegivel_nao_derruba_o_gate(tmp_path):
    """Health check das 07:00 nao pode morrer por um json truncado."""
    (tmp_path / "2026-09-03_09-34_auto.pending.json").write_text("{ truncado",
                                                                encoding="utf-8")
    assert tq.canal_mudo("2026-09-03_09-34_auto", rdir=tmp_path)[0] is False


# ── A parte que importa: o sinal ESCALA ──────────────────────────────────────

def test_o_health_check_das_07h_reporta_meia_conversa(tmp_path, capsys, monkeypatch):
    """O ponto do arquivo inteiro.

    `canal_mudo` funcionar e necessario e nao e suficiente: o alerta do
    `capture_multi` tambem funcionava. O que faltou foi alguem contar ao Kelvin.
    Este teste exercita o trecho do `daily_report` que faz isso.
    """
    import agent.daily_report as dr

    _sidecar(tmp_path, "2026-09-03_07-59_auto", 61.8, 0.0)
    _sidecar(tmp_path, "2026-09-03_16-00_auto", 10.0, 48.0)  # sadia, nao aparece

    saida = []
    monkeypatch.setattr(dr, "safe_print", lambda m: saida.append(str(m)))
    dr._check_capture_quality(tmp_path, lambda p: 1.0)

    texto = "\n".join(saida)
    assert "METADE DA CONVERSA" in texto
    assert "2026-09-03_07-59_auto" in texto
    assert "2026-09-03_16-00_auto" not in texto


def test_gravacao_antiga_nao_reaparece_todo_dia(tmp_path, capsys, monkeypatch):
    """Alerta que repete para sempre vira ruido e para de ser lido."""
    import agent.daily_report as dr

    _sidecar(tmp_path, "2026-08-27_14-20_auto", 78.4, 0.0)
    saida = []
    monkeypatch.setattr(dr, "safe_print", lambda m: saida.append(str(m)))
    dr._check_capture_quality(tmp_path, lambda p: 999.0)   # velha

    assert "METADE DA CONVERSA" not in "\n".join(saida)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
