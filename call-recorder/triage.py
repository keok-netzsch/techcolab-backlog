"""Kelvin classifies what the machine could not. Nothing is guessed into a person.

The Teams window title carries the meeting SUBJECT, never the participants:
"Power BI Data Export" was a call with Stefan and Ana about the OKR 05 export
policy, and no amount of string matching could have known that. So recordings
whose destination is not certain are marked `needs_review` and wait here instead
of being filed under a guess.

    python triage.py                     # o que espera decisao
    python triage.py 11-00 project       # reuniao de projeto -> Inbox
    python triage.py 11-00 manager Stefan-Lautenschlager
    python triage.py 11-00 person Ana-Leite --lembrar
    python triage.py 11-00 --nota "OKR 05 - politica de export, decisao do Stefan"

`--lembrar` grava o titulo em meeting-aliases.json, para a proxima ocorrencia da
mesma reuniao recorrente sair classificada sozinha.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
RECORDINGS = HERE / "recordings"
ALIASES = HERE / "meeting-aliases.json"

KINDS = ("person", "manager", "note", "project", "retro", "idea",
         "requirements", "learning")


def _jobs():
    return sorted(RECORDINGS.glob("*.job.json"))


def _load(p):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def listar():
    pend = []
    for p in _jobs():
        j = _load(p)
        if j and j.get("needs_review"):
            pend.append((p, j))
    if not pend:
        print("nada aguardando classificacao.")
        return 0

    print(f"{len(pend)} gravacao(oes) aguardando a sua classificacao:\n")
    for p, j in pend:
        print(f"  {p.stem.replace('.job','')}")
        print(f"     {j.get('date')} {j.get('time','').replace('-',':')}  "
              f"kind atual: {j['kind']}"
              + (f" -> {j['target']}" if j.get("target") else ""))
        print(f"     reuniao: {j.get('meeting','-')}")
        print()
    print("Para decidir:")
    print("   python triage.py <trecho-do-nome> <kind> [alvo] [--lembrar]")
    print(f"   kinds: {', '.join(KINDS)}")
    return 0


def _match(fragment):
    hits = [p for p in _jobs() if fragment in p.name]
    if not hits:
        raise SystemExit(f"nenhum job casa com '{fragment}'")
    if len(hits) > 1:
        raise SystemExit("ambiguo:\n  " + "\n  ".join(h.name for h in hits))
    return hits[0]


def _remember(title, kind, target):
    """Persist the decision so the same recurring meeting routes itself later."""
    try:
        data = json.loads(ALIASES.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    core = title
    for sep in ("|",):
        parts = [x.strip() for x in title.split(sep)
                 if x.strip() and "microsoft teams" not in x.lower()]
        if parts:
            core = parts[-1] if len(parts) == 1 else parts[1] if len(parts) > 1 else parts[0]
    data[core.lower()] = {"kind": kind, "target": target}
    ALIASES.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                       encoding="utf-8")
    return core


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("fragmento", nargs="?")
    ap.add_argument("kind", nargs="?")
    ap.add_argument("alvo", nargs="?", default="")
    ap.add_argument("--lembrar", action="store_true")
    ap.add_argument("--nota", default="")
    ap.add_argument("-h", "--help", action="store_true")
    a = ap.parse_args()

    if a.help:
        print(__doc__)
        return 0
    if not a.fragmento:
        return listar()

    p = _match(a.fragmento)
    j = _load(p)
    if j is None:
        raise SystemExit(f"job ilegivel: {p.name}")

    if a.kind and a.kind not in KINDS:
        raise SystemExit(f"kind invalido '{a.kind}'. Use: {', '.join(KINDS)}")

    if a.kind:
        j["kind"] = a.kind
        j["target"] = a.alvo
        j["needs_review"] = False
    if a.nota:
        j["context"] = a.nota          # carried into the vault note as provenance

    p.write_text(json.dumps(j, ensure_ascii=False), encoding="utf-8")
    print(f"{p.stem.replace('.job','')}: kind={j['kind']}"
          + (f" target={j['target']}" if j.get("target") else "")
          + (" (revisado)" if not j.get("needs_review") else ""))
    if a.nota:
        print(f"   contexto: {a.nota}")

    if a.lembrar and a.kind:
        core = _remember(j.get("meeting", ""), a.kind, a.alvo)
        print(f"   lembrado: '{core}' -> {a.kind} {a.alvo}".rstrip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
