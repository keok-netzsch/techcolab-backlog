"""Turn autocapture `.pending.json` sidecars into `.job.json` the queue can route.

This is the half of Call Recorder 2.0 that was never built. Autocapture records
Teams calls on its own and writes `<base>.wav` + `<base>.pending.json`, but
nothing consumed those, so every automatically captured call sat in recordings/
and never reached the vault — 11 of them by 2026-08-28, 290 minutes of audio.

Classification comes from the Teams window title captured at record time, matched
against the folders that actually exist in the vault. Names are never invented:
a title that matches nobody becomes a loose note (`kind: note`) rather than being
filed under a guess.

    python classify.py            # mostra o que faria, nao escreve
    python classify.py --apply    # grava os .job.json
    python classify.py --apply --only 2026-08-28   # so os desta data
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
RECORDINGS = HERE / "recordings"
TRANSCRIPTS = HERE / "transcripts"

VAULT = Path(os.environ.get(
    "TECHCOLAB_VAULT_ROOT",
    Path.home() / "OneDrive - NETZSCH" / "Documents" / "TechColab_D&A_KO"))

# A meeting whose title matches none of these is a project meeting, not a 1:1.
MEETING_HINTS = ("daily", "planning", "war room", "review", "retro", "sync",
                 "workshop", "kickoff", "steering", "townhall", "export")


def _fold(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s.lower())
                   if unicodedata.category(c) != "Mn")


def _people(folder: Path) -> list:
    """Folder names under Team/ or Stakeholders/ — the only valid targets."""
    if not folder.exists():
        return []
    return sorted(d.name for d in folder.iterdir()
                  if d.is_dir() and "-" in d.name)


def _title_core(window_title: str) -> str:
    """Strip the Teams chrome: 'Chat | Leite, Ana | Microsoft Teams' -> 'Leite, Ana'."""
    parts = [p.strip() for p in window_title.split("|")]
    parts = [p for p in parts if p and "microsoft teams" not in _fold(p)]
    if parts and _fold(parts[0]) in ("chat", "meeting join", "ingresso na reuniao"):
        parts = parts[1:]
    return parts[0] if parts else ""


def match_person(core: str, folders: list):
    """Match 'Leite, Ana' or 'Ana Leite' to the folder 'Ana-Leite'.

    Requires BOTH name parts to appear, so 'Pedro Klein' never matches
    'Pedro-Hennig' — a wrong match writes into another person's 1:1 file.
    """
    tokens = [t for t in re.split(r"[,\s]+", _fold(core)) if len(t) > 2]
    if not tokens:
        return None
    for folder in folders:
        parts = [_fold(p) for p in folder.split("-") if len(p) > 2]
        if parts and all(any(p == t for t in tokens) for p in parts):
            return folder
    return None


def classify(pending: dict, team: list, stake: list) -> dict:
    """Return {kind, target, why} for one recording."""
    title = pending.get("window_title", "") or ""
    core = _title_core(title)

    person = match_person(core, team)
    if person:
        return {"kind": "person", "target": person,
                "why": f"'{core}' bate com Team/{person}"}

    holder = match_person(core, stake)
    if holder:
        return {"kind": "manager", "target": holder,
                "why": f"'{core}' bate com Stakeholders/{holder}"}

    if any(h in _fold(core) for h in MEETING_HINTS):
        return {"kind": "project", "target": "",
                "why": f"'{core}' parece reuniao de projeto"}

    # Deliberately a loose note: filing under a guessed person is worse than
    # leaving it in the Inbox for Kelvin to place.
    return {"kind": "note", "target": "",
            "why": f"'{core}' nao bate com ninguem do vault - vai para Inbox"}


def build_job(pending_path: Path, pending: dict, verdict: dict) -> dict:
    stem = Path(pending["wav"]).stem
    started = datetime.fromisoformat(pending["started"])
    return {
        "wav": pending["wav"],
        "transcript": str(TRANSCRIPTS / f"{stem}.txt"),
        "kind": verdict["kind"],
        "target": verdict["target"],
        "lang": "auto",
        "date": started.strftime("%Y-%m-%d"),
        "time": started.strftime("%H-%M"),
        "structured": False,
        "coach": False,          # auto-detected English still triggers the coach
        "source": "autocapture",
        "meeting": pending.get("window_title", ""),
    }


def main():
    ap = argparse.ArgumentParser(description="Classifica gravacoes do autocapture")
    ap.add_argument("--apply", action="store_true", help="grava os .job.json")
    ap.add_argument("--only", default="", help="prefixo de data, ex. 2026-08-28")
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    team = _people(VAULT / "Team")
    stake = _people(VAULT / "Stakeholders")
    if not team and not stake:
        print(f"[ERRO] vault nao encontrado em {VAULT}")
        return 1

    pendings = sorted(RECORDINGS.glob("*.pending.json"))
    if args.only:
        pendings = [p for p in pendings if p.name.startswith(args.only)]
    if not pendings:
        print("nada pendente.")
        return 0

    print(f"{'gravacao':28s} {'kind':8s} {'alvo':22s} motivo")
    print("-" * 100)
    n = 0
    for p in pendings:
        try:
            pend = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"{p.name[:28]:28s} ILEGIVEL: {e}")
            continue
        wav = RECORDINGS / pend["wav"]
        if not wav.exists():
            print(f"{pend['wav'][:28]:28s} SEM WAV - pulando")
            continue

        v = classify(pend, team, stake)
        print(f"{pend['wav'][:28]:28s} {v['kind']:8s} {v['target'][:22]:22s} {v['why']}")

        if args.apply:
            job = RECORDINGS / f"{wav.stem}.job.json"
            job.write_text(json.dumps(build_job(p, pend, v), ensure_ascii=False),
                           encoding="utf-8")
            p.rename(p.with_suffix(".json.classified"))
            n += 1

    print("-" * 100)
    if args.apply:
        print(f"{n} job(s) criado(s). A fila das 20:00 transcreve, ou rode a mao:")
        print(r'   python "%USERPROFILE%\techcolab-backlog\call-recorder\process.py" queue')
    else:
        print("SIMULACAO — nada foi escrito. Use --apply para gravar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
