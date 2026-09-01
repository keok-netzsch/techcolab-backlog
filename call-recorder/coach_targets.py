"""Prescription ledger for the English Coach — say HOW, then check it happened.

Why this exists
---------------
The coach already says where Kelvin is weak (vocabulary 6.5, register 6.7) and
even offers alternatives per session. What it never did was carry a suggestion
forward. Every session proposed new wording into a file nobody re-read, so
"vocabulary" stayed at 6.5 for four months while the reports kept saying
"broaden your vocabulary" (Kelvin, 2026-09-01: "ele mostra onde melhorar, mas
não como... sugerir certas palavras, e depois verificar se eu usei tais
palavras").

So a suggestion becomes a **target**: a small, named thing to do in the next
call, whose use is then measured.

The measurement is deterministic on purpose — the same reason coach_patterns.py
exists. "Did he say 'leverage'?" is a regex over his own lines, not a judgement
call, so progress cannot be hallucinated by a 7B model. Only the *generation* of
new targets uses the model, and only by reusing what it already proposed for that
session; this module never asks it anything.

Two kinds, both checkable:
  use   — a word or phrase to start using   -> achieved after ACHIEVE_HITS sessions with a hit
  avoid — a habit to stop                   -> achieved after ACHIEVE_CLEAN clean sessions

State: {COACH_DIR}/targets.json. Never edited by hand — see the vault rule about
the vault being a record, not an interaction surface.
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

# A list you can hold in your head walking into a call. More than this and it
# stops being a plan and becomes a backlog nobody reads — the failure this
# module exists to fix.
MAX_ACTIVE = 6
ACHIEVE_HITS = 2      # distinct sessions using it before a "use" target retires
ACHIEVE_CLEAN = 2     # consecutive clean sessions before an "avoid" target retires
STUCK_AFTER = 6       # sessions with no progress -> flagged, never silently dropped


def _targets_path(coach_dir: Path) -> Path:
    return Path(coach_dir) / "targets.json"


def load(coach_dir: Path) -> dict:
    p = _targets_path(coach_dir)
    if not p.exists():
        return {"targets": []}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        # A corrupt ledger must not take the coach down; it starts over loudly.
        print("[targets] targets.json unreadable - starting a new ledger")
        return {"targets": []}
    data.setdefault("targets", [])
    return data


def save(coach_dir: Path, data: dict) -> Path:
    p = _targets_path(coach_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def _occurrences(text: str, phrase: str) -> int:
    """Word-boundary, case-insensitive count of a word or multi-word phrase."""
    if not phrase.strip():
        return 0
    pattern = r"\b" + r"\s+".join(re.escape(w) for w in phrase.split()) + r"\b"
    return len(re.findall(pattern, text, flags=re.I))


def check(transcript: str, data: dict) -> list[dict]:
    """Measure every active target against this session's transcript.

    `transcript` must already be Kelvin's own lines — coach.py isolates them
    before this point, and grading the other party's vocabulary would be absurd.
    """
    results = []
    for t in data["targets"]:
        if t.get("status") != "active":
            continue
        n = _occurrences(transcript, t["target"])
        results.append({"id": t["id"], "target": t["target"], "kind": t["kind"],
                        "count": n,
                        "good": (n > 0) if t["kind"] == "use" else (n == 0)})
    return results


def apply_results(data: dict, results: list[dict], session_id: str, today: str) -> dict:
    """Fold this session's measurement into the ledger. Returns a small summary."""
    by_id = {t["id"]: t for t in data["targets"]}
    achieved, still_open = [], []
    for r in results:
        t = by_id.get(r["id"])
        if not t:
            continue
        t.setdefault("sessions", [])
        t["sessions"].append({"session": session_id, "date": today, "count": r["count"]})
        if r["good"]:
            t["streak"] = t.get("streak", 0) + 1
        else:
            # An "avoid" streak is about consecutive clean sessions, so a slip
            # resets it. A "use" streak counts sessions that used it at all, and
            # a quiet session should not erase two months of progress.
            if t["kind"] == "avoid":
                t["streak"] = 0
        need = ACHIEVE_HITS if t["kind"] == "use" else ACHIEVE_CLEAN
        if t.get("streak", 0) >= need:
            t["status"] = "achieved"
            t["achieved_on"] = today
            achieved.append(t)
        else:
            t["stuck"] = len(t["sessions"]) >= STUCK_AFTER and t.get("streak", 0) == 0
            still_open.append(t)
    return {"achieved": achieved, "still_open": still_open}


def _next_id(data: dict) -> str:
    nums = [int(t["id"].split("-")[1]) for t in data["targets"]
            if t.get("id", "").startswith("t-") and t["id"].split("-")[1].isdigit()]
    return f"t-{(max(nums) + 1) if nums else 1:03d}"


def propose(data: dict, ev: dict, session_id: str, today: str) -> list[dict]:
    """Turn this session's own suggestions into targets, up to MAX_ACTIVE.

    Nothing new is invented here: it promotes what the model already produced for
    this session (vocabulary alternatives it offered, error patterns it found) so
    the suggestion survives past the file nobody reopened.
    """
    active = [t for t in data["targets"] if t.get("status") == "active"]
    seen = {t["target"].casefold() for t in data["targets"]}
    room = MAX_ACTIVE - len(active)
    if room <= 0:
        return []

    # ONE alternative per habit. The model offers three ways to replace "sell it
    # out"; taking all three burns half the list on a single habit, which is what
    # the first real run did (3 of 6 slots, and every "avoid" pushed out).
    use_cands: list[dict] = []
    for v in ev.get("vocabulary_suggestions") or []:
        alts = [a.strip() for a in (v.get("alternatives") or []) if a.strip()]
        if not alts:
            continue
        use_cands.append({"kind": "use", "target": alts[0],
                          "instead_of": (v.get("used") or "").strip(),
                          "why": f"offered as a sharper alternative to \"{v.get('used', '')}\""})

    avoid_cands: list[dict] = []
    for e in ev.get("errors") or []:
        original = (e.get("original") or "").strip()
        # A long quote is a sentence, not a habit — it would never recur verbatim,
        # so it can never be measured as fixed.
        if original and len(original.split()) <= 5:
            avoid_cands.append({"kind": "avoid", "target": original,
                                "instead_of": (e.get("corrected") or "").strip(),
                                "why": (e.get("explanation") or e.get("type") or "").strip()})

    # Interleaved so one batch is never entirely of one kind.
    candidates: list[dict] = []
    for i in range(max(len(use_cands), len(avoid_cands))):
        if i < len(use_cands):
            candidates.append(use_cands[i])
        if i < len(avoid_cands):
            candidates.append(avoid_cands[i])

    # A habit is the PAIR (bad phrase, good phrase). The model reports the same
    # pair twice — once as a vocabulary upgrade, once as an error — and taking
    # both spends two slots on one instruction ("use off-the-shelf solutions" +
    # "stop saying shelf solutions"). Covering either side covers the habit.
    for t in data["targets"]:
        seen.add((t.get("instead_of") or "").casefold())
    seen.discard("")

    new = []
    for c in candidates:
        if room <= 0:
            break
        key = c["target"].casefold()
        other = (c["instead_of"] or "").casefold()
        if not c["target"] or key in seen or (other and other in seen):
            continue
        seen.add(key)
        if other:
            seen.add(other)
        room -= 1
        new.append({"id": _next_id({"targets": data["targets"] + new}),
                    "kind": c["kind"], "target": c["target"],
                    "instead_of": c["instead_of"], "why": c["why"],
                    "assigned_on": today, "assigned_from": session_id,
                    "status": "active", "streak": 0, "sessions": []})
    data["targets"].extend(new)
    return new


def render(results: list[dict], summary: dict, new: list[dict]) -> list[str]:
    """Markdown block for the session note. Empty list when there is nothing yet."""
    if not (results or new):
        return []
    lines = ["## Targets", ""]
    if results:
        hit = [r for r in results if r["good"]]
        lines.append(f"**Carried in from earlier sessions — {len(hit)} of {len(results)} met.**")
        lines.append("")
        for r in results:
            mark = "✅" if r["good"] else "⬜"
            if r["kind"] == "use":
                detail = f"used {r['count']}×" if r["count"] else "not used"
            else:
                detail = "clean" if r["count"] == 0 else f"still said it {r['count']}×"
            lines.append(f"- {mark} _{r['target']}_ — {detail}")
        lines.append("")
    if summary.get("achieved"):
        lines.append("**Retired this session:** "
                     + ", ".join(f"_{t['target']}_" for t in summary["achieved"]))
        lines.append("")
    stuck = [t for t in summary.get("still_open", []) if t.get("stuck")]
    if stuck:
        lines.append("**Not moving** (assigned a while ago, still at zero): "
                     + ", ".join(f"_{t['target']}_" for t in stuck))
        lines.append("")
    if new:
        lines.append("**For the next call:**")
        lines.append("")
        for t in new:
            if t["kind"] == "use":
                lines.append(f"- Use _{t['target']}_"
                             + (f" instead of _{t['instead_of']}_" if t["instead_of"] else ""))
            else:
                lines.append(f"- Stop saying _{t['target']}_"
                             + (f" — say _{t['instead_of']}_" if t["instead_of"] else ""))
        lines.append("")
    return lines


def run(coach_dir: Path, transcript: str, ev: dict, session_id: str,
        today: str | None = None) -> list[str]:
    """Single entry point used by coach.py: check, fold in, propose, save."""
    today = today or date.today().isoformat()
    data = load(coach_dir)
    results = check(transcript, data)
    summary = apply_results(data, results, session_id, today)
    new = propose(data, ev, session_id, today)
    save(coach_dir, data)
    met = sum(1 for r in results if r["good"])
    print(f"[targets] {met}/{len(results)} met · {len(summary['achieved'])} retired · "
          f"{len(new)} new")
    return render(results, summary, new)
