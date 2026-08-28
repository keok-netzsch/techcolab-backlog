"""Redundant capture: record every plausible endpoint, choose afterwards.

Why this exists
---------------
Every capture failure measured so far came from CHOOSING A DEVICE UP FRONT and
being wrong by the time the call started:

  2026-08-27 08:01 (11.8 min) — channel 0 was hum. Windows had made the jack
      input ("Saida do Microfone") the default; nothing was plugged into it, so
      it floated. Dynamic range 5.6 dB, 0.7% speech.
  2026-08-27 14:20 (33.0 min) — channel 1 was digital silence. This machine has
      TWO render endpoints, "Altofalantes" and "Auscultadores"; `default_speaker()`
      resolved to the speakers while Teams was actually playing to the headset.
  2026-08-27 15:34 (43.0 min) — channel 0 again ~1% speech.

Probing devices before recording was tried and made it worse: opening a device
to test it is what cost a 50-minute call on the same day. Diagnosis must never
compete with capture.

So: do not choose. Open EVERY candidate input and EVERY render endpoint, spool
them all to disk, and pick the winner when the call ends, using the audio itself
as the evidence. On this machine that is 2 mics + 2 loopbacks at 16 kHz PCM16 —
about 12 MB per hour in total, deleted as soon as the winners are kept.

The selection metric is speech activity, not level: hum has a perfectly
respectable RMS and no speech in it.
"""
from __future__ import annotations

import os
import threading

SAMPLE_RATE = 16000
SPOOL_SUBDIR = "_multi"

# A stream must clear both to count as carrying speech. Hum is loud but flat
# (measured 5.6 dB dynamic range); real conversation on this machine ran 44-67 dB.
MIN_DYNAMIC_DB = 12.0
MIN_ACTIVE_PCT = 5.0


# ── Endpoint discovery ───────────────────────────────────────────────────────

def input_candidates():
    """Physical inputs worth recording, de-duplicated across host APIs.

    MME is preferred over WASAPI for microphones: the WASAPI path to the built-in
    array returns digital silence on this machine, while MME captures normally.
    Stereo Mix / Mapper / Primary are excluded — they are not microphones.
    """
    import sounddevice as sd

    apis = {i: a["name"] for i, a in enumerate(sd.query_hostapis())}
    out, seen = [], set()
    for pref in ("MME", "Windows WASAPI"):
        for idx, d in enumerate(sd.query_devices()):
            if d["max_input_channels"] <= 0 or apis.get(d["hostapi"]) != pref:
                continue
            name = d["name"]
            if any(s in name for s in ("Mix", "Mapper", "Primary", "PC Speaker")):
                continue
            key = name[:28].strip().lower()
            if key in seen:
                continue
            seen.add(key)
            out.append((idx, name))
    return out


def loopback_candidates():
    """Every render endpoint, not just the default one.

    The default is a moving target: plugging a headset repoints it, and an app
    can pin its output independently of the system default.
    """
    try:
        import soundcard as sc
    except ImportError:
        return []
    try:
        return [(s.name, sc.get_microphone(s.name, include_loopback=True))
                for s in sc.all_speakers()]
    except Exception:
        return []


# ── Scoring ──────────────────────────────────────────────────────────────────

def score(samples, sample_rate: int = SAMPLE_RATE) -> dict:
    """Classify a track as 'speech' | 'hum' | 'silent' with the numbers behind it."""
    import numpy as np

    if samples is None or len(samples) < sample_rate:
        return {"verdict": "silent", "dynamic_db": 0.0, "active_pct": 0.0,
                "mean_db": -999.0}

    win = sample_rate // 10
    k = len(samples) // win
    rms = np.sqrt((samples[:k * win].reshape(k, win).astype(np.float64) ** 2).mean(axis=1))

    # Floor clamped at -120 dBFS: a loopback that is digitally silent between
    # sounds gives a 10th percentile of exactly 0, and log(0) turned into a
    # reported dynamic range of 226 dB — a number that is physically impossible
    # and quietly discredits every other figure in the same report.
    FLOOR_MIN = 1e-6

    def db(v):
        return 20 * float(np.log10(max(v, FLOOR_MIN)))

    mean_db = db(rms.mean())
    floor = float(np.percentile(rms, 10))
    dynamic = db(float(np.percentile(rms, 95))) - db(floor)
    # Speech is intermittent and well above its own floor; hum sits on it.
    active = float((rms > floor * 4).mean()) * 100

    if mean_db < -80:
        verdict = "silent"
    elif dynamic >= MIN_DYNAMIC_DB and active >= MIN_ACTIVE_PCT:
        verdict = "speech"
    else:
        verdict = "hum"
    return {"verdict": verdict, "dynamic_db": round(dynamic, 1),
            "active_pct": round(active, 1), "mean_db": round(mean_db, 1)}


def pick_best(scored: list):
    """Best track wins on speech activity. Returns (index, report_lines).

    Never returns None when anything was captured: half a call beats no call.
    """
    if not scored:
        return None, ["nenhum stream capturado"]
    lines = []
    for i, (label, s) in enumerate(scored):
        lines.append(f"  {label[:40]:40s} {s['verdict']:6s} "
                     f"din {s['dynamic_db']:5.1f} dB  fala {s['active_pct']:5.1f}%")
    speech = [i for i, (_, s) in enumerate(scored) if s["verdict"] == "speech"]
    if speech:
        best = max(speech, key=lambda i: scored[i][1]["active_pct"])
    else:
        best = max(range(len(scored)), key=lambda i: scored[i][1]["active_pct"])
        lines.append("  AVISO: nenhum stream com fala - mantido o menos ruim")
    lines.append(f"  -> escolhido: {scored[best][0]}")
    return best, lines


# ── Capture ──────────────────────────────────────────────────────────────────

def _spool_dir(base_dir: str) -> str:
    d = os.path.join(base_dir, SPOOL_SUBDIR, str(os.getpid()))
    os.makedirs(d, exist_ok=True)
    return d


def capture_all(stop_flag, base_dir: str, log=print, mics=None, loops=None) -> dict:
    """Record every candidate endpoint until stop_flag(). Returns {label: path}.

    Each stream spools straight to its own PCM16 file: RAM stays flat regardless
    of call length, and a crash leaves usable audio behind instead of nothing.
    Writes happen in the pump loop, never inside an audio callback.
    """
    import sounddevice as sd
    import soundfile as sf

    d = _spool_dir(base_dir)
    # Injectable so the diagnostic can sweep EVERY input while production keeps
    # a conservative list — the narrow list is what hid `FrontMic` (WDM-KS only).
    mics = input_candidates() if mics is None else mics
    loops = loopback_candidates() if loops is None else loops
    log(f"[multi] gravando {len(mics)} entrada(s) + {len(loops)} loopback(s)")
    for _, n in mics:
        log(f"[multi]   mic      {n}")
    for n, _ in loops:
        log(f"[multi]   loopback {n}")

    paths: dict[str, str] = {}
    threads = []

    def pump_mic(idx, name):
        # Index in the label, not just the name: the same physical microphone is
        # exposed under several host APIs with an identical truncated name, and
        # a colliding key would silently drop devices from the result.
        label = f"mic:[{idx}] {name[:34]}"
        path = os.path.join(d, f"mic_{idx}.wav")
        buf = []
        try:
            with sf.SoundFile(path, "w", samplerate=SAMPLE_RATE, channels=1,
                              subtype="PCM_16") as w, \
                 sd.InputStream(device=idx, samplerate=SAMPLE_RATE, channels=1,
                                dtype="float32",
                                callback=lambda x, f, t, s: buf.append(x.copy())):
                while not stop_flag():
                    sd.sleep(200)
                    while buf:
                        w.write(buf.pop(0))
                while buf:
                    w.write(buf.pop(0))
            paths[label] = path
        except Exception as e:
            log(f"[multi] entrada '{name}' falhou: {e}")

    def pump_loop(name, dev, i):
        label = f"sys:{name[:28]}"
        path = os.path.join(d, f"sys_{i}.wav")
        try:
            with sf.SoundFile(path, "w", samplerate=SAMPLE_RATE, channels=1,
                              subtype="PCM_16") as w, \
                 dev.recorder(samplerate=SAMPLE_RATE, channels=1) as rec:
                while not stop_flag():
                    w.write(rec.record(numframes=SAMPLE_RATE // 5))
            paths[label] = path
        except Exception as e:
            log(f"[multi] loopback '{name}' falhou: {e}")

    for idx, name in mics:
        threads.append(threading.Thread(target=pump_mic, args=(idx, name), daemon=True))
    for i, (name, dev) in enumerate(loops):
        threads.append(threading.Thread(target=pump_loop, args=(name, dev, i), daemon=True))
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return paths


def select_channels(paths: dict, log=print):
    """Score every spooled track and return (mic_samples, sys_samples, report).

    Either side may come back None when nothing usable was captured for it — the
    caller must still save what exists and say so loudly.
    """
    import numpy as np
    import soundfile as sf

    def load(p):
        try:
            a, _ = sf.read(p, dtype="float32")
            return a if a.ndim == 1 else a[:, 0]
        except Exception:
            return None

    mic_scored, sys_scored, data = [], [], {}
    for label, path in sorted(paths.items()):
        a = load(path)
        data[label] = a
        s = score(a)
        (mic_scored if label.startswith("mic:") else sys_scored).append((label, s))

    log("[multi] canal 0 (voce):")
    im, lines = pick_best(mic_scored)
    for ln in lines:
        log(ln)
    log("[multi] canal 1 (outro):")
    isys, lines2 = pick_best(sys_scored)
    for ln in lines2:
        log(ln)

    mic = data.get(mic_scored[im][0]) if im is not None else None
    sysa = data.get(sys_scored[isys][0]) if isys is not None else None

    report = {
        "mic": mic_scored[im] if im is not None else None,
        "sys": sys_scored[isys] if isys is not None else None,
    }
    for side, key in (("canal 0 (voce)", "mic"), ("canal 1 (outro)", "sys")):
        r = report[key]
        if r is None or r[1]["verdict"] != "speech":
            got = "nada capturado" if r is None else r[1]["verdict"]
            log(f"[multi] *** ALERTA: {side} sem fala ({got}). "
                f"A gravacao ficou incompleta. ***")
    return mic, sysa, report


def cleanup(base_dir: str) -> None:
    import shutil
    shutil.rmtree(_spool_dir(base_dir), ignore_errors=True)


def capture_dual_redundant(stop_flag, base_dir: str, log=print):
    """Drop-in replacement for record.capture_dual using redundant capture.

    Returns (mic, sys) as (N,1) float32 arrays of equal length — the exact shape
    the existing callers already concatenate — or None so the caller can fall
    back to the classic single-device path.

    This is the whole point of the module in production: Kelvin rotates headsets
    (Logitech at the office, an Asus, and currently generic earphones in the
    jack). Any pinned device name is wrong the next time hardware changes, and
    the Windows default input on this machine points at an empty jack. Recording
    every present input and choosing by speech activity is the only approach that
    survives the hardware moving around.
    """
    import numpy as np

    try:
        paths = capture_all(stop_flag, base_dir, log=log)
    except Exception as e:
        log(f"[multi] captura redundante falhou ({e})")
        return None
    if not paths:
        return None

    mic, sysa, _ = select_channels(paths, log=log)
    try:
        cleanup(base_dir)
    except Exception:
        pass

    if mic is None and sysa is None:
        return None
    n = max(len(x) for x in (mic, sysa) if x is not None)

    def col(x):
        if x is None:
            return np.zeros((n, 1), dtype="float32")
        a = np.asarray(x, dtype="float32")
        if len(a) < n:
            a = np.concatenate([a, np.zeros(n - len(a), dtype="float32")])
        return a[:n].reshape(-1, 1)

    return col(mic), col(sysa)
