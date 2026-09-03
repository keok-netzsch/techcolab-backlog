"""Process ONE queued recording, by name. Same pipeline as `process.py queue`.

`cmd_queue` is all-or-nothing: it drains every pending job. That is right for the
20:00 batch and wrong when Kelvin wants one specific call now — on this machine a
single 45-minute recording is roughly 1.5 h of Whisper, so transcribing ten of
them to get at one is not a real option during the working day.

    python process_one.py 2026-08-28_11-00
    python process_one.py 2026-08-28_11-00_auto.job.json
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

RECORDINGS = HERE / "recordings"


def find_job(fragment: str) -> Path:
    hits = sorted(p for p in RECORDINGS.glob("*.job.json") if fragment in p.name)
    if not hits:
        raise SystemExit(f"nenhum job pendente casa com '{fragment}'.\n"
                         f"pendentes: " +
                         ", ".join(p.stem for p in sorted(RECORDINGS.glob("*.job.json")))
                         or "(nenhum)")
    if len(hits) > 1:
        raise SystemExit("ambiguo — casa com mais de um job:\n  " +
                         "\n  ".join(h.name for h in hits))
    return hits[0]


def _main_travado():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)

    import process as proc
    import record

    jf = find_job(sys.argv[1])
    job = json.loads(jf.read_text(encoding="utf-8"))
    wav = RECORDINGS / Path(job["wav"]).name
    if not wav.exists():
        raise SystemExit(f"wav ausente: {wav}")

    # MESMA trava da fila. Este arquivo nasceu depois do single-flight de 29/08 e
    # nunca a pegou — e a fila e o process_one leem a MESMA lista de jobs.
    #
    # Custou em 2026-09-02: enquanto a fila processava o 2026-09-02_08-03, outra
    # sessao rodou process_one na mesma gravacao. Os dois transcreveram e os dois
    # chamaram o coach. O mesmo audio de 32,6 min saiu com 2296, 2338 e 2296
    # palavras (tres transcricoes distintas) e foi avaliado B1, B2 e C1 no espaco
    # de uma hora. O segundo a terminar ainda bateu num WinError 183 ao tentar
    # estacionar um job que o primeiro ja tinha estacionado.
    #
    # Sem trava aqui, a trava da fila protege a fila de si mesma e de mais nada.
    lock = proc.acquire_queue_lock(RECORDINGS)
    if lock is None:
        raise SystemExit(
            "[one] outra fila (ou outro process_one) ja esta rodando - saindo sem "
            "tocar em nada.\n"
            "      Transcrever a mesma gravacao duas vezes gera duas notas e duas "
            "avaliacoes do coach, com veredictos diferentes.")

    print(f"[one] {wav.name}  kind={job['kind']}  target={job.get('target') or '-'}")
    print(f"[one] reuniao: {job.get('meeting', '-')}")
    print("[one] transcrevendo (pode demorar ~2x a duracao do audio)...", flush=True)

    lang = job.get("lang", "pt")
    whisper_lang = None if lang == "auto" else lang
    text, detected = record.transcribe(str(wav), language=whisper_lang)
    effective = detected if lang == "auto" else lang

    tpath = Path(job["transcript"])
    tpath.parent.mkdir(parents=True, exist_ok=True)
    tpath.write_text(text, encoding="utf-8")
    Path(str(tpath) + ".lang").write_text(effective, encoding="utf-8")
    print(f"[one] transcrito: {len(text.split())} palavras, lang={effective}")

    if job.get("route_after_transcript"):
        job["transcript_ready"] = True
        job["lang_detected"] = effective
        jf.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
        proc.maybe_run_coach(tpath, effective, forced=bool(job.get("coach")))
        jf.rename(jf.with_suffix(".json.routing"))
        print(f"[one] transcrito e parqueado para roteamento: {jf.stem}")
        print("[one] proximo passo: python route.py")
        return

    kind, date = job["kind"], job["date"]
    if kind == "person":
        proc.cmd_transcript(job["target"], str(tpath), date,
                            structured=job.get("structured", False), lang=effective)
    elif kind == "manager":
        proc.cmd_manager(job["target"], str(tpath), date, lang=effective)
    elif kind == "note":
        proc.cmd_note(str(tpath), date, lang=effective, time_str=job.get("time"))
    elif kind in proc.CAPTURE_MODES:
        proc.cmd_capture(kind, str(tpath), date, lang=effective,
                         time_str=job.get("time"), context=job.get("context", ""))
    else:
        print(f"[one] kind desconhecido '{kind}' — transcrito, mas nao roteado.")

    proc.maybe_run_coach(tpath, effective, forced=bool(job.get("coach")))

    # Consume the job the same way cmd_queue does, so the 20:00 batch does not
    # transcribe this file all over again tonight.
    jf.rename(jf.with_suffix(".json.done"))
    print(f"[one] concluido. Job consumido: {jf.name} -> .done")


def main():
    """Envolve `_main_travado` so para liberar a trava num finally.

    finally, e nao no fim do corpo: uma excecao que escape deixaria a trava presa
    e nenhuma fila rodaria de novo ate alguem notar. E a mesma razao pela qual
    `cmd_queue` faz assim desde 29/08.
    """
    import process as proc
    try:
        return _main_travado()
    finally:
        lock = RECORDINGS / getattr(proc, "QUEUE_LOCK_NAME", ".queue.lock")
        try:
            if lock.exists() and lock.read_text(encoding="utf-8").split()[0] == str(os.getpid()):
                lock.unlink(missing_ok=True)
        except Exception:
            pass


if __name__ == "__main__":
    main()
