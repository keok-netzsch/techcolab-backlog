"""Tests for the decoupled recording queue (process.cmd_queue)."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "call-recorder"))

import process  # noqa: E402
import record  # noqa: E402


def _ollama_ok(monkeypatch):
    monkeypatch.setattr(process.requests, "get", lambda *a, **k: type("R", (), {})())


def _write_job(rdir, base, **fields):
    wav = rdir / f"{base}.wav"
    wav.write_bytes(b"RIFFfakeWAV")
    job = rdir / f"{base}.job.json"
    job.write_text(json.dumps(fields), encoding="utf-8")
    return job


def test_queue_transcribes_and_routes_person(tmp_path, monkeypatch):
    _ollama_ok(monkeypatch)
    rdir = tmp_path / "recordings"; rdir.mkdir()
    tpath = tmp_path / "transcripts" / "2026-06-04_11-00_Ana-Leite.txt"
    job = _write_job(
        rdir, "2026-06-04_11-00_Ana-Leite",
        wav="2026-06-04_11-00_Ana-Leite.wav", transcript=str(tpath),
        kind="person", target="Ana-Leite", lang="pt", date="2026-06-04", time="11-00",
    )
    monkeypatch.setattr(record, "transcribe", lambda w, language="pt": ("transcricao fake", "pt"))
    routed = {}
    monkeypatch.setattr(process, "cmd_transcript",
                        lambda target, t, date, structured=False, lang="pt": routed.update(target=target))

    r = process.cmd_queue(str(rdir))

    assert job.name in r["processed"]
    assert not job.exists()                          # job consumed
    assert tpath.read_text(encoding="utf-8") == "transcricao fake"
    assert routed["target"] == "Ana-Leite"           # routed to the person


def test_queue_routes_note_and_runs_coach_for_english(tmp_path, monkeypatch):
    _ollama_ok(monkeypatch)
    rdir = tmp_path / "recordings"; rdir.mkdir()
    tpath = tmp_path / "transcripts" / "2026-06-04_12-00_nota-avulsa.txt"
    _write_job(
        rdir, "2026-06-04_12-00_nota-avulsa",
        wav="2026-06-04_12-00_nota-avulsa.wav", transcript=str(tpath),
        kind="note", target=None, lang="en", date="2026-06-04", time="12-00", coach=True,
    )
    monkeypatch.setattr(record, "transcribe", lambda w, language="pt": ("hello this is english", "en"))
    monkeypatch.setattr(process, "cmd_note", lambda *a, **k: None)
    coach_called = {}
    monkeypatch.setattr(process.subprocess, "run",
                        lambda *a, **k: coach_called.setdefault("ran", True))

    r = process.cmd_queue(str(rdir))
    assert len(r["processed"]) == 1
    assert coach_called.get("ran") is True           # English → coach ran


def test_queue_drops_orphan_job_when_wav_missing(tmp_path, monkeypatch):
    _ollama_ok(monkeypatch)
    rdir = tmp_path / "recordings"; rdir.mkdir()
    job = rdir / "x.job.json"
    job.write_text(json.dumps({"wav": "missing.wav", "transcript": "t.txt",
                               "kind": "note", "date": "2026-06-04"}), encoding="utf-8")
    r = process.cmd_queue(str(rdir))
    assert job.name in r["skipped"]
    assert not job.exists()                           # orphan dropped


def test_queue_empty_when_no_jobs(tmp_path):
    rdir = tmp_path / "recordings"; rdir.mkdir()
    r = process.cmd_queue(str(rdir))
    assert r == {"processed": [], "failed": [], "skipped": []}


# ── Trava de concorrencia ─────────────────────────────────────────────────────
# A fila ganhou tarefa propria as 20:00 em 2026-08-29. Um lote manual iniciado de
# dia pode ainda estar rodando quando a tarefa dispara, e as duas leem a MESMA
# lista de .job.json: a nota iria para o vault duas vezes e dois Whisper
# disputariam a mesma CPU.


def test_lock_recusa_segunda_fila(tmp_path):
    assert process.acquire_queue_lock(tmp_path) is not None
    assert process.acquire_queue_lock(tmp_path) is None


def test_lock_orfa_de_processo_morto_e_liberada(tmp_path):
    # Crash, logoff ou reboot no meio do lote deixa a trava para tras. O lote da
    # noite tem que rodar mesmo assim - trava presa seria pior que concorrencia.
    (tmp_path / process.QUEUE_LOCK_NAME).write_text("999999 x", encoding="utf-8")
    lock = process.acquire_queue_lock(tmp_path)
    assert lock is not None
    assert lock.read_text(encoding="utf-8").startswith(str(os.getpid()))


def test_lock_ilegivel_nao_trava_a_fila_para_sempre(tmp_path):
    (tmp_path / process.QUEUE_LOCK_NAME).write_text("nao e um pid", encoding="utf-8")
    assert process.acquire_queue_lock(tmp_path) is not None


def test_pid_alive_nao_mata_o_processo_que_sonda(tmp_path):
    # os.kill(pid, 0) no Windows chama TerminateProcess: a sonda ingenua mataria
    # a propria fila que veio conferir.
    assert process._pid_alive(os.getpid()) is True
    assert process._pid_alive(999999) is False
    assert process._pid_alive(0) is False


def test_queue_ocupada_nao_consome_o_job(tmp_path, monkeypatch):
    _ollama_ok(monkeypatch)
    job = _write_job(tmp_path, "2026-08-29_10-00_auto", kind="note", lang="pt")
    (tmp_path / process.QUEUE_LOCK_NAME).write_text(f"{os.getpid()} agora", encoding="utf-8")
    res = process.cmd_queue(str(tmp_path))
    assert res["processed"] == []
    assert res["skipped"] == [job.name]
    assert job.exists(), "job recusado por trava nao pode ser consumido nem renomeado"


def test_lock_liberada_quando_o_laco_explode(tmp_path, monkeypatch):
    _ollama_ok(monkeypatch)
    _write_job(tmp_path, "2026-08-29_10-00_auto", kind="note", lang="pt")

    def boom(*a, **k):
        raise KeyboardInterrupt("Ctrl+C no meio do lote")

    monkeypatch.setattr(process, "_queue_run", boom)
    try:
        process.cmd_queue(str(tmp_path))
    except KeyboardInterrupt:
        pass
    assert not (tmp_path / process.QUEUE_LOCK_NAME).exists(), \
        "excecao que escapa do laco nao pode deixar a trava presa"
