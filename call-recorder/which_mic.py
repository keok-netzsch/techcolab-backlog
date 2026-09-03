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

    # Capture the failures instead of swallowing them. Suppressing this log is
    # what made the FIRST run useless: seven devices — including all three
    # "Saida do MicrofoneMic" entries, the one Teams actually uses — failed to
    # open and vanished from the report with no trace, which reads exactly like
    # "recorded, heard nothing".
    _erros = []

    t0 = time.time()
    paths = cm.capture_all(lambda: time.time() - t0 > seconds,
                           base_dir=str(Path(__file__).parent / "recordings"),
                           log=_erros.append, mics=mics)   # loopbacks incluidos
    print("   >>> pode parar <<<\n")

    import soundfile as sf

    rows, sys_rows = [], []
    for label, path in sorted(paths.items()):
        if label.startswith("sys:"):
            try:
                a, sr = sf.read(path, dtype="float32")
                sys_rows.append((label, cm.score(a if a.ndim == 1 else a[:, 0], sr)))
            except Exception:
                pass
            continue
        try:
            a, sr = sf.read(path, dtype="float32")
        except Exception as e:
            print(f"   {label}: falha ao ler ({e})")
            continue
        s = cm.score(a if a.ndim == 1 else a[:, 0], sr)
        rows.append((label, s))

    cm.cleanup(str(Path(__file__).parent / "recordings"))

    # Also to a file: the terminal is where the answer went to die the first time
    # it was run, and asking Kelvin to fish it out of scrollback wastes a round
    # trip on something the script already knows.
    out_lines = [f"{'entrada':44s} {'veredito':9s} {'dinamica':>9s} {'fala':>7s}",
                 "-" * 74]
    for label, s in sorted(rows, key=lambda r: -r[1]["active_pct"]):
        out_lines.append(f"{label[4:][:44]:44s} {s['verdict']:9s} "
                         f"{s['dynamic_db']:7.1f} dB {s['active_pct']:6.1f}%")
    for ln in out_lines:
        print(ln)

    from datetime import datetime
    report = Path(__file__).parent / "which_mic_result.txt"
    header = [f"which_mic — {datetime.now():%Y-%m-%d %H:%M:%S} — {seconds}s de voz"]

    if sys_rows:
        out_lines.append("")
        out_lines.append("SAIDAS (canal 1 - a outra pessoa):")
        for label, s2 in sorted(sys_rows, key=lambda r: -r[1]["active_pct"]):
            out_lines.append(f"   {label[4:][:41]:41s} {s2['verdict']:9s} "
                             f"{s2['dynamic_db']:7.1f} dB {s2['active_pct']:6.1f}%")
        print()
        print("SAIDAS (canal 1 - a outra pessoa):")
        for label, s2 in sorted(sys_rows, key=lambda r: -r[1]["active_pct"]):
            print(f"   {label[4:][:41]:41s} {s2['verdict']:9s} "
                  f"{s2['dynamic_db']:7.1f} dB {s2['active_pct']:6.1f}%")

    # O criterio e o DA PRODUCAO, nao um numero proprio. `pick_best` escolhe
    # qualquer stream com veredito "speech" (dinamica >= 12 dB e atividade >=
    # MIN_ACTIVE_PCT, hoje 5%). Este arquivo exigia `> 25` — um limiar solto que
    # nao vinha de lugar nenhum.
    #
    # Custo, medido em 2026-09-03: o Kelvin falou 20 s, quatro entradas ouviram
    # ("speech", ate 19.4% e 17.5 dB), e o relatorio imprimiu "NENHUMA entrada
    # ouviu a sua voz" mandando ele trocar o dispositivo padrao do Windows. A
    # producao teria escolhido a melhor delas sem hesitar — a call de 09:34
    # daquele dia gravou a voz dele com 12.2%. Diagnostico que mede diferente da
    # producao manda consertar o que nao esta quebrado, e e assim que se cria o
    # proximo defeito.
    good = [r for r in rows if r[1]["verdict"] == "speech"]
    print()
    if good:
        best = max(good, key=lambda r: r[1]["active_pct"])
        print(f"USAR ESTA: {best[0][4:]}")
        print(f"   ({best[1]['active_pct']:.0f}% de fala — a sua voz chegou aqui)")
    else:
        print("NENHUMA entrada ouviu a sua voz.")
        print("   Verifique se o microfone do fone esta selecionado no Windows")
        print("   (Configuracoes > Sistema > Som > Entrada) e rode de novo.")
        out_lines.append("NENHUMA entrada ouviu a voz.")

    if good:
        best = max(good, key=lambda r: r[1]["active_pct"])
        out_lines.append(f"USAR ESTA: {best[0][4:]}  ({best[1]['active_pct']:.0f}% de fala)")
    # Failures go in BEFORE the file is written, or the report ships without the
    # single most useful section — which is what a device that cannot be opened
    # looks like, versus one that was recorded and heard nothing.
    falhas = [e for e in _erros if "falhou" in e]
    if falhas:
        out_lines.append("")
        out_lines.append("ENTRADAS QUE NAO ABRIRAM (nao foram gravadas):")
        for e in falhas:
            out_lines.append(f"   {e}")
        print()
        print("ENTRADAS QUE NAO ABRIRAM (nao foram gravadas):")
        for e in falhas:
            print(f"   {e}")

    report.write_text(chr(10).join(header + [""] + out_lines) + chr(10),
                      encoding="utf-8")

    print()
    print("Resultado salvo em:")
    print(f"   {report}")


if __name__ == "__main__":
    main()
