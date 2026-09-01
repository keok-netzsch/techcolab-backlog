"""Objecao do interlocutor: "manter e marcar" (decisao do Kelvin, 2026-09-01).

Se alguem recusa ser gravado, o audio NAO e apagado e NAO e transcrito. Ele fica
em recordings/ com um sidecar `<base>.no-consent.json`, e todo estagio que
consumiria aquele arquivo para de consumi-lo: a classificacao nao cria job, a
fila nao transcreve, a retencao nao poda.

O teste que mais importa aqui e o da retencao. Um .wav marcado nao tem
`.job.json` nem `.pending.json` — pela regra anterior ele era "orphan", e orphan
e apagado aos 7 dias. Sem a guarda, "manter e marcar" viraria "marcar e apagar
na semana seguinte", em silencio.
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "call-recorder"))

import process  # noqa: E402
import record  # noqa: E402


def _wav(tmp_path, stem="2026-09-01_14-30_auto", age_days=0):
    p = tmp_path / f"{stem}.wav"
    open(p, "w").close()
    if age_days:
        ts = time.time() - age_days * 86400
        os.utime(p, (ts, ts))
    return p


# ── O marcador ────────────────────────────────────────────────────────────────

def test_marking_creates_sidecar_next_to_the_wav(tmp_path):
    wav = _wav(tmp_path)
    path = record.mark_no_consent(str(wav), "Fulano pediu para nao gravar")
    assert os.path.exists(path)
    assert path == str(tmp_path / "2026-09-01_14-30_auto.no-consent.json")
    assert record.is_no_consent(str(wav))


def test_marker_records_the_reason_and_the_policy(tmp_path):
    wav = _wav(tmp_path)
    record.mark_no_consent(str(wav), "Fulano pediu para nao gravar")
    meta = record.read_no_consent(str(wav))
    assert meta["motivo"] == "Fulano pediu para nao gravar"
    assert meta["marcado_em"]
    assert "nunca transcrever" in meta["politica"]


def test_unmarked_recording_is_not_flagged(tmp_path):
    assert not record.is_no_consent(str(_wav(tmp_path)))


def test_remarking_keeps_the_original_date(tmp_path):
    # A data em que a pessoa objetou e o fato; rodar o comando de novo nao a move.
    wav = _wav(tmp_path)
    record.mark_no_consent(str(wav), "primeira")
    first = record.read_no_consent(str(wav))["marcado_em"]
    record.mark_no_consent(str(wav), "segunda")
    meta = record.read_no_consent(str(wav))
    assert meta["marcado_em"] == first
    assert meta["remarcado_em"]
    assert meta["motivo"] == "segunda"


def test_unreadable_marker_still_counts_as_marked(tmp_path):
    # Sidecar corrompido nao pode virar permissao para transcrever.
    wav = _wav(tmp_path)
    (tmp_path / "2026-09-01_14-30_auto.no-consent.json").write_text("{quebrado",
                                                                    encoding="utf-8")
    assert record.is_no_consent(str(wav))
    assert record.read_no_consent(str(wav)) == {}
    assert record._recording_state(str(wav))[0] == "no-consent"


def test_clearing_the_mark(tmp_path):
    wav = _wav(tmp_path)
    record.mark_no_consent(str(wav))
    assert record.clear_no_consent(str(wav)) is True
    assert not record.is_no_consent(str(wav))
    assert record.clear_no_consent(str(wav)) is False


# ── Retencao: marcado NUNCA e podado nem quarentenado ─────────────────────────

def test_retention_keeps_a_marked_recording_forever(tmp_path):
    wav = _wav(tmp_path, age_days=90)
    record.mark_no_consent(str(wav), "objecao")
    assert record.prune_old_recordings(str(tmp_path), days=7) == 0
    assert wav.exists()


def test_retention_does_not_quarantine_a_marked_recording(tmp_path):
    wav = _wav(tmp_path, age_days=90)
    record.mark_no_consent(str(wav))
    record.prune_old_recordings(str(tmp_path), days=7)
    assert not (tmp_path / "failed" / wav.name).exists()
    assert wav.exists()


def test_marked_beats_orphan_and_pending(tmp_path):
    wav = _wav(tmp_path, age_days=90)
    assert record._recording_state(str(wav))[0] == "orphan"
    (tmp_path / "2026-09-01_14-30_auto.pending.json").write_text("{}", encoding="utf-8")
    assert record._recording_state(str(wav))[0] == "pending"
    record.mark_no_consent(str(wav))
    state, detail = record._recording_state(str(wav))
    assert state == "no-consent"
    assert "nunca transcrever" in detail


def test_an_unmarked_orphan_is_still_pruned(tmp_path):
    # A guarda nova nao pode afrouxar a retencao para todo o resto.
    old = _wav(tmp_path, stem="2026-06-01_09-00_auto", age_days=90)
    marked = _wav(tmp_path, stem="2026-06-02_09-00_auto", age_days=90)
    record.mark_no_consent(str(marked))
    assert record.prune_old_recordings(str(tmp_path), days=7) == 1
    assert not old.exists()
    assert marked.exists()


# ── A fila nao transcreve o que esta marcado ──────────────────────────────────

def _job_for(wav):
    jf = wav.with_suffix(".job.json")
    jf.write_text(json.dumps({"wav": wav.name, "kind": "note", "date": "2026-09-01",
                              "transcript": str(wav.with_suffix(".txt"))}),
                  encoding="utf-8")
    return jf


def test_queue_skips_and_parks_a_marked_job(tmp_path):
    wav = _wav(tmp_path)
    jf = _job_for(wav)
    record.mark_no_consent(str(wav), "objecao")

    result = {"processed": [], "failed": [], "skipped": []}
    process._queue_run([jf], result, tmp_path, dry_run=False)

    assert result["skipped"] == [jf.name]
    assert result["processed"] == []
    assert not jf.exists()
    assert wav.with_suffix(".job.json.no-consent").exists()
    assert wav.exists()          # o audio continua la


def test_queue_dry_run_reports_a_marked_job_as_skipped(tmp_path):
    # Simulacao que mostra a gravacao como "seria processada" e pior que nenhuma.
    wav = _wav(tmp_path)
    jf = _job_for(wav)
    record.mark_no_consent(str(wav))

    result = {"processed": [], "failed": [], "skipped": []}
    process._queue_run([jf], result, tmp_path, dry_run=True)

    assert result["skipped"] == [jf.name]
    assert result["processed"] == []
    assert jf.exists()           # dry-run nao move nada


def test_queue_still_lists_an_unmarked_job(tmp_path):
    wav = _wav(tmp_path)
    jf = _job_for(wav)
    result = {"processed": [], "failed": [], "skipped": []}
    process._queue_run([jf], result, tmp_path, dry_run=True)
    assert result["processed"] == [jf.name]


# ── CLI: marcar, listar, desfazer ─────────────────────────────────────────────

def test_cli_marks_the_last_recording_by_default(tmp_path):
    _wav(tmp_path, stem="2026-08-30_09-00_auto", age_days=2)
    newest = _wav(tmp_path, stem="2026-09-01_15-00_auto")
    out = process.cmd_no_consent(motivo="recusou", recordings_dir=str(tmp_path))
    assert out["marcadas"] == [newest.name]
    assert record.is_no_consent(str(newest))


def test_cli_matches_a_partial_name(tmp_path):
    wav = _wav(tmp_path, stem="2026-09-01_15-00_Ana-Leite")
    _wav(tmp_path, stem="2026-09-01_16-00_auto")
    process.cmd_no_consent("Ana-Leite", recordings_dir=str(tmp_path))
    assert record.is_no_consent(str(wav))


def test_cli_refuses_an_ambiguous_match(tmp_path):
    a = _wav(tmp_path, stem="2026-09-01_15-00_auto")
    b = _wav(tmp_path, stem="2026-09-01_16-00_auto")
    out = process.cmd_no_consent("auto", recordings_dir=str(tmp_path))
    assert out["marcadas"] == []
    assert not record.is_no_consent(str(a))
    assert not record.is_no_consent(str(b))


def test_cli_parks_the_job_immediately(tmp_path):
    wav = _wav(tmp_path)
    jf = _job_for(wav)
    process.cmd_no_consent("ultima", recordings_dir=str(tmp_path))
    assert not jf.exists()
    assert wav.with_suffix(".job.json.no-consent").exists()


def test_cli_parks_a_job_already_parked_for_routing(tmp_path):
    wav = _wav(tmp_path)
    routing = wav.with_suffix(".job.json.routing")
    routing.write_text("{}", encoding="utf-8")
    process.cmd_no_consent("ultima", recordings_dir=str(tmp_path))
    assert not routing.exists()
    assert wav.with_suffix(".job.json.no-consent").exists()


def test_cli_undo_restores_the_job_to_the_queue(tmp_path):
    wav = _wav(tmp_path)
    _job_for(wav)
    process.cmd_no_consent("ultima", recordings_dir=str(tmp_path))
    out = process.cmd_no_consent("ultima", desfazer=True, recordings_dir=str(tmp_path))
    assert out["desmarcadas"] == [wav.name]
    assert not record.is_no_consent(str(wav))
    assert wav.with_suffix(".job.json").exists()
    assert not wav.with_suffix(".job.json.no-consent").exists()


def test_cli_warns_when_a_transcript_already_exists(tmp_path):
    # A marca nao apaga o que ja foi produzido - e tem que dizer isso em voz alta.
    wav = _wav(tmp_path)
    tpath = tmp_path / "2026-09-01_14-30_auto.txt"
    tpath.write_text("ja transcrito", encoding="utf-8")
    wav.with_suffix(".job.json.done").write_text(
        json.dumps({"transcript": str(tpath)}), encoding="utf-8")
    out = process.cmd_no_consent("ultima", recordings_dir=str(tmp_path))
    assert any("transcript existente" in w for w in out["avisos"])
    assert tpath.exists()


def test_cli_listing_is_the_default_with_no_target(tmp_path):
    wav = _wav(tmp_path)
    record.mark_no_consent(str(wav), "recusou")
    out = process.cmd_no_consent(listar=True, recordings_dir=str(tmp_path))
    assert out["marcadas"] == [wav.name]


def test_cli_on_an_empty_dir_is_safe(tmp_path):
    out = process.cmd_no_consent("ultima", recordings_dir=str(tmp_path))
    assert out["marcadas"] == []
    assert out["avisos"] == ["nao encontrada"]
