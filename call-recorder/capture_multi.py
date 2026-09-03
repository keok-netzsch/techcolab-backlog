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
import time

SAMPLE_RATE = 16000
SPOOL_SUBDIR = "_multi"

# A stream must clear both to count as carrying speech. Hum is loud but flat
# (measured 5.6 dB dynamic range); real conversation on this machine ran 44-67 dB.
MIN_DYNAMIC_DB = 12.0
MIN_ACTIVE_PCT = 5.0


# ── Endpoint discovery ───────────────────────────────────────────────────────

def input_candidates():
    """Inputs worth recording — the SAME device under EVERY host API it exposes.

    Do not de-duplicate by device name. The same physical microphone behaves
    completely differently depending on the host API, and on 2026-08-28 that
    difference was the whole bug: "Saida do MicrofoneMic" delivered Kelvin's
    voice at 79% speech through WASAPI and flat hum at 0.0% through DirectSound.
    De-duplicating by name kept the MME entry and discarded the one that works.

    WDM-KS is excluded on purpose: it opens in exclusive mode, and taking the
    microphone that way during a call could steal it from Teams and leave him
    muted. Extra coverage is not worth breaking the call being recorded.
    """
    import sounddevice as sd

    apis = {i: a["name"] for i, a in enumerate(sd.query_hostapis())}
    out = []
    for idx, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] <= 0:
            continue
        if apis.get(d["hostapi"]) not in ("MME", "Windows WASAPI", "Windows DirectSound"):
            continue
        name = d["name"]
        if any(s in name for s in ("Mix", "Mapper", "Primary", "PC Speaker")):
            continue
        out.append((idx, f"{name} [{apis[d['hostapi']]}]"))
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


# ── Zumbido de rede ──────────────────────────────────────────────────────────
#
# A entrada de microfone desta maquina entrega ~-24 dBFS CONSTANTES de zumbido
# de rede. Um microfone parado fica entre -60 e -45. Medido em 2026-09-03,
# direto no dispositivo, com o Kelvin em silencio:
#
#   picos      60.0 Hz e 120.0 Hz     (fundamental e 2o harmonico)
#   100-200 Hz    25.4 dB             <- a banda mais forte do sinal
#   300-1k Hz     14.7 dB             <- onde a voz dele vive
#   1k-3k Hz       8.4 dB
#
# O zumbido fica 11 dB ACIMA da banda da voz. Por isso `active_pct` da ~0% no
# microfone que ele de fato usa (`Saida do MicrofoneMic`, o padrao do Windows):
# nada se destaca de um piso que ja e alto e constante, nem a fala. O gravador
# entao escolhe o array do notebook, que pontua melhor por acaso e nao e onde
# ele fala.
#
# NAO e a alimentacao: medido na tomada e na bateria, os numeros sao os mesmos
# (-24.0 vs -22.6 dBFS, picos identicos). A causa fisica segue em aberto e o
# filtro nao a resolve — ele torna a gravacao utilizavel enquanto isso.
#
# Corte escolhido por MEDICAO sobre a call de 13:37 daquele dia, nao por teoria:
#
#   sem filtro     din 11.3 dB   fala  3.7%   hum
#   dehum 150 Hz   din 12.5 dB   fala  5.7%   speech   <- passa raspando
#   dehum 200 Hz   din 15.4 dB   fala 10.7%   speech
#   dehum 250 Hz   din 17.6 dB   fala 15.0%   speech   <- escolhido
#   dehum 300 Hz   din 18.7 dB   fala 16.6%   speech
#
# 250 Hz devolve os mesmos numeros do teste das 11:47 daquele dia (17.5 dB,
# 19.4%), que foi quando o microfone funcionou sem zumbido. 150 Hz passaria
# a 0.5 dB do limiar, e margem dessa espessura volta a falhar na primeira call
# um pouco mais ruidosa.
#
# Corta o fundamental da voz masculina (85-180 Hz) e preserva os harmonicos.
# E o que a telefonia faz desde sempre com sua banda de 300-3400 Hz, e o
# Whisper foi treinado com muito audio dessa forma.
HUM_HIGHPASS_HZ = 250.0


def dehum(samples, sample_rate: int = SAMPLE_RATE, cutoff: float = HUM_HIGHPASS_HZ):
    """High-pass por subtracao de media movel, aplicado 2x. float32 novo.

    Nao e biquad e nao e FFT, e as duas alternativas foram descartadas por
    custo sobre a call INTEIRA:

    - IIR exige recorrencia amostra a amostra; um laco Python sobre os 110M
      pontos de uma call de 115 min leva minutos, dentro de uma fila que ja
      gasta horas com o Whisper.
    - `rfft` desses mesmos 110M pontos pede mais de 1 GB so no array complexo.

    Media movel via `cumsum` e O(n) e roda em C. Subtrair uma media movel de N
    amostras remove o que e mais lento que N, ou seja e um high-pass; aplicar
    duas vezes dobra a inclinacao e da queda suficiente para 60 e 120 Hz.
    A janela sai de `sample_rate / cutoff` porque e o periodo da frequencia de
    corte em amostras.

    Verificado contra o high-pass exato por FFT no audio real de 2026-09-03:
    os dois levam a dinamica de 9.5 dB para ~15-16 dB e a fala de 0.7% para
    ~16%. Aproximacao que chega no mesmo veredito, por uma fracao do custo.
    """
    import numpy as np

    x = np.asarray(samples, dtype=np.float64).ravel()
    if len(x) < 4 or cutoff <= 0 or cutoff >= sample_rate / 2:
        return np.asarray(samples, dtype=np.float32)

    n = max(3, int(round(sample_rate / float(cutoff))))
    if n >= len(x):
        return np.asarray(samples, dtype=np.float32)

    def media_movel(v, w):
        # Borda replicada: zero-padding criaria um degrau no inicio do arquivo,
        # e um degrau e exatamente o tipo de artefato que o Whisper decodifica
        # como fala inventada.
        pad = w // 2
        vp = np.concatenate([np.full(pad, v[0]), v, np.full(w - 1 - pad, v[-1])])
        c = np.cumsum(vp, dtype=np.float64)
        c = np.concatenate([[0.0], c])
        return (c[w:] - c[:-w]) / w

    y = x - media_movel(x, n)
    y = y - media_movel(y, n)
    return y.astype(np.float32)


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

    Aceita `(label, score)` ou `(label, score, score_sem_zumbido)`. Na forma de
    3 o RELATORIO sai do sinal como gravado e a ESCOLHA sai do filtrado — ver o
    comentario em `select_channels`. Loopback vem sempre na forma de 2: ele nao
    tem zumbido de rede (piso medido em -68.9 dBFS contra -32.1 do microfone) e
    filtrar ali seria mexer no que ja funciona.
    """
    if not scored:
        return None, ["nenhum stream capturado"]

    def _decisor(r):
        return r[2] if len(r) > 2 else r[1]

    lines = []
    for r in scored:
        label, s = r[0], r[1]
        extra = ""
        if len(r) > 2 and r[2]["verdict"] != s["verdict"]:
            extra = (f"   [sem zumbido: {r[2]['verdict']} "
                     f"din {r[2]['dynamic_db']:.1f} dB fala {r[2]['active_pct']:.1f}%]")
        lines.append(f"  {label[:40]:40s} {s['verdict']:6s} "
                     f"din {s['dynamic_db']:5.1f} dB  fala {s['active_pct']:5.1f}%{extra}")

    speech = [i for i, r in enumerate(scored) if _decisor(r)["verdict"] == "speech"]
    if speech:
        best = max(speech, key=lambda i: _decisor(scored[i])["active_pct"])
    else:
        best = max(range(len(scored)), key=lambda i: _decisor(scored[i])["active_pct"])
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

        # Open at the device's NATIVE rate, not at 16 kHz. WASAPI shared mode
        # refuses any other rate — every WASAPI path on this machine failed with
        # "Invalid sample rate [-9997]" and silently dropped out of the capture,
        # including both real microphones. Whisper wants 16 kHz, so resample on
        # the way to disk instead of demanding it from the driver.
        try:
            native = int(sd.query_devices(idx)["default_samplerate"]) or SAMPLE_RATE
        except Exception:
            native = SAMPLE_RATE

        def to_16k(block):
            if native == SAMPLE_RATE:
                return block
            import numpy as np
            n_out = int(len(block) * SAMPLE_RATE / native)
            if n_out < 1:
                return block[:0]
            src = np.linspace(0, len(block) - 1, n_out)
            return np.interp(src, np.arange(len(block)),
                             block[:, 0]).astype("float32").reshape(-1, 1)

        try:
            with sf.SoundFile(path, "w", samplerate=SAMPLE_RATE, channels=1,
                              subtype="PCM_16") as w, \
                 sd.InputStream(device=idx, samplerate=native, channels=1,
                                dtype="float32",
                                callback=lambda x, f, t, s: buf.append(x.copy())):
                while not stop_flag():
                    sd.sleep(200)
                    while buf:
                        w.write(to_16k(buf.pop(0)))
                while buf:
                    w.write(to_16k(buf.pop(0)))
            paths[label] = path
        except Exception as e:
            log(f"[multi] entrada '{name}' falhou: {e}")

    def pump_loop(name, dev, i):
        label = f"sys:{name[:28]}"
        path = os.path.join(d, f"sys_{i}.wav")

        # COM e POR THREAD, e esta funcao roda numa thread nova. `soundcard`
        # fala com o WASAPI via COM: sem CoInitializeEx aqui, `dev.recorder`
        # morre com 0x800401f0 (CO_E_NOTINITIALIZED) no instante em que abre, os
        # dois endpoints caem juntos e o canal 1 vai para o disco zerado.
        #
        # A mesma correcao ja existia em `record.pump_sys` desde 2026-08-27. O
        # commit f8d936b escreveu ela la e, no mesmo dia, ligou ESTE caminho como
        # padrao (CAPTURE_REDUNDANT=1) — a correcao nasceu no ramo que deixou de
        # rodar. De 27/08 a 03/09 o loopback falhou assim em 7 gravacoes, entre
        # elas uma call de 115 min e uma de 48 min.
        #
        # Intermitente de proposito enganoso: uma thread sem CoInitializeEx so
        # funciona enquanto OUTRA thread do processo mantem a MTA viva, entao
        # reiniciar o autocapture "consertava" ate a proxima vez.
        import ctypes
        com_ready = False
        try:
            hr = ctypes.windll.ole32.CoInitializeEx(None, 0)  # 0 = APARTMENTTHREADED
            com_ready = hr in (0, 1)          # S_OK | S_FALSE (ja inicializado)
            if not com_ready:
                log(f"[multi] loopback '{name}': CoInitializeEx devolveu "
                    f"0x{hr & 0xFFFFFFFF:08x}")
        except Exception as e:
            log(f"[multi] loopback '{name}': CoInitializeEx falhou ({e})")

        try:
            # Uma falha transitoria ao abrir nao pode custar o canal inteiro —
            # mesmo retry do caminho classico.
            rec_ctx, last_err = None, None
            for tentativa in range(3):
                try:
                    rec_ctx = dev.recorder(samplerate=SAMPLE_RATE, channels=1)
                    rec_ctx.__enter__()
                    if tentativa:
                        log(f"[multi] loopback '{name}': aberto na tentativa {tentativa + 1}")
                    break
                except Exception as e:
                    last_err, rec_ctx = e, None
                    time.sleep(0.5)
            if rec_ctx is None:
                raise last_err or RuntimeError("loopback nao abriu")
            try:
                with sf.SoundFile(path, "w", samplerate=SAMPLE_RATE, channels=1,
                                  subtype="PCM_16") as w:
                    while not stop_flag():
                        w.write(rec_ctx.record(numframes=SAMPLE_RATE // 5))
            finally:
                rec_ctx.__exit__(None, None, None)
            paths[label] = path
        except Exception as e:
            log(f"[multi] loopback '{name}' falhou: {e}")
        finally:
            if com_ready:
                try:
                    ctypes.windll.ole32.CoUninitialize()
                except Exception:
                    pass

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
    import soundfile as sf

    def load(p):
        try:
            a, _ = sf.read(p, dtype="float32")
            return a if a.ndim == 1 else a[:, 0]
        except Exception:
            return None

    # Dois scores por microfone, de proposito:
    #
    #   `s`      do sinal COMO GRAVADO — e o que vai para o log e para o
    #            channel_profile, que alimentam `canal_mudo` e
    #            `contaminacao_de_canal`. Se este numero viesse filtrado, os
    #            gates passariam a medir um audio que nao existe em disco.
    #   `s_lim`  do sinal sem zumbido — e o que DECIDE qual entrada vence.
    #
    # Sem essa separacao o gravador escolhe o array do notebook, que pontua
    # melhor por acaso, em vez do microfone em que o Kelvin de fato fala e que
    # o zumbido de rede afoga (ver HUM_HIGHPASS_HZ). O `.wav` continua com o
    # sinal original: filtrar na gravacao apagaria a evidencia do problema, e
    # a transcricao aplica o mesmo filtro por conta propria.
    mic_scored, sys_scored, data = [], [], {}
    for label, path in sorted(paths.items()):
        a = load(path)
        data[label] = a
        s = score(a)
        if label.startswith("mic:"):
            try:
                s_lim = score(dehum(a)) if a is not None else s
            except Exception:
                s_lim = s          # filtro nunca pode derrubar uma captura
            mic_scored.append((label, s, s_lim))
        else:
            sys_scored.append((label, s))

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
        if r is None:
            log(f"[multi] *** ALERTA: {side} sem fala (nada capturado). "
                f"A gravacao ficou incompleta. ***")
            continue
        if r[1]["verdict"] == "speech":
            continue
        # Zumbido que o filtro resolve nao e gravacao incompleta: a transcricao
        # aplica o mesmo `dehum` e recupera a fala. Gritar aqui gastaria o
        # alerta — que so serve enquanto significa alguma coisa — no caso em que
        # nada se perdeu.
        if len(r) > 2 and r[2]["verdict"] == "speech":
            log(f"[multi] {side}: zumbido de rede sobre a fala "
                f"(como gravado: din {r[1]['dynamic_db']:.1f} dB, "
                f"fala {r[1]['active_pct']:.1f}%; sem zumbido: "
                f"din {r[2]['dynamic_db']:.1f} dB, fala {r[2]['active_pct']:.1f}%). "
                f"A transcricao filtra.")
            continue
        log(f"[multi] *** ALERTA: {side} sem fala ({r[1]['verdict']}). "
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
