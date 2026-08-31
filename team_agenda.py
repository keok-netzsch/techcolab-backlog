"""team_agenda.py — Shared 1:1 agenda generation.

Heavy LLM work runs in the scheduled daily agent (agent/daily_report.py), which
pre-generates Team/{folder}/next-agenda.md for each direct report. The Team tab
just reads the pre-generated file (instant), with an on-demand "Regenerate" button.
"""

import json
import re
import urllib.request
from datetime import date
from pathlib import Path

from config import EXTRACTION_MODEL, OLLAMA_BASE_URL, TEAM_DIR

AGENDA_FILE = "next-agenda.md"


def _parse_last_1on1(path: Path):
    """Latest session (topics + action items) from a person's 1on1.md, or None."""
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    parts = re.split(r"^## (\d{4}-\d{2}-\d{2})\b", text, flags=re.MULTILINE)
    if len(parts) < 3:
        return None
    s_date, content = parts[1], parts[2]
    topics, actions, in_t, in_a = [], [], False, False
    for line in content.splitlines():
        s = line.strip()
        if re.match(r"\*\*(T[oó]picos?|Topics?):?\*\*", s):
            in_t, in_a = True, False; continue
        if re.match(r"\*\*(Action [Ii]tems?|Ac[oõ]es?):?\*\*", s):
            in_t, in_a = False, True; continue
        if s.startswith("**") or s.startswith("---"):
            in_t = in_a = False
        if in_t and s.startswith("- "):
            topics.append(s[2:])
        if in_a and re.match(r"- \[[ x]\]", s):
            actions.append({"text": s[6:].strip(), "done": s[3] == "x"})
    return {"date": s_date, "topics": topics, "actions": actions}


def list_team_folders():
    """Team member folders read live from the vault (excludes stray '1on1' and '_*').
    Returns a list of (folder, display_name)."""
    base = Path(TEAM_DIR)
    if not base.exists():
        return []
    return [
        (p.name, p.name.replace("-", " "))
        for p in sorted(base.iterdir())
        if p.is_dir() and p.name != "1on1" and not p.name.startswith("_")
    ]


def generate_agenda_text(folder: str, name: str, timeout: int = 60) -> str:
    """Build the prompt from the person's OKR/PDI/last 1:1 and call Ollama.
    Returns the agenda markdown. Raises on connection/LLM failure."""
    fp  = Path(TEAM_DIR) / folder
    okr = (fp / "OKR.md").read_text(encoding="utf-8", errors="replace")[:700] if (fp / "OKR.md").exists() else ""
    pdi = (fp / "PDI.md").read_text(encoding="utf-8", errors="replace")[:600] if (fp / "PDI.md").exists() else ""
    sess = _parse_last_1on1(fp / "1on1.md")
    ctx = ""
    if sess:
        ctx = f"Last 1:1 ({sess['date']}) topics:\n" + "\n".join(f"- {t}" for t in sess["topics"][:5])
        oa = [a["text"] for a in sess["actions"] if not a["done"]]
        if oa:
            ctx += "\n\nOpen actions:\n" + "\n".join(f"- {a}" for a in oa[:5])

    prompt = (
        "You are a management coach. "
        f"Prepare a concise 1:1 agenda for {name}.\n\n"
        f"=== OKR ===\n{okr}\n\n"
        f"=== PDI ===\n{pdi}\n\n"
        f"=== Last 1:1 context ===\n{ctx}\n\n"
        "Suggest 4-6 agenda topics, each with one focus line. "
        "Numbered list only. No preamble."
    )
    payload = json.dumps({
        "model": EXTRACTION_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "temperature": 0.4,
    }).encode()
    req = urllib.request.Request(
        OLLAMA_BASE_URL + "/chat/completions",
        data=payload, headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        result = json.loads(resp.read())
    return result["choices"][0]["message"]["content"].strip()


def write_agenda(folder: str, name: str, timeout: int = 60) -> Path:
    """Generate and persist Team/{folder}/next-agenda.md. Returns the file path."""
    text = generate_agenda_text(folder, name, timeout=timeout)
    out  = Path(TEAM_DIR) / folder / AGENDA_FILE
    out.parent.mkdir(parents=True, exist_ok=True)
    fm = (
        "---\n"
        "type: 1on1-agenda\n"
        f"generated: {date.today().isoformat()}\n"
        f"person: {name}\n"
        "---\n\n"
    )
    out.write_text(fm + text + "\n", encoding="utf-8")
    return out


def read_agenda(folder: str):
    """Return (generated_date, body) from next-agenda.md, or None if absent."""
    f = Path(TEAM_DIR) / folder / AGENDA_FILE
    if not f.exists():
        return None
    raw = f.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"^generated:\s*(.+)$", raw, re.MULTILINE)
    gen = m.group(1).strip() if m else ""
    body = re.sub(r"^---\n.*?\n---\n+", "", raw, count=1, flags=re.DOTALL).strip()
    return (gen, body)


def generate_all(timeout: int = 60) -> dict:
    """Generate agendas for every team member. Graceful: per-member failures are
    collected, not raised, so a downed Ollama doesn't break the agent run.
    Returns {'ok': [folders], 'failed': [(folder, error)]}."""
    ok, failed = [], []
    for folder, name in list_team_folders():
        try:
            write_agenda(folder, name, timeout=timeout)
            ok.append(folder)
        except Exception as e:
            failed.append((folder, str(e)))
    return {"ok": ok, "failed": failed}
