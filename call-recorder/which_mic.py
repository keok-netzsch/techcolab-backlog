"""Which input actually hears Kelvin? Record every candidate while he speaks.

Deliberately driven by a HUMAN VOICE and not by a test tone. On 2026-08-28 a
tone-based check declared "Saida do MicrofoneMic" healthy at 84% activity, and
the three calls that followed recorded 1-2% speech on that channel. The tone was
playing out of the same physical jack, so the input was picking up electrical
crosstalk from the output — a signal perfectly correlated with the test, and
completely unrelated to whether the microphone works.

Voice cannot be faked that way. Run this, talk for the whole countdown, and the
answer is the input that shows real speech activity.

    python which_mic.py [segundos]
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import capture_multi as cm  # noqa: E402


def all_inputs():
    """Every input device on every host API, minus the ones that are not mics.

    The narrow list missed the answer once already: it allowed only MME and
    WASAPI, and this machine exposes `FrontMic` — the front-panel jack a headset
    plugs into — solely through WDM-KS. A diagnostic has no business being
    selective; being exhaustive is the entire point.
    """
    import sounddevice as sd

    apis = {i: a["name"] for i, a in enumerate(sd.query_hostapis())}
    out = []
    for idx, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] <= 0:
            continue
        name = d["name"]
        if any(s in name for s in ("Mapper", "Primary", "PC Speaker")):
            continue
        out.append((idx, f"{name}  [{apis.get(d['hostapi'], '?')}]"))
    return out


def main():
    seconds = int(sys.argv[1]) if len(sys.argv) > 1 else 15

    mics = all_inputs()
    print(f"Vou gravar {len(mics)} entrada(s) por {seconds}s:")
    for _, name in mics:
        print(f"   - {name}")
    print()
    print("FALE SEM PARAR ate o fim. Conte em voz alta, leia qualquer coisa —")
    print("o que importa e voz continua, nao o conteudo.")
    print()
    for i in (3, 2, 1):
        print(f"   comecando em {i}...", flush=True)
        time.sleep(1)
    print("   >>> FALE AGORA <<<", flush=True)

    t0 = time.time()
    paths = cm.capture_all(lambda: time.time() - t0 > seconds,
                           base_dir=str(Path(__file__).parent / "recordings"),
                           log=lambda m: None, mics=mics, loops=[])
    print("   >>> pode parar <<<\n")

    import soundfile as sf

    rows = []
    for label, path in sorted(paths.items()):
        if not label.startswith("mic:"):
            continue
        try:
            a, sr = sf.read(path, dtype="float32")
        except Exception as e:
            print(f"   {label}: falha ao ler ({e})")
            continue
        s = cm.score(a if a.ndim == 1 else a[:, 0], sr)
        rows.append((label, s))

    cm.cleanup(str(Path(__file__).parent / "recordings"))

    print(f"{'entrada':44s} {'veredito':9s} {'dinamica':>9s} {'fala':>7s}")
    print("-" * 74)
    for label, s in sorted(rows, key=lambda r: -r[1]["active_pct"]):
        print(f"{label[4:][:44]:44s} {s['verdict']:9s} "
              f"{s['dynamic_db']:7.1f} dB {s['active_pct']:6.1f}%")

    good = [r for r in rows if r[1]["verdict"] == "speech" and r[1]["active_pct"] > 25]
    print()
    if good:
        best = max(good, key=lambda r: r[1]["active_pct"])
        print(f"USAR ESTA: {best[0][4:]}")
        print(f"   ({best[1]['active_pct']:.0f}% de fala — a sua voz chegou aqui)")
    else:
        print("NENHUMA entrada ouviu a sua voz.")
        print("   Verifique se o microfone do fone esta selecionado no Windows")
        print("   (Configuracoes > Sistema > Som > Entrada) e rode de novo.")


if __name__ == "__main__":
    main()
