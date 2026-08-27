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

    print("[INFO] Captura dupla ativa:")
    print(f"       canal 0 (voce)  <- microfone padrao [sounddevice]")
    print(f"       canal 1 (outro) <- {speaker.name} [loopback]")

    out = {}

    def pump_mic():
        # Deliberately sounddevice, not soundcard: the WASAPI path to this mic
        # returns digital silence, while the MME path sounddevice uses is the one
        # already proven to capture in production. Never risk losing our own side.
        buf = []
        try:
            with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype=DTYPE,
                                callback=lambda d, f, t, s: buf.append(d.copy())):
                while not stop_flag():
                    sd.sleep(200)
        except Exception as e:
            print(f"[WARN] captura do microfone interrompida: {e}")
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
    if a is None or b is None or len(a) == 0:
        return None

    n = min(len(a), len(b)) if len(b) else len(a)
    if len(b) == 0:
        b = np.zeros((n, 1), dtype="float32")
    return a[:n], b[:n]


def prune_old_recordings(directory: str, days: int = RECORDINGS_RETENTION_DAYS) -> int:
    """Delete .wav files in `directory` older than `days`. Returns count removed.
    Keeps recent audio for re-transcription while preventing unbounded growth."""
    cutoff = datetime.now().timestamp() - days * 86400
    removed = 0
    try:
        for name in os.listdir(directory):
            if not name.lower().endswith(".wav"):
                continue
            path = os.path.join(directory, name)
            try:
                if os.path.getmtime(path) < cutoff:
                    os.remove(path)
                    removed += 1
            except OSError:
                pass
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
