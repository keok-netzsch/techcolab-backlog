"""
agent/scrape_sessions.py — Claude Code session scraper for Claude Pro Report.

Reads JSONL session files from ~/.claude/projects/, extracts session summaries,
optionally uses Ollama to enrich them, and updates the Claude Pro Report HTML
with recent session activity (initiative cards + timeline entries).

Usage:
    python agent/scrape_sessions.py [--days N]

Returns a list of session summary dicts — also called by daily_report.py.
"""

import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from config import CLAUDE_PRO_REPORT_HTML, OLLAMA_BASE_URL, EXTRACTION_MODEL

PROJECTS_DIR = Path.home() / ".claude" / "projects"
DEFAULT_DAYS_BACK = 7

_PT_MONTHS = {
    1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr", 5: "Mai", 6: "Jun",
    7: "Jul", 8: "Ago", 9: "Set", 10: "Out", 11: "Nov", 12: "Dez",
}

# Maps project directory name -> initiative metadata
PROJECT_INITIATIVE_MAP = {
    "C--Users-Kelvin-okuda-techcolab-backlog": {
        "number": "09",
        "title": "Personal Toolkit · Techco.lab",
        "area": "Produto · Automação",
    },
    "C--Users-Kelvin-okuda-OneDrive---NETZSCH-Documents-TechColab-D-A-KO": {
        "number": "02",
        "title": "Vault Obsidian — Segundo Cérebro",
        "area": "Gestão · IA",
    },
}

# User messages matching these patterns are skipped (meta/system prompts)
_SKIP_PATTERNS = [
    r"^execute the approved",
    r"^running daily report",
    r"^health check",
]


def _date_str(d: date) -> str:
    return f"{d.day} {_PT_MONTHS[d.month]} {d.year}"


def _is_meta_message(text: str) -> bool:
    low = text.lower().strip()
    return any(re.match(p, low) for p in _SKIP_PATTERNS)


def parse_session(jsonl_path: Path) -> dict | None:
    """Parse a single JSONL session file and return basic session data."""
    first_user_msg = None
    cwd = None
    session_date = None

    try:
        with open(jsonl_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if not cwd and obj.get("cwd"):
                    cwd = obj["cwd"]

                if not session_date and obj.get("timestamp"):
                    try:
                        session_date = date.fromisoformat(obj["timestamp"][:10])
                    except (ValueError, TypeError):
                        pass

                if (
                    not first_user_msg
                    and obj.get("type") == "user"
                    and isinstance(obj.get("message", {}).get("content"), str)
                ):
                    content = obj["message"]["content"].strip()
                    if len(content) > 15 and not _is_meta_message(content):
                        first_user_msg = content[:500]

    except Exception:
        return None

    if not session_date:
        try:
            session_date = date.fromtimestamp(jsonl_path.stat().st_mtime)
        except Exception:
            return None

    if not first_user_msg:
        return None

    return {
        "session_id": jsonl_path.stem,
        "date": session_date,
        "project_dir": jsonl_path.parent.name,
        "cwd": cwd or "",
        "first_user_msg": first_user_msg,
        "path": str(jsonl_path),
    }


def get_recent_sessions(days_back: int = DEFAULT_DAYS_BACK) -> list[dict]:
    """Return sessions from the last N days, sorted by date descending."""
    if not PROJECTS_DIR.exists():
        print(f"[scrape] Projects dir not found: {PROJECTS_DIR}")
        return []

    cutoff = date.today() - timedelta(days=days_back)
    sessions = []

    for project_dir in PROJECTS_DIR.iterdir():
        if not project_dir.is_dir():
            continue
        for jsonl_file in project_dir.glob("*.jsonl"):
            session = parse_session(jsonl_file)
            if session and session["date"] >= cutoff:
                sessions.append(session)

    sessions.sort(key=lambda s: s["date"], reverse=True)
    return sessions


def _ollama_summarize(first_user_msg: str, initiative_title: str) -> dict | None:
    """Use Ollama to generate a short Portuguese summary. Returns None on failure."""
    try:
        import urllib.request, json as _json
        base_url = OLLAMA_BASE_URL.replace("/v1", "")
        prompt = (
            f"Resume em português o que foi feito nesta sessão Claude Code "
            f"para o projeto '{initiative_title}'.\n\n"
            f"Primeira mensagem do usuário: {first_user_msg[:300]}\n\n"
            f"Responda exatamente neste formato (duas linhas):\n"
            f"titulo: [uma linha, máx 80 chars, o que foi construído/corrigido]\n"
            f"avanco: [uma frase curta com o principal avanço alcançado]\n"
        )
        payload = _json.dumps({
            "model": EXTRACTION_MODEL,
            "prompt": prompt,
            "stream": False,
        }).encode()
        req = urllib.request.Request(
            f"{base_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            result = _json.loads(resp.read())
            text = result.get("response", "")
            parsed = {}
            for line in text.splitlines():
                if line.lower().startswith("titulo:"):
                    parsed["title"] = line.split(":", 1)[1].strip()
                elif line.lower().startswith("avanco:"):
                    parsed["advance"] = line.split(":", 1)[1].strip()
            return parsed if parsed else None
    except Exception:
        return None


def _clean_for_html(text: str) -> str:
    """Escape special HTML chars in a text string."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_session_summaries(sessions: list[dict]) -> list[dict]:
    """Enrich sessions with initiative mapping and optional Ollama summaries."""
    enriched = []
    for s in sessions:
        initiative = PROJECT_INITIATIVE_MAP.get(s["project_dir"])
        if not initiative:
            continue

        summary = _ollama_summarize(s["first_user_msg"], initiative["title"])
        raw_title = (summary or {}).get("title") or s["first_user_msg"].split("\n")[0][:80]

        enriched.append({
            **s,
            "initiative_number": initiative["number"],
            "initiative_title": initiative["title"],
            "title": _clean_for_html(raw_title),
            "advance": _clean_for_html((summary or {}).get("advance") or ""),
        })

    return enriched


# ── HTML update helpers ──────────────────────────────────────────────────────

def _update_initiative_advance(html: str, initiative_number: str, advance_text: str) -> str:
    """Replace the 'Principal avanço' line for a specific initiative card."""
    if not advance_text:
        return html
    pattern = (
        r'(<span class="initiative-number">'
        + re.escape(initiative_number)
        + r'</span>.*?<strong>Principal avan[çc]o:</strong> )([^<]*)(</div>)'
    )
    new_html = re.sub(
        pattern,
        r'\g<1>' + advance_text.replace("\\", "\\\\") + r'\g<3>',
        html,
        count=1,
        flags=re.DOTALL,
    )
    return new_html


def _inject_session_timeline_entries(html: str, session_summaries: list[dict]) -> str:
    """Insert new timeline entries for session days not already present."""
    by_date: dict[date, list] = {}
    for s in session_summaries:
        by_date.setdefault(s["date"], []).append(s)

    for day in sorted(by_date.keys(), reverse=True):
        day_str = _date_str(day)
        if day_str in html:
            continue  # already represented

        sessions_on_day = by_date[day]
        titles = [s["title"] for s in sessions_on_day if s.get("title")]
        if not titles:
            continue

        main_title = max(titles, key=len)
        other = [t for t in titles if t != main_title]
        detail = "; ".join(other) if other else ""
        detail_html = (
            f'\n        <div class="timeline-detail">{detail}</div>'
            if detail else ""
        )
        entry = (
            f'      <div class="timeline-item">\n'
            f'        <div class="timeline-date">{day_str}</div>\n'
            f'        <div class="timeline-title">{main_title}</div>'
            f'{detail_html}\n'
            f'      </div>\n'
        )
        html = html.replace(
            '<div class="timeline">\n',
            '<div class="timeline">\n' + entry,
            1,
        )

    return html


def _update_stat_counters(html: str, active_count: int, days_since: int) -> str:
    """Update the stat-strip counters in the HTML."""
    from config import CLAUDE_PRO_START_DATE
    from datetime import date as _date
    today = _date.today()
    days_since = (today - _date.fromisoformat(CLAUDE_PRO_START_DATE)).days

    html = re.sub(
        r'(<div class="stat-number">)\d+(</div>\s*<div class="stat-label">Iniciativas ativas)',
        rf'\g<1>{active_count}\g<2>',
        html,
    )
    html = re.sub(
        r'(<div class="stat-number">)\d+(</div>\s*<div class="stat-label">Dias desde ado[çc][ãa]o)',
        rf'\g<1>{days_since}\g<2>',
        html,
    )
    return html


def update_html(session_summaries: list[dict], active_initiative_count: int | None = None) -> bool:
    """Apply all session-based updates to the Claude Pro Report HTML."""
    html_path = CLAUDE_PRO_REPORT_HTML
    if not html_path.exists():
        print(f"[scrape] HTML not found: {html_path}")
        return False

    try:
        html = html_path.read_text(encoding="utf-8")

        # Group by initiative — use most recent session per initiative
        by_initiative: dict[str, list] = {}
        for s in session_summaries:
            by_initiative.setdefault(s["initiative_number"], []).append(s)

        for number, sessions in by_initiative.items():
            most_recent = sessions[0]
            if most_recent.get("advance"):
                html = _update_initiative_advance(html, number, most_recent["advance"])

        html = _inject_session_timeline_entries(html, session_summaries)

        if active_initiative_count is not None:
            html = _update_stat_counters(html, active_initiative_count, 0)

        html_path.write_text(html, encoding="utf-8")
        print(f"[scrape] HTML updated with {len(session_summaries)} session(s) across {len(by_initiative)} initiative(s)")
        return True

    except Exception as exc:
        print(f"[scrape] HTML update failed: {exc}")
        return False


# ── Main ────────────────────────────────────────────────────────────────────

def main(days_back: int = DEFAULT_DAYS_BACK) -> list[dict]:
    """Scan sessions, build summaries, update HTML. Returns summary list."""
    print(f"[scrape] Scanning sessions from last {days_back} days...")
    sessions = get_recent_sessions(days_back)
    print(f"[scrape] Found {len(sessions)} raw sessions")

    summaries = build_session_summaries(sessions)
    print(f"[scrape] {len(summaries)} sessions mapped to known initiatives")

    if summaries:
        update_html(summaries)
    else:
        print("[scrape] No mappable sessions found — HTML unchanged")

    return summaries


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Scrape Claude Code sessions and update Claude Pro Report")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS_BACK,
                        help=f"Days to look back (default: {DEFAULT_DAYS_BACK})")
    args = parser.parse_args()
    results = main(args.days)
    print(f"[scrape] Done. {len(results)} session(s) processed.")
