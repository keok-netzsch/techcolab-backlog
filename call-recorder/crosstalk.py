"""Diafonia: a voz do outro entrou no canal do Kelvin?

Substitui o criterio que vigorava ate 2026-09-04, `Kelvin% + Interlocutor% > 120`.
Aquilo nao media diafonia. Media "os dois canais estao ocupados", e um microfone
aberto num ambiente com ruido estoura sozinho, sem uma palavra cruzada.

CUSTO MEDIDO. Em 04/09 as 9 gravacoes que o criterio antigo havia acusado foram
remedidas contra o audio:

    acusadas   LIFT 0.46 – 0.92   corr -0.26 – -0.15
    limpas     LIFT 0.60 – 1.06   corr -0.07 – -0.01

Os dois grupos se sobrepoem. O gate nunca separou nada — inclusive as 6 de 17 que
ficaram registradas como "contaminadas" entre 28/08 e 02/09. Nenhuma delas tem
diafonia.

O QUE MEDE. Envelope RMS dos dois canais em janelas de 50 ms, e a correlacao de
Pearson entre eles.

  - Conversa normal e alternada: um fala, o outro cala. Correlacao NEGATIVA.
    Nas 16 gravacoes reais medidas ficou entre -0.26 e -0.01, sem excecao.
  - Com vazamento o canal do Kelvin sobe junto com o do outro. Correlacao sobe
    monotonicamente com o ganho do vazamento.

CALIBRACAO. Injetando `ch0 += ganho * ch1` em duas gravacoes reais, uma de mic
quieto e outra de mic quente:

    ganho   corr (mic quieto)   corr (mic quente)
    0.00         -0.05               -0.17
    0.10         -0.02               +0.05
    0.20         +0.06               +0.35
    0.35         +0.20               +0.68
    0.50         +0.34               +0.84

Por isso `AVISO = 0.10` e `GRAVE = 0.30`: pega vazamento a partir de ~20% de
ganho, e ainda deixa 0.11 de margem sobre o pior caso limpo ja observado.

POR QUE NAO LIFT. `P(ch0 ativo | ch1 ativo) / P(ch0 ativo | ch1 calado)` tambem
sobe com o vazamento, mas SATURA quando o mic ja esta quente: na gravacao de mic
quente o LIFT parou em 1.20 mesmo com ganho 0.8, enquanto a correlacao foi a 0.94.
Um detector que fica cego justamente na gravacao problematica nao serve. O LIFT
continua sendo calculado e reportado — ajuda a ler o caso, nao decide.

ONDE E MEDIDO. No `autocapture`, com os dois canais ainda em memoria, gravado no
sidecar (`crosstalk`). O gate le esse numero. Nao recalcula do `.wav`: o
`--todos` varre a pasta inteira, e reabrir 35 arquivos de ~150 MB transformaria
um gate de segundos em um de minutos. Gravacao sem o campo devolve "nao medido",
nunca um veredito — ausencia de dado nao e acusacao (mesma regra do `canal_mudo`).
Para preencher o que ja existe: `python crosstalk.py --backfill`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
RECORDINGS = HERE / "recordings"

WIN_MS = 50
AVISO = 0.10
GRAVE = 0.30


def medir_arrays(ch0, ch1, rate: int, win_ms: int = WIN_MS) -> dict:
    """{'corr', 'lift', 'ch0_pct', 'ch1_pct', 'win_ms'} a partir dos dois canais.

    Aceita float32 em qualquer escala: so o envelope importa, e o piso de -60 dBFS
    e aplicado sobre o proprio maximo teorico de int16, entao a entrada e
    normalizada antes.
    """
    import numpy as np

    a = np.asarray(ch0, dtype=np.float64).reshape(-1)
    b = np.asarray(ch1, dtype=np.float64).reshape(-1)
    n = min(len(a), len(b))
    if n == 0:
        return {"corr": None, "lift": None, "ch0_pct": 0.0, "ch1_pct": 0.0,
                "win_ms": win_ms}
    pico = max(float(np.abs(a[:n]).max()), float(np.abs(b[:n]).max()), 1e-9)
    a, b = a[:n] / pico, b[:n] / pico

    win = max(int(rate * win_ms / 1000), 1)
    k = n // win
    if k < 2:
        return {"corr": None, "lift": None, "ch0_pct": 0.0, "ch1_pct": 0.0,
                "win_ms": win_ms}
    env = np.stack([
        np.sqrt((a[:k * win].reshape(k, win) ** 2).mean(axis=1)),
        np.sqrt((b[:k * win].reshape(k, win) ** 2).mean(axis=1)),
    ], axis=1)

    ativo = []
    for c in (0, 1):
        v = env[:, c]
        piso = float(np.percentile(v, 10))
        ativo.append(v > max(piso * 4, 10 ** (-60 / 20)))
    a0, a1 = ativo

    on = float(a0[a1].mean()) if a1.any() else None
    off = float(a0[~a1].mean()) if (~a1).any() else None
    lift = (on / off) if (on is not None and off) else None

    # Canal constante nao tem correlacao definida; numpy devolve nan com warning.
    if env[:, 0].std() == 0 or env[:, 1].std() == 0:
        corr = None
    else:
        corr = float(np.corrcoef(env[:, 0], env[:, 1])[0, 1])

    return {
        "corr": None if corr is None else round(corr, 3),
        "lift": None if lift is None else round(lift, 3),
        "ch0_pct": round(float(a0.mean()) * 100, 1),
        "ch1_pct": round(float(a1.mean()) * 100, 1),
        "win_ms": win_ms,
    }


def medir_wav(path, win_ms: int = WIN_MS) -> dict | None:
    """Le um .wav estereo do disco. None quando nao da para medir."""
    import wave

    import numpy as np

    try:
        with wave.open(str(path), "rb") as w:
            if w.getnchannels() != 2 or w.getsampwidth() != 2:
                return None
            rate = w.getframerate()
            raw = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    except Exception:
        return None
    if raw.size == 0:
        return None
    raw = raw.reshape(-1, 2).astype(np.float32)
    return medir_arrays(raw[:, 0], raw[:, 1], rate, win_ms=win_ms)


def veredito(corr) -> str:
    """'' | 'aviso' | 'grave'. `None` (nao medido) nunca acusa."""
    if corr is None:
        return ""
    if corr >= GRAVE:
        return "grave"
    if corr >= AVISO:
        return "aviso"
    return ""


def descrever(m: dict) -> str:
    if not m:
        return ""
    if m.get("corr") is None:
        return "nao mensuravel (um canal sem variacao)"
    partes = [f"correlacao entre canais {m['corr']:+.2f}"]
    if m.get("lift") is not None:
        partes.append(f"lift {m['lift']:.2f}")
    partes.append(f"Kelvin {m.get('ch0_pct', 0):.1f}% / interlocutor {m.get('ch1_pct', 0):.1f}%")
    corpo = ", ".join(partes)
    if veredito(m["corr"]):
        return f"voz do interlocutor no canal do Kelvin ({corpo})"
    return f"sem diafonia ({corpo})"


# ── backfill dos sidecars que ainda tem .wav ─────────────────────────────────

def _sidecars(raiz: Path, stem: str):
    for sufixo in (".pending.json", ".pending.json.classified"):
        p = raiz / (stem + sufixo)
        if p.exists():
            yield p


def backfill(rdir=None, forcar: bool = False, log=print) -> int:
    raiz = Path(rdir) if rdir else RECORDINGS
    n = 0
    for wav in sorted(raiz.glob("*.wav")):
        stem = wav.stem
        alvos = list(_sidecars(raiz, stem))
        if not alvos:
            continue
        if not forcar and all(
            (json.loads(p.read_text(encoding="utf-8")) or {}).get("crosstalk")
            for p in alvos
        ):
            continue
        m = medir_wav(wav)
        if m is None:
            log(f"  {stem}: nao deu para medir")
            continue
        for p in alvos:
            j = json.loads(p.read_text(encoding="utf-8")) or {}
            j["crosstalk"] = m
            p.write_text(json.dumps(j, ensure_ascii=False, indent=2), encoding="utf-8")
        nivel = veredito(m["corr"]) or "ok"
        log(f"  {stem}: {nivel:5}  {descrever(m)}")
        n += 1
    return n


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--backfill" in argv:
        print("Medindo diafonia dos .wav que ainda existem:")
        n = backfill(forcar="--forcar" in argv)
        print(f"{n} sidecar(s) atualizado(s).")
        return 0
    alvos = [a for a in argv if not a.startswith("--")]
    if not alvos:
        print(__doc__.strip().splitlines()[0])
        print("\n  python crosstalk.py <arquivo.wav>")
        print("  python crosstalk.py --backfill [--forcar]")
        return 0
    for a in alvos:
        m = medir_wav(a)
        print(f"{a}: {descrever(m) if m else 'nao deu para medir'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
