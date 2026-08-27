"""
record.py — Grava microfone e transcreve com faster-whisper
Uso: python record.py [--output caminho/saida.txt]
Encerra: Ctrl+C
"""
import os

os.environ["HF_HUB_DISABLE_SSL_VERIFY"] = "1"

import argparse
import signal
import sys
from datetime import datetime

# Heavy audio/ML deps (numpy, sounddevice, soundfile, faster_whisper) are imported
# lazily inside the functions that need them, so this module can be imported for its
# pure helpers (e.g. prune_old_recordings) without PortAudio / Whisper installed —
# important for CI and for tooling that only needs the retention logic.

# --- Configuração ---
SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = "float32"
MODEL_SIZE = os.environ.get("WHISPER_MODEL", "medium")   # small | medium | large-v3
LANGUAGE = "pt"            # default; overridden by --language CLI arg
CHUNK_SECONDS = 30         # tamanho do buffer de gravação em memória
RECORDINGS_RETENTION_DAYS = 7   # áudios em recordings/ mais antigos que isto são apagados

# Dual capture: the mic alone only ever records Kelvin. In a call with a headset
# the other party never reaches the mic at all, so ~half of every 1:1 was lost
# (measured: 44% of one recording was gaps where the other person was speaking).
# WASAPI loopback grabs what the system is *playing* — i.e. the other party.
# The two sources are kept as separate channels, never mixed: channel 0 is always
# Kelvin and channel 1 is always the interlocutor, which makes speaker attribution
# exact instead of something an LLM has to guess from the text afterwards.
CAPTURE_SYSTEM_AUDIO = os.environ.get("CAPTURE_SYSTEM_AUDIO", "1") != "0"
SPEAKER_LABELS = ("Kelvin", "Interlocutor")

# --------------------

chunks = []
recording = True


def signal_handler(sig, frame):
    global recording
    print("\n\n[INFO] Encerrando gravação...")
    recording = False


def callback(indata, frames, time, status):
    if status:
        print(f"[WARN] {status}", file=sys.stderr)
    chunks.append(indata.copy())


def _log(msg: str) -> None:
    """Diagnostico que sobrevive ao pythonw.

    Sob pythonw sys.stdout e None: `print` nao levanta excecao, apenas descarta
    a mensagem. Foi por isso que a falha de 2026-08-27 registrou so "captura
    falhou" sem causa — todo o detalhe estava em prints invisiveis.
    """
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S}  [record] {msg}"
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "record.log"), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass
    try:
        print(line, flush=True)
    except Exception:
        pass


def _probe_input(device, seconds=2.0):
    """Classifica uma entrada em 'live' | 'dead' | 'floating' por uma amostra curta.

    - dead     : silencio digital (dispositivo desligado). Ex.: o Microphone
                 Array deste notebook entrega -96,7 dBFS com 0,5 dB de faixa.
    - floating : nivel alto e CONSTANTE, sem a intermitencia da fala. Assinatura
                 de entrada de jack sem nada conectado, captando zumbido. Foi o
                 que gravou 11,8 min de chiado numa call de 2026-08-27.
    - live     : varia como audio de verdade.
    """
    import numpy as np
    import sounddevice as sd
    try:
        a = sd.rec(int(seconds * SAMPLE_RATE), samplerate=SAMPLE_RATE,
                   channels=1, dtype="float32", device=device)
        sd.wait()
    except Exception as e:
        return "error", f"{e}"
    x = a[:, 0]
    win = SAMPLE_RATE // 10
    k = len(x) // win
    if k == 0:
        return "error", "amostra curta demais"
    rms = np.sqrt((x[:k * win].reshape(k, win).astype(np.float64) ** 2).mean(axis=1))
    db = lambda v: 20 * np.log10(v + 1e-12)   # noqa: E731
    mean_db, floor_db, peak_db = db(rms.mean()), db(np.percentile(rms, 10)), db(np.percentile(rms, 95))
    dyn = peak_db - floor_db
    detail = f"medio {mean_db:.1f} dBFS, dinamica {dyn:.1f} dB"
    if mean_db < -80:
        return "dead", detail
    if dyn < 6 and mean_db > -45:
        return "floating", detail
    return "live", detail


def pick_input_device():
    """Devolve (device_index, nome, motivo) de uma entrada que parece viva.

    O dispositivo padrao do Windows nao e confiavel: ele muda sozinho quando um
    fone e plugado, e pode apontar para um jack vazio. Gravar 12 minutos de
    zumbido e pior que gastar 2 segundos conferindo.
    """
    import sounddevice as sd
    default = sd.default.device[0]
    verdict, detail = _probe_input(default)
    name = sd.query_devices(default)["name"]
    if verdict == "live":
        return default, name, f"padrao, {detail}"

    skip = ("Mix", "Mapper", "Primary", "PC Speaker")
    for i, d in enumerate(sd.query_devices()):
        if i == default or d["max_input_channels"] <= 0:
            continue
        if any(s in d["name"] for s in skip):
            continue
        v2, d2 = _probe_input(i)
        if v2 == "live":
            return i, d["name"], f"padrao '{name}' estava {verdict} ({detail}); trocado, {d2}"
    # Nada vivo: fica no padrao e registra, para nao perder a gravacao inteira.
    return default, name, f"NENHUMA entrada viva; mantido o padrao ({verdict}, {detail})"


def capture_dual(stop_flag):
    """Record the mic and the system output concurrently until `stop_flag()` is true.

    Returns (mic, system) as float32 mono arrays of equal length, or None when
    loopback is unavailable (no `soundcard`, no loopback endpoint) so the caller
    can fall back to the mic-only path.
    """
    try:
        import soundcard as sc
    except ImportError:
        print("[WARN] soundcard nao instalado - gravando apenas o microfone.")
        print("       pip install soundcard  (habilita a captura do outro lado)")
        return None

    import threading
    import numpy as np

    import sounddevice as sd

    try:
        speaker = sc.default_speaker()
        loop = sc.get_microphone(speaker.name, include_loopback=True)
    except Exception as e:
        print(f"[WARN] loopback indisponivel ({e}) - gravando apenas o microfone.")
        return None

    # Nomear os dois endpoints, nao so o do loopback: o dispositivo padrao muda
    # sozinho quando um fone e plugado (2026-08-27: o mic padrao passou de
    # "Microphone Array" para o mic do jack entre uma call e outra). Sem esse
    # registro nao da para dizer, depois, se um canal mudo foi mute do usuario
    # ou endpoint errado.
    # Só registra qual e o dispositivo padrao. NAO sonda e NAO escolhe: sondar
    # abre o dispositivo, e abrir o dispositivo antes de gravar foi o que
    # quebrou a captura. Diagnostico nao pode custar a gravacao.
    try:
        _mic_name = sd.query_devices(sd.default.device[0])["name"]
    except Exception as e:
        _mic_name = f"? ({e})"
    _log("captura dupla iniciando")
    _log(f"  canal 0 (voce)  <- {_mic_name} [padrao do sistema]")
    _log(f"  canal 1 (outro) <- {speaker.name} [loopback]")

    out = {}

    def pump_mic():
        # Deliberately sounddevice, not soundcard: the WASAPI path to this mic
        # returns digital silence, while the MME path sounddevice uses is the one
        # already proven to capture in production. Never risk losing our own side.
        buf = []
        # device=None DE PROPOSITO: deixa o PortAudio resolver o padrao, que e o
        # que funcionou em producao. Passar um indice explicito vindo de sondagem
        # quebrou a captura de uma call de 50 min em 2026-08-27 — o Teams tomou o
        # dispositivo entre a sondagem e a abertura do stream. A sondagem agora
        # so informa (ver _mic_note); ela nao escolhe mais.
        try:
            with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype=DTYPE,
                                callback=lambda d, f, t, s: buf.append(d.copy())):
                while not stop_flag():
                    sd.sleep(200)
        except Exception as e:
            _log(f"microfone: falha ao abrir: {e}")
        out["mic"] = np.concatenate(buf) if buf else np.zeros((0, 1), dtype="float32")

    def pump_sys():
        buf = []
        try:
            with loop.recorder(samplerate=SAMPLE_RATE, channels=1) as rec:
                while not stop_flag():
                    buf.append(rec.record(numframes=SAMPLE_RATE // 2))
        except Exception as e:                        # one side failing must not
            print(f"[WARN] captura do loopback interrompida: {e}")   # kill the other
        out["sys"] = np.concatenate(buf) if buf else np.zeros((0, 1), dtype="float32")

    threads = [threading.Thread(target=pump_mic, daemon=True),
               threading.Thread(target=pump_sys, daemon=True)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    a, b = out.get("mic"), out.get("sys")
    empty = np.zeros((0, 1), dtype="float32")
    a = empty if a is None else a
    b = empty if b is None else b

    # NUNCA descartar tudo porque um lado falhou. A versao anterior retornava
    # None quando o mic vinha vazio, e isso jogou fora 50 min de uma call em
    # 2026-08-27 — o loopback estava intacto e foi perdido junto. Meia gravacao
    # e infinitamente melhor que nenhuma.
    if len(a) == 0 and len(b) == 0:
        _log("captura vazia nos dois canais - nada a salvar")
        return None
    if len(a) == 0:
        _log(f"!! canal 0 (mic) VAZIO. Salvando so o canal 1 "
             f"({len(b)/SAMPLE_RATE/60:.1f} min de loopback).")
        return np.zeros((len(b), 1), dtype="float32"), b
    if len(b) == 0:
        _log(f"!! canal 1 (loopback) VAZIO. Salvando so o canal 0 "
             f"({len(a)/SAMPLE_RATE/60:.1f} min de microfone).")
        return a, np.zeros((len(a), 1), dtype="float32")

    n = min(len(a), len(b))
    return a[:n], b[:n]


MIN_TRANSCRIPT_BYTES = 200   # below this, treat the transcript as a failure


def _recording_state(wav_path: str):
    """Classify a recording as ('done'|'pending'|'failed'|'orphan', detail).

    The old policy deleted by mtime alone, so a recording whose transcription had
    been failing for a week was destroyed exactly like one that succeeded. Two
    live cases made that concrete: the queue was killed mid-run twice on
    2026-08-26, and `autocapture.py` writes `.pending.json` sidecars that nothing
    consumes yet (`classify.py` is not built), so every auto-captured call was on
    a 7-day path to silent deletion.

    The clock now starts at SUCCESS, not at capture.
    """
    import json as _json

    base = os.path.splitext(wav_path)[0]

    # Awaiting classification (autocapture) or awaiting transcription (queue):
    # unprocessed work, regardless of age.
    for sidecar, why in ((base + ".pending.json", "aguarda classificacao"),
                         (base + ".job.json", "na fila de transcricao")):
        if os.path.exists(sidecar):
            return "pending", why

    done = base + ".job.json.done"
    if not os.path.exists(done):
        return "orphan", "sem sidecar"

    try:
        meta = _json.loads(open(done, encoding="utf-8").read())
        tpath = meta.get("transcript", "")
    except (OSError, ValueError) as e:
        return "failed", f"sidecar ilegivel: {e}"

    if not tpath or not os.path.exists(tpath):
        return "failed", "job concluido mas transcript nao existe"
    try:
        if os.path.getsize(tpath) < MIN_TRANSCRIPT_BYTES:
            return "failed", f"transcript com {os.path.getsize(tpath)} bytes"
    except OSError as e:
        return "failed", f"transcript ilegivel: {e}"

    return "done", os.path.basename(tpath)


def prune_old_recordings(directory: str, days: int = RECORDINGS_RETENTION_DAYS) -> int:
    """Delete recordings that were SUCCESSFULLY transcribed and are older than `days`.

    Returns the count deleted. Audio that never produced a usable transcript is
    quarantined into `failed/` instead of being removed — losing a recording is
    unrecoverable, while keeping one costs disk.
    """
    cutoff = datetime.now().timestamp() - days * 86400
    removed = 0
    quarantine = os.path.join(directory, "failed")
    try:
        names = os.listdir(directory)
    except OSError:
        return 0

    for name in names:
        if not name.lower().endswith(".wav"):
            continue
        path = os.path.join(directory, name)
        try:
            if os.path.getmtime(path) >= cutoff:
                continue
        except OSError:
            continue

        state, detail = _recording_state(path)
        if state == "pending":
            _log(f"retencao: {name} mantido - {detail}")
            continue
        if state == "failed":
            try:
                os.makedirs(quarantine, exist_ok=True)
                os.replace(path, os.path.join(quarantine, name))
                for ext in (".job.json.done", ".pending.json", ".job.json"):
                    side = os.path.splitext(path)[0] + ext
                    if os.path.exists(side):
                        os.replace(side, os.path.join(quarantine,
                                                      os.path.basename(side)))
                _log(f"retencao: {name} MOVIDO para failed/ - {detail}")
            except OSError as e:
                _log(f"retencao: falha ao quarentenar {name}: {e}")
            continue

        # 'done' (transcrito com sucesso) e 'orphan' (nada referencia este wav)
        try:
            os.remove(path)
            removed += 1
        except OSError:
            pass
    return removed


class TranscriptionTooSparse(RuntimeError):
    """Whisper returned far less speech than the audio duration implies.

    Guards the failure seen 2026-08-26 on a 43-min call: Whisper transcribed
    the first ~30s, entered a degenerate state, and emitted "." for the rest.
    The queue reported `processed=1 failed=0`, the vault note was written, and
    only the English coach's own word-count gate noticed anything was wrong.
    A Portuguese recording (no coach in the path) would have failed silently.
    """


# Healthy 1:1s on this machine run 79-160 words per minute of audio, even
# mic-only with half the conversation missing. The degenerate run scored 2.
# 25 leaves a wide margin either way.
MIN_WORDS_PER_MINUTE = 25
SANITY_MIN_MINUTES = 5          # short clips are too noisy to judge


def _sanity_check(lines: list, audio_seconds: float) -> None:
    minutes = audio_seconds / 60
    if minutes < SANITY_MIN_MINUTES:
        return
    words = sum(len(l.split("] ", 1)[-1].split()) for l in lines
                if len(l.split("] ", 1)[-1].strip(" .")) > 3)
    wpm = words / minutes if minutes else 0
    if wpm < MIN_WORDS_PER_MINUTE:
        raise TranscriptionTooSparse(
            f"{words} palavras em {minutes:.1f} min ({wpm:.1f}/min, minimo "
            f"{MIN_WORDS_PER_MINUTE}). O audio provavelmente esta bom e a "
            f"transcricao degenerou - reprocessar antes de confiar no texto."
        )


def transcribe(audio_path: str, language: str | None = LANGUAGE) -> tuple[str, str]:
    """Transcribe audio and return (text, detected_language).

    Pass language=None to let Whisper auto-detect the language.

    Raises TranscriptionTooSparse when the output is implausibly thin for the
    audio length, so the caller can fail loudly instead of storing garbage.
    """
    from faster_whisper import WhisperModel
    print(f"[INFO] Carregando modelo Whisper ({MODEL_SIZE})...")
    # 'medium' is bundled locally (model/); other sizes (e.g. 'small') download by
    # name to the HF cache — lighter/faster for short calls (WHISPER_MODEL=small).
    if MODEL_SIZE == "medium":
        model_src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model")
    else:
        model_src = MODEL_SIZE
    model = WhisperModel(model_src, device="cpu", compute_type="int8")

    # A 2-channel file comes from capture_dual(): channel 0 is the mic, channel 1
    # is the system loopback. Transcribing each separately and interleaving by
    # timestamp yields exact speaker labels — no diarization guesswork.
    import soundfile as sf
    if sf.info(audio_path).channels == 2:
        return _transcribe_dual(model, audio_path, language)

    print("[INFO] Transcrevendo...")
    # vad_filter cortando os silencios evita que o modelo carregue um estado
    # degenerado por 40 minutos — foi a diferenca entre os 1:1s do time (bons)
    # e a call do Stefan (98% de "."), gravados no mesmo dia.
    segments, info = model.transcribe(
        audio_path, language=language,
        vad_filter=True, vad_parameters={"min_silence_duration_ms": 700},
    )
    lines = []
    for seg in segments:
        ts = f"[{seg.start:05.1f}s]"
        lines.append(f"{ts} {seg.text.strip()}")
    detected = getattr(info, "language", None) or (language or "pt")

    import soundfile as sf2
    info_wav = sf2.info(audio_path)
    _sanity_check(lines, info_wav.frames / info_wav.samplerate)
    return "\n".join(lines), detected


def _transcribe_dual(model, audio_path: str, language: str | None):
    """Transcribe each channel of a dual-capture file and merge chronologically."""
    import numpy as np
    import soundfile as sf

    data, sr = sf.read(audio_path, dtype="float32")
    rows, detected = [], None

    for idx, label in enumerate(SPEAKER_LABELS):
        track = np.ascontiguousarray(data[:, idx])
        if float(np.sqrt(np.mean(track.astype(np.float64) ** 2))) < 1e-5:
            print(f"[WARN] canal {idx} ({label}) esta mudo - pulando.")
            continue
        print(f"[INFO] Transcrevendo canal {idx} ({label})...")
        segments, info = model.transcribe(track, language=language)
        for seg in segments:
            rows.append((seg.start, label, seg.text.strip()))
        detected = detected or getattr(info, "language", None)

    rows.sort(key=lambda r: r[0])
    lines = [f"[{t:05.1f}s] {label}: {text}" for t, label, text in rows]
    # Mesma guarda do caminho de 1 canal: com 2 canais o volume esperado e ainda
    # maior (os dois lados da conversa), entao um resultado esparso aqui e mais
    # suspeito, nao menos.
    _sanity_check(lines, len(data) / sr)
    return "\n".join(lines), detected or (language or "pt")


# File Processing (idea-031): accept an existing audio/video file as input instead
# of recording from the mic. faster-whisper decodes the container via ffmpeg/PyAV,
# so a video's audio track is transcribed directly with no manual extraction step.
SUPPORTED_MEDIA_EXTS = {
    ".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aac", ".wma",   # audio
    ".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v",           # video
}


def is_supported_media(path: str) -> bool:
    """True if `path` has an extension Whisper can decode (audio or video)."""
    return os.path.splitext(str(path))[1].lower() in SUPPORTED_MEDIA_EXTS


def transcribe_file(input_path: str, output_path: str | None = None,
                    language: str | None = LANGUAGE) -> tuple[str, str]:
    """Transcribe an existing audio/video file through the same pipeline as a live
    capture. Returns (transcript_path, detected_language).

    Pass language="auto" (or None) to let Whisper detect the language. Raises
    FileNotFoundError if the file is missing and ValueError for unsupported types.
    """
    if not os.path.isfile(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")
    if not is_supported_media(input_path):
        ext = os.path.splitext(input_path)[1] or "(none)"
        raise ValueError(
            f"Unsupported media type: {ext}. "
            f"Supported: {', '.join(sorted(SUPPORTED_MEDIA_EXTS))}"
        )

    if output_path:
        out_path = output_path
    else:
        # Next to the INPUT, not next to this script. Writing into the install
        # directory meant the unit test that exercises this branch dropped a
        # `transcript_reuniao_diretoria_*.txt` into the repo on every run — 76 of
        # them accumulated between 29/07 and 26/08 and were mistaken for a broken
        # recurring-meeting pipeline. A transcript belongs with its source file.
        stem = os.path.splitext(os.path.basename(input_path))[0]
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
        out_path = os.path.join(os.path.dirname(os.path.abspath(input_path)),
                                f"transcript_{stem}_{ts}.txt")

    lang_eff = None if language == "auto" else language
    transcript, detected = transcribe(input_path, language=lang_eff)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(transcript)
    # Language sidecar so the PS1 orchestrator can read it without parsing stdout.
    with open(out_path + ".lang", "w", encoding="utf-8") as f:
        f.write(detected)
    return out_path, detected


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=None,
                        help="Caminho para salvar a transcrição (.txt)")
    parser.add_argument("--language", default=LANGUAGE,
                        help="Idioma para Whisper (ex: pt, en, auto). Padrão: pt")
    parser.add_argument("--input", default=None,
                        help="Transcreve um arquivo de áudio/vídeo existente (ex.: reuniao.mp4) "
                             "em vez de gravar do microfone")
    parser.add_argument("--record-only", action="store_true",
                        help="Apenas grava e salva o .wav (sem transcrever) — para fila/processamento posterior")
    args = parser.parse_args()

    # File Processing mode: transcribe an existing file and exit. Handled before the
    # audio-capture imports so it works on machines without a mic / PortAudio.
    if args.input:
        out_path, detected = transcribe_file(args.input, args.output, args.language)
        print(f"[INFO] Idioma detectado: {detected}")
        print(f"[INFO] Transcricao salva em: {out_path}")
        print(f"DETECTED_LANG:{detected}")
        print(f"TRANSCRIPT_PATH:{out_path}")
        return

    import numpy as np
    import sounddevice as sd
    import soundfile as sf

    LANGUAGE_EFFECTIVE = None if args.language == "auto" else args.language

    signal.signal(signal.SIGINT, signal_handler)

    print("[INFO] Gravando (Ctrl+C para encerrar)...")
    print(f"[INFO] Idioma: {LANGUAGE_EFFECTIVE} | Modelo: {MODEL_SIZE} | CPU int8\n")

    audio = None
    if CAPTURE_SYSTEM_AUDIO:
        dual = capture_dual(lambda: not recording)
        if dual is not None:
            mic_track, sys_track = dual
            audio = np.concatenate([mic_track, sys_track], axis=1)  # ch0 mic, ch1 sys
            print(f"[INFO] Capturados 2 canais ({len(audio)/SAMPLE_RATE:.1f}s cada).")

    if audio is None:
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS,
                            dtype=DTYPE, callback=callback):
            while recording:
                sd.sleep(500)

        if not chunks:
            print("[ERROR] Nenhum áudio capturado.")
            sys.exit(1)

        audio = np.concatenate(chunks, axis=0)
    duration = len(audio) / SAMPLE_RATE
    print(f"[INFO] Áudio capturado: {duration:.1f}s")

    # Base name shared by the transcript (.txt) and the saved recording (.wav).
    # Derived from --output when provided, otherwise the timestamp default.
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if args.output:
        out_path = args.output
        base_name = os.path.splitext(os.path.basename(args.output))[0]
    else:
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
        base_name = f"transcript_{ts}"
        out_path = os.path.join(script_dir, f"{base_name}.txt")

    # Persist the raw audio permanently so it can be re-transcribed later with a
    # different language/model (previously written to a temp file and deleted).
    recordings_dir = os.path.join(script_dir, "recordings")
    os.makedirs(recordings_dir, exist_ok=True)
    _pruned = prune_old_recordings(recordings_dir, RECORDINGS_RETENTION_DAYS)
    if _pruned:
        print(f"[CLEAN] {_pruned} gravação(ões) com mais de {RECORDINGS_RETENTION_DAYS} dias removida(s).")
    wav_path = os.path.join(recordings_dir, f"{base_name}.wav")
    sf.write(wav_path, audio, SAMPLE_RATE)
    print(f"[INFO] Áudio salvo em: {wav_path}")

    if args.record_only:
        # Decoupled flow: stop here (fast, no Whisper). The queue runner transcribes
        # and processes this .wav later, off the user's working hours.
        print(f"WAV_PATH:{wav_path}")
        return

    transcript, detected_lang = transcribe(wav_path, language=LANGUAGE_EFFECTIVE)
    print(f"[INFO] Idioma detectado: {detected_lang}")

    print("\n" + "=" * 60)
    print("TRANSCRICAO")
    print("=" * 60)
    print(transcript)
    print("=" * 60)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(transcript)

    # Write language sidecar so the PS1 orchestrator can read it without parsing stdout
    lang_sidecar = out_path + ".lang"
    with open(lang_sidecar, "w", encoding="utf-8") as f:
        f.write(detected_lang)

    print(f"\n[INFO] Transcricao salva em: {out_path}")
    print(f"[INFO] Arquivo: {out_path}")
    print(f"DETECTED_LANG:{detected_lang}")

    # Sinaliza caminho para o orquestrador (stdout ultima linha)
    print(f"TRANSCRIPT_PATH:{out_path}")


if __name__ == "__main__":
    main()
