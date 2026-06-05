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


def transcribe(audio_path: str, language: str | None = LANGUAGE) -> tuple[str, str]:
    """Transcribe audio and return (text, detected_language).

    Pass language=None to let Whisper auto-detect the language.
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
    print("[INFO] Transcrevendo...")
    segments, info = model.transcribe(audio_path, language=language)
    lines = []
    for seg in segments:
        ts = f"[{seg.start:05.1f}s]"
        lines.append(f"{ts} {seg.text.strip()}")
    detected = getattr(info, "language", None) or (language or "pt")
    return "\n".join(lines), detected


def main():
    import numpy as np
    import sounddevice as sd
    import soundfile as sf

    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=None,
                        help="Caminho para salvar a transcrição (.txt)")
    parser.add_argument("--language", default=LANGUAGE,
                        help="Idioma para Whisper (ex: pt, en). Padrão: pt")
    parser.add_argument("--record-only", action="store_true",
                        help="Apenas grava e salva o .wav (sem transcrever) — para fila/processamento posterior")
    args = parser.parse_args()

    LANGUAGE_EFFECTIVE = None if args.language == "auto" else args.language

    signal.signal(signal.SIGINT, signal_handler)

    print("[INFO] Gravando microfone (Ctrl+C para encerrar)...")
    print(f"[INFO] Idioma: {LANGUAGE_EFFECTIVE} | Modelo: {MODEL_SIZE} | CPU int8\n")

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
