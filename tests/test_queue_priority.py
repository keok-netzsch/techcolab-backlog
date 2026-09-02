"""Stefan e Alberto furam a fila de transcricao.

Decisao do Kelvin em 2026-09-02: "as calls com Stefan e Alberto tem prioridade
maxima". A fila era `sorted(glob("*.job.json"))`, ou seja, estritamente
cronologica pelo nome do arquivo. Com 214 min de audio parado no lote, uma call
com o chefe gravada as 08:00 saia horas depois de tudo que fosse anterior a ela.

O que estes testes travam:

  1. o job do chefe vem primeiro mesmo sendo o mais NOVO da fila (a ordenacao
     antiga o colocaria por ultimo);
  2. o titulo da janela do Teams basta - `Weekly Sync Kelvin <-> Stefan` nao
     tem `kind`/`target` resolvido, porque classify.py marca `needs_review`;
  3. o alias `Jour Fixe KO <> AR` conta como Alberto sem citar o nome dele;
  4. entre jobs de mesma prioridade a ordem continua cronologica - a mudanca
     nao pode embaralhar o resto da fila;
  5. job ilegivel nao derruba a ordenacao (vai para o fim, e quem trata o erro
     continua sendo o laco de processamento).

LIMITE que o teste tambem trava: prioridade mexe na ORDEM, nunca no DESTINO.
Existem dois Stefan no vault (Lautenschlager e Weiss) e um titulo com o primeiro
nome so nao distingue os dois. Errar a ordem custa uma call na frente da outra;
errar o destino escreve na nota da pessoa errada.
"""
import json
import sys
from pathlib import Path

CR = Path(__file__).resolve().parent.parent / "call-recorder"
sys.path.insert(0, str(CR))

import process  # noqa: E402


def _job(tmp, name, **fields):
    p = tmp / f"{name}.job.json"
    p.write_text(json.dumps(fields), encoding="utf-8")
    return p


def _ordem(tmp):
    return [p.name for p in sorted(
        tmp.glob("*.job.json"),
        key=lambda p: (process._job_priority(process._load_job_quiet(p)), p.name))]


def test_titulo_com_stefan_fura_a_fila_mesmo_sendo_o_mais_novo(tmp_path):
    _job(tmp_path, "2026-08-27_08-15_auto", meeting="Daily BIZ")
    _job(tmp_path, "2026-08-28_09-56_auto", meeting="Morales, Hernan")
    _job(tmp_path, "2026-09-02_08-03_auto",
         meeting="Meeting join | Weekly Sync Kelvin <-> Stefan | Microsoft Teams")

    assert _ordem(tmp_path)[0] == "2026-09-02_08-03_auto.job.json"


def test_alias_jour_fixe_conta_como_alberto_sem_citar_o_nome(tmp_path):
    _job(tmp_path, "2026-08-01_08-00_auto", meeting="Daily PM")
    _job(tmp_path, "2026-08-27_15-34_auto", meeting="Jour Fixe KO <> AR")

    assert _ordem(tmp_path)[0] == "2026-08-27_15-34_auto.job.json"


def test_target_resolvido_pelo_classify_tambem_prioriza(tmp_path):
    _job(tmp_path, "2026-08-01_08-00_auto", meeting="Daily PM")
    _job(tmp_path, "2026-08-30_10-00_auto", kind="manager",
         target="Stefan-Lautenschlager", meeting="")

    assert _ordem(tmp_path)[0] == "2026-08-30_10-00_auto.job.json"


def test_entre_iguais_a_ordem_segue_cronologica(tmp_path):
    _job(tmp_path, "2026-08-28_09-56_auto", meeting="Morales, Hernan")
    _job(tmp_path, "2026-08-27_08-15_auto", meeting="Daily BIZ")
    _job(tmp_path, "2026-09-02_08-03_auto", meeting="Weekly Sync Kelvin <-> Stefan")
    _job(tmp_path, "2026-09-02_08-39_auto", meeting="Weekly Sync Kelvin <-> Stefan")

    assert _ordem(tmp_path) == [
        "2026-09-02_08-03_auto.job.json",
        "2026-09-02_08-39_auto.job.json",
        "2026-08-27_08-15_auto.job.json",
        "2026-08-28_09-56_auto.job.json",
    ]


def test_job_ilegivel_vai_para_o_fim_em_vez_de_estourar(tmp_path):
    (tmp_path / "2026-08-01_08-00_auto.job.json").write_text("{ nao e json",
                                                             encoding="utf-8")
    _job(tmp_path, "2026-09-02_08-03_auto", meeting="Weekly Sync Kelvin <-> Stefan")

    ordem = _ordem(tmp_path)
    assert ordem[0] == "2026-09-02_08-03_auto.job.json"
    assert ordem[-1] == "2026-08-01_08-00_auto.job.json"


def test_prioridade_nao_decide_destino(tmp_path):
    """O outro Stefan do vault. Prioridade 0 na fila, e nada alem disso:
    nem `kind`, nem `target` sao inferidos daqui."""
    job = {"meeting": "1:1 Kelvin / Stefan", "kind": "project", "target": "",
           "needs_review": True}
    assert process._job_priority(job) == 0
    assert job["target"] == ""
    assert job["needs_review"] is True
