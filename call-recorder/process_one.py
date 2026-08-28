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


def main():
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
                         time_str=job.get("time"))
    else:
        print(f"[one] kind desconhecido '{kind}' — transcrito, mas nao roteado.")

    proc.maybe_run_coach(tpath, effective, forced=bool(job.get("coach")))

    # Consume the job the same way cmd_queue does, so the 20:00 batch does not
    # transcribe this file all over again tonight.
    jf.rename(jf.with_suffix(".json.done"))
    print(f"[one] concluido. Job consumido: {jf.name} -> .done")


if __name__ == "__main__":
    main()
