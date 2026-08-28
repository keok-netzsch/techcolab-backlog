"""Quality gate for Whisper transcripts: catch the parts that are not real speech.

Why the existing guard was not enough
-------------------------------------
`TranscriptionTooSparse` judges the WHOLE file by words-per-minute, so it catches
"everything degenerated" and misses "a stretch degenerated". On 2026-08-28 the
OKR 05 call passed it comfortably — 8209 words over 45 minutes — while the first
15 minutes of Kelvin's channel were 30 consecutive hallucinations reading "This
is the end of this video, I hope you enjoyed it". Kelvin was about to forward
that to Ana.

What actually gives it away
---------------------------
1. EXACT 30.0-SECOND SPACING. Whisper decodes in 30 s windows. When a window has
   no speech it still emits something, and those emissions land on 0.0, 30.0,
   60.0, 90.0 ... Real speech never repeatedly starts on a round window boundary.
   This is the strongest signal and it needs no phrase list.
2. Training-set phrases. YouTube outros and subtitle credits, in several
   languages, are what the model falls back to on empty audio.
3. Internal repetition — "I'm sorry, I'm sorry, I'm sorry, ...".

Signals 2 and 3 are language- and model-specific and will age. Signal 1 is
structural: it holds for any language and any phrase the model happens to invent.

    python transcript_quality.py <arquivo.txt>     # relatorio
    python transcript_quality.py --todos           # audita transcripts/
    python transcript_quality.py <arquivo> --limpar  # grava versao limpa
"""
from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).parent
TRANSCRIPTS = HERE / "transcripts"

WINDOW = 30.0          # faster-whisper decode window, in seconds
WINDOW_TOL = 0.15      # how close to a boundary still counts as "on" it
MIN_WINDOW_RUN = 3     # consecutive boundary hits before it means anything

# Phrases the model falls back to when the audio carries no speech. Kept short
# and matched case-insensitively; this list is a convenience, not the mechanism.
FALLBACK_PHRASES = (
    r"end of (this|the) video", r"hope you enjoyed", r"thanks? for watching",
    r"please (leave a )?(like|subscribe)", r"don'?t forget to subscribe",
    r"see you (in the )?next (video|time)", r"subtitles? (by|are)",
    r"amara\.org", r"legendas? (pela|por)", r"obrigad[oa] por assistir",
    r"inscreva-se", r"\[m[uú]sica\]", r"\[music\]", r"untertitel",
    r"sous-titres", r"transcri(be|ption|pcion) (by|por)",
)
_RX_FALLBACK = re.compile("|".join(FALLBACK_PHRASES), re.I)

_RX_LINE = re.compile(r"^\[(\d+(?:\.\d+)?)s\]\s*(?:([^:]{1,32}):\s*)?(.*)$")


def _fold(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s.lower())
                   if unicodedata.category(c) != "Mn")


def parse(text: str) -> list:
    """[(start_seconds, speaker_or_None, utterance, raw_line)] for timestamped lines."""
    out = []
    for raw in text.splitlines():
        m = _RX_LINE.match(raw.strip())
        if m:
            out.append((float(m.group(1)), m.group(2), m.group(3).strip(), raw))
    return out


def on_window_boundary(t: float) -> bool:
    return abs(t / WINDOW - round(t / WINDOW)) * WINDOW <= WINDOW_TOL


def window_runs(rows: list, min_run: int = MIN_WINDOW_RUN) -> list:
    """Runs of consecutive lines that all start on a 30 s boundary.

    This is the fingerprint of empty-audio decoding: Whisper emitting one
    invented line per silent window. Three in a row is already conclusive —
    the chance of real speech starting on three consecutive round boundaries
    is negligible.
    """
    runs, atual = [], []
    for r in rows:
        if on_window_boundary(r[0]):
            atual.append(r)
        else:
            if len(atual) >= min_run:
                runs.append(atual)
            atual = []
    if len(atual) >= min_run:
        runs.append(atual)
    return runs


def internal_repetition(utterance: str, threshold: float = 0.7,
                        min_words: int = 6, min_reps: int = 3) -> bool:
    """Machine degeneration, not a person repeating themselves for emphasis.

    Calibrated against real lines from both sides. Human speech that must NOT be
    flagged, all Portuguese conversational emphasis:
        "E, o VR, o VR."
        "Nao e o Cassio, nao e o Cassio."
        "Isso e legal, isso e legal."
    Machine degeneration that MUST be flagged:
        "I'm sorry, I'm sorry, I'm sorry, I'm sorry, I'm sorry, ..."

    What separates them is how MANY times, not whether. People say a thing twice;
    a decoder stuck in a loop says it until the window ends. So a multi-word
    phrase needs three or more consecutive repeats, not two. That deliberately
    gives up the rare two-pair case ("to do to do to the way to the way") —
    catching one extra line is not worth flagging 15 of 20 files, because a gate
    that cries wolf stops being read, and the 30 s window signal already catches
    hallucination that appears in bulk.
    """
    words = re.findall(r"[\w']+", utterance.lower())
    if len(words) < min_words:
        return False
    covered = [False] * len(words)
    for n in range(1, min(5, len(words) // 2 + 1)):
        i = 0
        while i + 2 * n <= len(words):
            gram = words[i:i + n]
            j, reps = i + n, 1
            while j + n <= len(words) and words[j:j + n] == gram:
                reps, j = reps + 1, j + n
            if reps >= (4 if n == 1 else min_reps):
                for k in range(i, j):
                    covered[k] = True
                i = j
            else:
                i += 1
    return sum(covered) / len(words) >= threshold


def scan(text: str) -> dict:
    """Full report. `suspect` holds the raw lines that should not be trusted."""
    rows = parse(text)
    if not rows:
        return {"ok": False, "reason": "sem linhas com timestamp",
                "rows": 0, "suspect": [], "runs": [], "speakers": {}}

    suspect, motivos = {}, {}

    for run in window_runs(rows):
        for r in run:
            suspect[r[3]] = r
            motivos[r[3]] = f"janela vazia de 30s (bloco de {len(run)})"

    for r in rows:
        if _RX_FALLBACK.search(_fold(r[2])):
            suspect[r[3]] = r
            motivos.setdefault(r[3], "frase de treino do modelo")
        elif internal_repetition(r[2]):
            suspect[r[3]] = r
            motivos.setdefault(r[3], "repeticao degenerada")

    speakers = {}
    for r in rows:
        sp = r[1] or "(sem rotulo)"
        d = speakers.setdefault(sp, {"total": 0, "suspeitas": 0})
        d["total"] += 1
        if r[3] in suspect:
            d["suspeitas"] += 1

    dur = rows[-1][0] - rows[0][0]
    limpas = [r for r in rows if r[3] not in suspect]
    palavras = sum(len(r[2].split()) for r in limpas)

    return {
        "ok": not suspect,
        "rows": len(rows),
        "suspect": list(suspect.values()),
        "motivos": motivos,
        "runs": window_runs(rows),
        "speakers": speakers,
        "duration_min": round(dur / 60, 1),
        "clean_words": palavras,
        "wpm": round(palavras / (dur / 60), 1) if dur > 60 else None,
    }


def clean(text: str):
    """Return (cleaned_text, removed_raw_lines)."""
    rep = scan(text)
    fora = {r[3] for r in rep["suspect"]}
    mantidas = [ln for ln in text.splitlines() if ln.strip() and ln not in fora]
    return "\n".join(mantidas), sorted(fora)


def _relatorio(path: Path, verbose: bool = True) -> dict:
    rep = scan(path.read_text(encoding="utf-8", errors="replace"))
    n = len(rep["suspect"])
    marca = "OK  " if rep["ok"] else "AVISO"
    print(f"{marca} {path.name[:44]:44s} {rep['rows']:5d} linhas  "
          f"{n:4d} suspeitas" + (f"  ({rep['duration_min']} min)" if rep.get("duration_min") else ""))
    if verbose and n:
        for sp, d in rep["speakers"].items():
            if d["suspeitas"]:
                pct = d["suspeitas"] / d["total"] * 100
                print(f"        {sp:14s} {d['suspeitas']:4d}/{d['total']:<4d} ({pct:.0f}% suspeito)")
        for run in rep["runs"]:
            print(f"        bloco de janela vazia: {run[0][0]/60:.1f} min -> "
                  f"{run[-1][0]/60:.1f} min ({len(run)} linhas)")
        for r in rep["suspect"][:3]:
            print(f"        ex.: {r[3][:88]}")
    return rep


def main():
    ap = argparse.ArgumentParser(description="Gate de qualidade de transcricao")
    ap.add_argument("arquivo", nargs="?")
    ap.add_argument("--todos", action="store_true", help="audita transcripts/")
    ap.add_argument("--limpar", action="store_true", help="grava <nome>_limpo.txt")
    a = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    if a.todos:
        # .log.txt sao logs do gravador, nao transcricao; .lang e o sidecar de
        # idioma. Auditar isso so produz alarme sobre arquivo que nao e transcript.
        arquivos = sorted(p for p in TRANSCRIPTS.glob("*.txt")
                          if not p.name.endswith((".lang", ".log.txt")))
        ruins = 0
        for p in arquivos:
            if not _relatorio(p, verbose=False)["ok"]:
                ruins += 1
        print("-" * 78)
        print(f"{len(arquivos)} transcricoes, {ruins} com trechos suspeitos")
        return 0

    if not a.arquivo:
        print(__doc__)
        return 1

    p = Path(a.arquivo)
    if not p.exists():
        p = TRANSCRIPTS / a.arquivo
    if not p.exists():
        print(f"nao encontrei {a.arquivo}")
        return 1

    rep = _relatorio(p)
    if a.limpar and not rep["ok"]:
        texto, fora = clean(p.read_text(encoding="utf-8", errors="replace"))
        out = p.with_name(p.stem + "_limpo.txt")
        out.write_text(texto + "\n", encoding="utf-8")
        print(f"\n{len(fora)} linhas removidas -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
