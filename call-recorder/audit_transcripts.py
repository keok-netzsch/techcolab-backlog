"""Varre transcripts/ procurando transcricao degenerada.

Motivo: em 2026-08-26 uma call de 43 min virou 98% de "." — o Whisper
transcreveu ~30s, travou e emitiu pontos ate o fim. A fila reportou sucesso, a
nota foi criada no vault, e so o portao de palavras do English Coach percebeu.
Uma gravacao em portugues (sem coach no caminho) teria passado batido.

O `record.transcribe()` agora recusa esse resultado na origem, mas isto existe
para (a) auditar o que ja esta gravado e (b) pegar qualquer coisa que entre por
um caminho que nao passe pela guarda.

    python audit_transcripts.py [--min-wpm 25]

Sai com codigo 1 se achar algo suspeito, para poder virar step de agente.
"""
import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
TRANSCRIPTS = HERE / "transcripts"


def measure(path: Path):
    text = path.read_text(encoding="utf-8", errors="replace")
    stamps = [float(m) for m in re.findall(r"\[(\d+\.\d)s\]", text)]
    if not stamps:
        return None
    segs = [ln for ln in text.split("\n") if ln.strip()]
    bodies = [re.sub(r"^\[.*?\]\s*", "", ln).strip() for ln in segs]
    # Um segmento so com pontuacao/traco e ruido, nao fala.
    junk = [b for b in bodies if len(b.strip(" .·-")) <= 3]
    words = sum(len(b.split()) for b in bodies if len(b.strip(" .")) > 3)
    minutes = stamps[-1] / 60
    return {
        "minutes": minutes,
        "segments": len(segs),
        "junk_pct": 100 * len(junk) / len(segs) if segs else 0,
        "wpm": words / minutes if minutes else 0,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-wpm", type=float, default=25,
                    help="abaixo disto e suspeito (1:1s saudaveis: 79-160)")
    ap.add_argument("--max-junk", type=float, default=40,
                    help="%% maximo de segmentos sem fala")
    args = ap.parse_args()

    if not TRANSCRIPTS.exists():
        print(f"nao encontrei {TRANSCRIPTS}")
        return 0

    suspects = []
    print(f"{'arquivo':50s} {'min':>6s} {'lixo%':>6s} {'pal/min':>8s}  status")
    for p in sorted(TRANSCRIPTS.glob("*.txt")):
        m = measure(p)
        if not m:
            continue
        bad = m["wpm"] < args.min_wpm or m["junk_pct"] > args.max_junk
        if bad:
            suspects.append(p.name)
        print(f"{p.name[:50]:50s} {m['minutes']:6.1f} {m['junk_pct']:6.0f} "
              f"{m['wpm']:8.0f}  {'<<< SUSPEITO' if bad else 'ok'}")

    if suspects:
        print(f"\n{len(suspects)} suspeito(s). O audio provavelmente esta bom — "
              f"conferir energia do .wav antes de assumir gravacao ruim, e "
              f"reprocessar com vad_filter=True e idioma explicito.")
        return 1
    print("\nNenhum transcript degenerado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
