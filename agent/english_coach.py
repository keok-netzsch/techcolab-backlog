"""
agent/english_coach.py — Weekly English Coach report.

Scans the vault for recordings tagged with `lang: en` from the past 7 days,
consolidates the transcripts, and generates a structured coaching report via Ollama.

The report is saved to:
    {VAULT_ROOT}/agent-reports/english-coach-YYYY-WNN.md

Usage:
    python agent/english_coach.py            # analyse last 7 days
    python agent/english_coach.py --days 14  # extend look-back window
    python agent/english_coach.py --dry-run  # list sessions found, no Ollama call

Requires: Ollama running locally (ollama serve) with qwen2.5-coder or llama3.2:3b pulled.
"""

import argparse
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

# ── Project path setup ────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from config import VAULT_ROOT

import requests

REPORTS_DIR = VAULT_ROOT / "agent-reports"

OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5-coder:latest"   # better JSON + structured output

# Directories to scan (relative to VAULT_ROOT)
SCAN_DIRS = [
    "Team",          # Team/*/1on1/*.md
    "Stakeholders",  # Stakeholders/*/1on1/*.md
    "English-Coach", # English-Coach/sessions/*.md
]

MAX_CHARS_PER_SESSION = 1500   # cap per transcript to stay within 3B context
MAX_TOTAL_CHARS       = 8000   # hard cap on consolidated text sent to Ollama


# ── Vault scanning ────────────────────────────────────────────────────────────

def _parse_frontmatter(text: str) -> dict:
    """Return a dict of key:value from a YAML frontmatter block (--- ... ---)."""
    fm = {}
    m = re.match(r"^---\r?\n(.*?)\r?\n---", text, re.DOTALL)
    if not m:
        return fm
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip().strip("'\"")
    return fm


def _extract_body(text: str) -> str:
    """Return the markdown body after the frontmatter block."""
    m = re.match(r"^---\r?\n.*?\r?\n---\r?\n", text, re.DOTALL)
    if m:
        return text[m.end():]
    return text


def _extract_transcript_section(body: str) -> str:
    """
    For English-Coach session files, extract the raw transcript from
    the `## Transcript` section (inside a ``` code block).
    Falls back to the full body if no such block is found.
    """
    m = re.search(r"## Transcript\s*\n+```\n(.*?)```", body, re.DOTALL)
    if m:
        return m.group(1).strip()
    return body.strip()


def find_english_sessions(days: int) -> list[dict]:
    """
    Walk the vault and return sessions with lang: en within the last `days` days.
    Each item: {date, type, person, path, text}
    """
    cutoff = date.today() - timedelta(days=days)
    sessions = []

    for scan_dir in SCAN_DIRS:
        base = VAULT_ROOT / scan_dir
        if not base.exists():
            continue

        # Collect all .md files up to 2 levels deep (Team/Person/1on1/*.md, etc.)
        for md in base.rglob("*.md"):
            try:
                raw = md.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            fm = _parse_frontmatter(raw)

            # Must have lang: en
            if fm.get("lang", "").strip().lower() != "en":
                continue

            # Must have a valid date within the window
            session_date_str = fm.get("date", "")
            try:
                session_date = date.fromisoformat(session_date_str)
            except ValueError:
                continue

            if session_date < cutoff:
                continue

            body = _extract_body(raw)
            session_type = fm.get("type", "unknown")

            if session_type == "english-coach-session":
                text = _extract_transcript_section(body)
            else:
                text = body.strip()

            sessions.append({
                "date":   session_date,
                "type":   session_type,
                "person": fm.get("person", "—"),
                "path":   md,
                "text":   text[:MAX_CHARS_PER_SESSION],
            })

    sessions.sort(key=lambda s: s["date"])
    return sessions


# ── Ollama ────────────────────────────────────────────────────────────────────

def _check_ollama():
    try:
        requests.get("http://localhost:11434/", timeout=3)
    except requests.exceptions.ConnectionError:
        print("[ERROR] Ollama not found at localhost:11434.")
        print("        Start with: ollama serve")
        sys.exit(1)


def _ollama_generate(prompt: str, use_json: bool = False) -> str:
    payload = {
        "model":  OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
    }
    if use_json:
        payload["format"] = "json"

    r = requests.post(OLLAMA_URL, json=payload, timeout=300)
    r.raise_for_status()
    return r.json()["response"].strip()


# ── Report generation ─────────────────────────────────────────────────────────

def _build_prompt(sessions: list[dict], week_label: str) -> str:
    session_blocks = []
    total = 0
    for s in sessions:
        label = f"[{s['date']} | {s['type']} | {s['person']}]"
        excerpt = s["text"]
        if total + len(excerpt) > MAX_TOTAL_CHARS:
            excerpt = excerpt[: MAX_TOTAL_CHARS - total]
        session_blocks.append(f"{label}\n{excerpt}")
        total += len(excerpt)
        if total >= MAX_TOTAL_CHARS:
            break

    combined = "\n\n---\n\n".join(session_blocks)

    return f"""You are a professional English language coach analyzing a non-native speaker's English usage across multiple recorded sessions from {week_label}.

Sessions ({len(sessions)} total):
---
{combined}
---

Produce a JSON report with this exact structure:
{{
  "overall_impression": "<2-3 sentence assessment of the week's English>",
  "level_estimate": "<A1|A2|B1|B2|C1|C2>",
  "recurring_strengths": ["<strength 1>", "<strength 2>"],
  "recurring_issues": [
    {{"category": "<grammar|vocabulary|fluency|structure|register>",
      "pattern": "<description of the recurring pattern>",
      "example": "<quoted phrase from the transcripts>",
      "fix": "<how to correct it>"}}
  ],
  "filler_words": ["<word or phrase>"],
  "vocabulary_upgrades": [
    {{"used": "<phrase>", "better": "<more precise/natural alternative>"}}
  ],
  "top_tips": [
    {{"dimension": "<grammar|vocabulary|fluency|structure|register>",
      "tip": "<concrete actionable tip>",
      "example": "<example sentence>"}}
  ],
  "next_week_focus": "<one specific skill to practise next week>"
}}

Be honest and specific. Reference actual phrases from the transcripts where possible."""


def _render_report(report: dict, sessions: list[dict], week_label: str,
                   iso_week: str) -> str:
    today_str = date.today().isoformat()

    lines = [
        f"---",
        f"date: {today_str}",
        f"week: {iso_week}",
        f"type: english-coach-weekly",
        f"sessions: {len(sessions)}",
        f"level: {report.get('level_estimate', '?')}",
        f"tags: [english-coach, weekly-report]",
        f"---",
        f"",
        f"# Weekly English Coaching Report — {week_label}",
        f"",
        f"> {report.get('overall_impression', '')}",
        f"",
        f"**Estimated level:** {report.get('level_estimate', '?')}",
        f"",
    ]

    # Sessions analyzed
    lines += ["## Sessions Analyzed", ""]
    for s in sessions:
        lines.append(f"- {s['date']} — {s['type']} ({s['person']})")
    lines.append("")

    # Strengths
    strengths = report.get("recurring_strengths", [])
    if strengths:
        lines += ["## Strengths", ""]
        for st in strengths:
            lines.append(f"- {st}")
        lines.append("")

    # Recurring issues
    issues = report.get("recurring_issues", [])
    if issues:
        lines += ["## Recurring Issues", ""]
        for iss in issues:
            lines.append(f"**{iss.get('category', '').title()}** — {iss.get('pattern', '')}")
            if iss.get("example"):
                lines.append(f"> _{iss['example']}_")
            if iss.get("fix"):
                lines.append(f"→ {iss['fix']}")
            lines.append("")

    # Filler words
    fillers = report.get("filler_words", [])
    if fillers:
        lines += ["## Filler Words & Habits", ""]
        lines.append(", ".join(f"`{f}`" for f in fillers))
        lines.append("")

    # Vocabulary
    vocab = report.get("vocabulary_upgrades", [])
    if vocab:
        lines += ["## Vocabulary Upgrades", ""]
        for v in vocab:
            lines.append(f"- _{v.get('used', '')}_ → **{v.get('better', '')}**")
        lines.append("")

    # Tips
    tips = report.get("top_tips", [])
    if tips:
        lines += ["## Top Tips for Next Week", ""]
        for t in tips:
            lines.append(f"**{t.get('dimension', '').title()}:** {t.get('tip', '')}")
            if t.get("example"):
                lines.append(f"> Example: _{t['example']}_")
            lines.append("")

    # Focus
    focus = report.get("next_week_focus", "")
    if focus:
        lines += ["## Next Week Focus", "", f"> {focus}", ""]

    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Weekly English Coach — vault scanner + Ollama report generator"
    )
    parser.add_argument("--days",    type=int, default=7,
                        help="Look-back window in days (default: 7)")
    parser.add_argument("--dry-run", action="store_true",
                        help="List sessions found without calling Ollama")
    args = parser.parse_args()

    today = date.today()
    iso_year, iso_week, _ = today.isocalendar()
    iso_week_str = f"{iso_year}-W{iso_week:02d}"
    week_label   = f"Week {iso_week:02d} / {iso_year}"

    print(f"\n[english-coach] Scanning vault for English sessions (last {args.days} days)...")
    sessions = find_english_sessions(args.days)

    if not sessions:
        print("[english-coach] No English sessions found. Nothing to report.")
        print(f"               Tip: make sure recordings have 'lang: en' in their frontmatter.")
        sys.exit(0)

    print(f"[english-coach] Found {len(sessions)} session(s):")
    for s in sessions:
        print(f"  • {s['date']}  {s['type']:<30}  {s['person']}")

    if args.dry_run:
        print("\n[dry-run] Skipping Ollama call. Exiting.")
        sys.exit(0)

    _check_ollama()

    print(f"\n[english-coach] Generating report with Ollama ({OLLAMA_MODEL})...")
    prompt = _build_prompt(sessions, week_label)

    try:
        raw = _ollama_generate(prompt, use_json=True)
        report = json.loads(raw)
    except (json.JSONDecodeError, KeyError) as e:
        print(f"[ERROR] Ollama returned invalid JSON: {e}")
        print("Raw response:", raw[:500])
        sys.exit(1)

    md = _render_report(report, sessions, week_label, iso_week_str)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS_DIR / f"english-coach-{iso_week_str}.md"
    out_path.write_text(md, encoding="utf-8")

    print(f"\n[english-coach] Report saved: {out_path}")
    print(f"[english-coach] Level estimate: {report.get('level_estimate', '?')}")
    print(f"[english-coach] Done.")


if __name__ == "__main__":
    main()
