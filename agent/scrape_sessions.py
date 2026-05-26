"""
agent/scrape_sessions.py — Extract session summaries from Claude Code JSONL history.

Reads all .jsonl files under ~/.claude/projects/, extracts session metadata
(ai-title, user messages, date, project mapping) and returns structured entries
suitable for appending to reports/claude-pro-timeline.json.

Standalone usage:
    python agent/scrape_sessions.py [--since-days N] [--project FOLDER]

Also called from daily_report._update_claude_pro_report() as a fallback
when no git commits exist for today.
"""

import json
import re
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

PROJECTS_DIR = Path.home() / ".claude" / "projects"
DEFAULT_DAYS_BACK = 14

_EN_MONTHS = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
}

# Project folder name → (initiative number, label)
PROJECT_MAP: dict[str, tuple[Optional[str], str]] = {
    "C--Users-Kelvin-okuda-techcolab-backlog": (
        "09", "Personal Toolkit · Techco.lab"
    ),
    "C--Users-Kelvin-okuda-OneDrive---NETZSCH-Documents-TechColab-D-A-KO": (
        "02", "Obsidian Vault"
    ),
    "C--Users-Kelvin-okuda": (
        None, "Generic session"
    ),
}

# Skip titles / first messages that are meta / too generic
_SKIP_RE = re.compile(
    r"^(execute (the )?approved|resumir|continue|continuação|resume|"
    r"prosseguir|executar pend|running daily|health check"
    r"|\\[A-Za-z]"            # skill-init injections like \SPM-Bot
    r"|new session[\.\s]"     # "New session. Read /mnt/skills/..."
    r")",
    re.IGNORECASE,
)


def _is_skip(text: str) -> bool:
    return bool(_SKIP_RE.search(text.strip()))


def _fmt_display_date(iso_date: str) -> str:
    dt = date.fromisoformat(iso_date)
    return f"{dt.day} {_EN_MONTHS[dt.month]} {dt.year}"


def parse_session(jsonl_path: Path) -> Optional[dict]:
    """
    Read a single .jsonl and return:
      date (ISO str), ai_title, user_messages[:6],
      initiative_num, initiative_label, session_id
    Returns None if the session is too thin.
    """
    ai_title = ""
    user_msgs: list[str] = []
    ts_first = ""

    try:
        with open(jsonl_path, encoding="utf-8", errors="replace") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    obj = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                # First timestamp → session date
                if not ts_first and obj.get("timestamp"):
                    ts_first = obj["timestamp"][:10]

                # AI-generated session title (most reliable signal)
                if obj.get("type") == "ai-title":
                    ai_title = obj.get("aiTitle", "")

                # User messages — two formats observed in the wild
                role = obj.get("message", {}).get("role")
                if role == "user":
                    content = obj["message"].get("content", "")
                    if isinstance(content, list):
                        for c in content:
                            if isinstance(c, dict) and c.get("type") == "text":
                                text = c["text"].strip()
                                if len(text) > 8 and not _is_skip(text):
                                    user_msgs.append(text[:300])
                    elif isinstance(content, str):
                        text = content.strip()
                        if len(text) > 8 and not _is_skip(text):
                            user_msgs.append(text[:300])

    except Exception:
        return None

    if not ts_first or (not ai_title and not user_msgs):
        return None

    proj = jsonl_path.parent.name
    init_num, init_lbl = PROJECT_MAP.get(proj, (None, proj))

    return {
        "date": ts_first,
        "session_id": jsonl_path.stem,
        "ai_title": ai_title,
        "user_messages": user_msgs[:6],
        "initiative_num": init_num,
        "initiative_label": init_lbl,
        "project_folder": proj,
    }


def get_recent_sessions(
    days_back: int = DEFAULT_DAYS_BACK,
    project_filter: Optional[str] = None,
) -> list[dict]:
    """Return parsed session dicts for the last N days, newest first."""
    if not PROJECTS_DIR.exists():
        print(f"[scrape] Projects dir not found: {PROJECTS_DIR}")
        return []

    cutoff = (date.today() - timedelta(days=days_back)).isoformat()
    results: list[dict] = []

    for jsonl_path in sorted(PROJECTS_DIR.rglob("*.jsonl")):
        if project_filter and jsonl_path.parent.name != project_filter:
            continue
        meta = parse_session(jsonl_path)
        if meta and meta["date"] >= cutoff:
            results.append(meta)

    results.sort(key=lambda x: x["date"], reverse=True)
    return results


def _ollama_summarize(
    user_messages: list[str],
    ollama_url: str,
    model: str = "llama3",
) -> Optional[tuple[str, str]]:
    """
    Ask Ollama to generate (title, detail) for a session.
    Returns None on any failure.
    """
    try:
        import urllib.request

        bullets = "\n".join(f"- {m[:200]}" for m in user_messages[:5])
        prompt = (
            "Summarize this Claude Code work session in one concise English title "
            "(max 10 words) and one short detail line (max 20 words). "
            'Return ONLY valid JSON: {"title": "...", "detail": "..."}.\n\n'
            f"Session messages:\n{bullets}"
        )
        payload = json.dumps(
            {"model": model, "prompt": prompt, "stream": False}
        ).encode()
        req = urllib.request.Request(
            f"{ollama_url.rstrip('/')}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw_resp = json.loads(resp.read()).get("response", "{}")
            parsed = json.loads(raw_resp)
            if parsed.get("title"):
                return parsed["title"].strip(), parsed.get("detail", "").strip()
    except Exception:
        pass
    return None


def _build_title_detail(
    meta: dict,
    ollama_url: Optional[str] = None,
    ollama_model: str = "llama3",
) -> tuple[str, str]:
    """
    Returns (title, detail) for a session.
    Priority: Ollama → ai_title → first user message.
    """
    ai_title = meta.get("ai_title", "")
    msgs = meta.get("user_messages", [])

    # Optional Ollama enrichment
    if ollama_url and msgs:
        result = _ollama_summarize(msgs, ollama_url, ollama_model)
        if result:
            return result

    # ai_title is concise and reliable when present
    if ai_title and not _is_skip(ai_title):
        title = ai_title[0].upper() + ai_title[1:]
        detail = msgs[0][:120] if msgs else ""
        return title, detail

    # Fallback: first non-trivial user message
    if msgs:
        raw = msgs[0][:80].strip()
        title = (raw[0].upper() + raw[1:]) if raw else "Claude Code session"
        detail = "; ".join(m[:80] for m in msgs[1:3])
        return title, detail

    return "Claude Code session", ""


def sessions_to_timeline_entries(
    sessions: list[dict],
    existing_dates: set[str],
    ollama_url: Optional[str] = None,
    ollama_model: str = "llama3",
) -> list[dict]:
    """
    Convert session list to claude-pro-timeline.json entries.
    Groups multiple sessions on the same date into one entry.
    Skips dates already present in existing_dates.
    """
    by_date: dict[str, list[dict]] = defaultdict(list)
    for s in sessions:
        by_date[s["date"]].append(s)

    entries: list[dict] = []
    for day, day_sessions in sorted(by_date.items(), reverse=True):
        if day in existing_dates:
            continue

        if len(day_sessions) == 1:
            title, detail = _build_title_detail(
                day_sessions[0], ollama_url, ollama_model
            )
        else:
            # Multiple sessions: collect all titles, use most descriptive as main
            pairs = [
                _build_title_detail(s, ollama_url, ollama_model)
                for s in day_sessions
            ]
            titles = list(dict.fromkeys(
                t for t, _ in pairs if t and t != "Claude Code session"
            ))
            title = max(titles, key=len) if titles else "Multiple sessions"
            rest = [t for t in titles if t != title]
            detail = "; ".join(rest)[:200]

        entries.append({
            "date": day,
            "display_date": _fmt_display_date(day),
            "title": title,
            "detail": detail,
        })

    return entries


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Scrape Claude Code session history and preview timeline candidates."
    )
    parser.add_argument("--since-days", type=int, default=DEFAULT_DAYS_BACK,
                        help=f"Days to look back (default: {DEFAULT_DAYS_BACK})")
    parser.add_argument("--project", type=str, default=None,
                        help="Filter to a single project folder name")
    parser.add_argument("--ollama-url", type=str, default=None,
                        help="Ollama base URL, e.g. http://localhost:11434")
    args = parser.parse_args()

    sessions = get_recent_sessions(args.since_days, args.project)
    print(f"\nFound {len(sessions)} session(s) in the last {args.since_days} day(s):\n")

    existing: set[str] = set()
    try:
        tl_path = ROOT / "reports" / "claude-pro-timeline.json"
        if tl_path.exists():
            existing = {e["date"] for e in json.loads(tl_path.read_text(encoding="utf-8"))}
    except Exception:
        pass

    candidates = sessions_to_timeline_entries(
        sessions, existing, args.ollama_url
    )

    print(f"New timeline candidates ({len(candidates)} date(s) not yet in JSON):\n")
    for e in candidates:
        print(f"  [{e['date']}] {e['title']}")
        if e["detail"]:
            print(f"           {e['detail'][:100]}")
        print()

    if not candidates:
        print("  (none — all dates already covered in timeline JSON)")


if __name__ == "__main__":
    main()
