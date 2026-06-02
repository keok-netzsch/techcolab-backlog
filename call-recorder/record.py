"""
record.py — Grava microfone e transcreve com faster-whisper
Uso: python record.py [--output caminho/saida.txt]
Encerra: Ctrl+C
"""
import os
os.environ["HF_HUB_DISABLE_SSL_VERIFY"] = "1"

import sys
import signal
import tempfile
import argparse
from datetime import datetime
from datetime import datetime

import numpy as np
import sounddevice as sd
import soundfile as sf
from faster_whisper import WhisperModel

# --- Configuração ---
SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = "float32"
MODEL_SIZE = "medium"      # small | medium | large-v3
LANGUAGE = "pt"            # default; overridden by --language CLI arg
CHUNK_SECONDS = 30         # tamanho do buffer de gravação em memória

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


def transcribe(audio_path: str, language: str = LANGUAGE) -> str:
    print("[INFO] Carregando modelo Whisper (primeira vez faz download ~460MB)...")
    model = WhisperModel(r"C:\Users\Kelvin.okuda\Scripts\call-recorder\model", device="cpu", compute_type="int8")
    print("[INFO] Transcrevendo...")
    segments, info = model.transcribe(audio_path, language=language)
    lines = []
    for seg in segments:
        ts = f"[{seg.start:05.1f}s]"
        lines.append(f"{ts} {seg.text.strip()}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=None,
                        help="Caminho para salvar a transcrição (.txt)")
    parser.add_argument("--language", default=LANGUAGE,
                        help="Idioma para Whisper (ex: pt, en). Padrão: pt")
    args = parser.parse_args()

    LANGUAGE_EFFECTIVE = args.language

    signal.signal(signal.SIGINT, signal_handler)

    print(f"[INFO] Gravando microfone (Ctrl+C para encerrar)...")
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

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        sf.write(f.name, audio, SAMPLE_RATE)
        tmp_path = f.name

    try:
        transcript = transcribe(tmp_path, language=LANGUAGE_EFFECTIVE)
    finally:
        os.unlink(tmp_path)

    print("\n" + "=" * 60)
    print("TRANSCRIÇÃO")
    print("=" * 60)
    print(transcript)
    print("=" * 60)

    # Salvar em arquivo
    if args.output:
        out_path = args.output
    else:
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
        out_path = os.path.join(os.path.dirname(__file__), f"transcript_{ts}.txt")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(transcript)

    print(f"\n[INFO] Transcrição salva em: {out_path}")
    print(f"[INFO] Arquivo: {out_path}")

    # Sinaliza caminho para o orquestrador (stdout última linha)
    print(f"TRANSCRIPT_PATH:{out_path}")


if __name__ == "__main__":
    main()
