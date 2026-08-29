"""Veredito sobre a captura em 2 canais da gravacao mais recente.

A pergunta que isto responde: o canal 1 (a outra pessoa, via loopback WASAPI)
capturou fala de verdade, ou o arquivo tem so o Kelvin como antes do 2.0?

Nao basta olhar RMS global: um canal mudo com um pouco de ruido de fundo tem
RMS baixo mas nao-zero. O que separa "tem fala" de "tem chiado" e a fracao de
tempo ACIMA do piso de ruido do proprio canal — fala e intermitente e bem mais
alta que o piso; chiado e continuo e plano.

    python verify_capture.py [caminho.wav]

Sem argumento, pega o .wav mais recente de recordings/.
"""
import sys
import wave
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
RECORDINGS = HERE / "recordings"
LABELS = ("canal 0 — voce (mic)", "canal 1 — o outro (loopback)")


def db(x):
    return 20 * np.log10(x + 1e-12)


def analyse(track, sr):
    """Fracao do tempo com fala, e niveis, em janelas de 0,5 s."""
    win = int(sr * 0.5)
    n = len(track) // win
    if n == 0:
        return None
    frames = track[:n * win].reshape(n, win)
    rms = np.sqrt((frames.astype(np.float64) ** 2).mean(axis=1))
    floor = np.percentile(rms, 10)              # piso do proprio canal
    peak = np.percentile(rms, 95)
    # 12 dB acima do piso e um limiar conservador para "alguem falando".
    thresh = max(floor * 4, 10 ** (-60 / 20))
    active = float((rms > thresh).mean())
    return {"active_pct": 100 * active, "floor_db": db(floor),
            "peak_db": db(peak), "rms_db": db(rms.mean()),
            "dynamic_db": db(peak) - db(floor)}


def main():
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
    else:
        wavs = sorted(RECORDINGS.glob("*.wav"), key=lambda p: p.stat().st_mtime)
        if not wavs:
            print("nenhuma gravacao em recordings/")
            return 1
        path = wavs[-1]

    print(f"arquivo: {path.name}")
    with wave.open(str(path)) as w:
        sr, ch, n = w.getframerate(), w.getnchannels(), w.getnframes()
        raw = np.frombuffer(w.readframes(n), dtype=np.int16)
    print(f"duracao: {n / sr / 60:.1f} min | {sr} Hz | {ch} canal(is)\n")

    if ch == 1:
        print("!! 1 CANAL — gravacao no formato antigo (so o microfone).")
        print("   Se isto veio do autocapture, a captura dupla caiu para o")
        print("   fallback: conferir se `soundcard` esta instalado e se o")
        print("   endpoint de loopback existe (autocapture.log diz qual usou).")
        return 1

    data = raw.reshape(-1, ch).astype(np.float64) / 32768
    results = []
    for i, label in enumerate(LABELS[:ch]):
        r = analyse(data[:, i], sr)
        results.append(r)
        print(f"{label}")
        print(f"   tempo com fala : {r['active_pct']:5.1f}%")
        print(f"   nivel medio    : {r['rms_db']:6.1f} dBFS")
        print(f"   piso de ruido  : {r['floor_db']:6.1f} dBFS")
        print(f"   faixa dinamica : {r['dynamic_db']:6.1f} dB\n")

    mic, other = results[0], results[1]
    print("=" * 58)
    if other["active_pct"] < 2 or other["dynamic_db"] < 6:
        print("VEREDITO: canal 1 SEM FALA. O loopback nao capturou o outro lado.")
        print("Conferir no autocapture.log qual endpoint foi usado e se o audio")
        print("da call saiu por ele (fone USB/Bluetooth muda o endpoint ativo).")
        return 1
    if mic["active_pct"] < 2:
        print("VEREDITO: canal 0 SEM FALA. O microfone nao entrou.")
        print("O outro lado foi gravado, voce nao — pior que o estado anterior.")
        return 1
    print("VEREDITO: OS DOIS CANAIS TEM FALA. Captura dupla funcionando.")
    print(f"Proporcao aproximada de fala — voce {mic['active_pct']:.0f}% / "
          f"o outro {other['active_pct']:.0f}%.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
