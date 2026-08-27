"""
agent/daily_report.py — Phase 1: daily analysis, health check, and report generation.

Runs automatically (via Task Scheduler). Reads the backlog, executes tests,
detects opportunities, and writes a structured report to the vault.
The user reviews the report in Obsidian, checks the actions they approve,
and then opens a Claude Code session to execute Phase 2.

Usage:
    python agent/daily_report.py
"""

import json
import os
import re
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# ── Ensure project root is in sys.path ────────────────────────────────────────
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from agent.agent_io import force_utf8_stdio, safe_print
from backlog.schema import VALID_STATUSES
from backlog.store import BacklogStore
from config import ANALYSIS_MODEL, BACKLOG_DIR, VAULT_ROOT

# stdout is redirected to logs/agent-last.log by run_agent.bat, so Python picks
# the ANSI code page (cp1252) instead of UTF-8. See agent/agent_io.py.
force_utf8_stdio()

TODAY = date.today()
REPORTS_DIR = VAULT_ROOT / "agent-reports"

# ── Labels (EN) ───────────────────────────────────────────────────────────────
STATUS_LABEL = {
    "backlog": "Backlog",
    "em análise": "Under review",
    "análise - aprovado": "Approved",
    "análise - rejeitado": "Rejected",
    "aguardando desenvolvimento": "Waiting",
    "em desenvolvimento": "In development",
    "em validação": "In validation",
    "concluído": "Done",
    "descartado": "Discarded",
}
PRIORITY_ICON = {"alta": "⭐⭐⭐", "média": "⭐⭐", "baixa": "⭐"}
EFFORT_SCORE = {"baixo": 1, "médio": 2, "alto": 3}
IMPACT_SCORE = {"alta": 3, "média": 2, "baixa": 1}
PRIORITY_SCORE = {"alta": 3, "média": 2, "baixa": 1}

CLOSED = {"concluído", "descartado", "análise - rejeitado"}
STALE_DAYS = 14  # flag items unchanged for this many days (Toolkit 2.0, idea-066)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _run_tests() -> dict:
    """Run pytest and return a summary dict."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(ROOT / "tests"), "-q", "--tb=no"],
        capture_output=True, text=True, cwd=str(ROOT),
        encoding="utf-8", errors="replace",
    )
    lines = result.stdout.strip().splitlines()
    summary = lines[-1] if lines else "no output"
    passed = failed = errors = 0
    for line in lines:
        if " passed" in line:
            try:
                passed = int(line.split(" passed")[0].split()[-1])
            except (ValueError, IndexError):
                pass
        if " failed" in line:
            try:
                failed = int(line.split(" failed")[0].split()[-1])
            except (ValueError, IndexError):
                pass
        if " error" in line:
            try:
                errors = int(line.split(" error")[0].split()[-1])
            except (ValueError, IndexError):
                pass
    return {
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "summary": summary,
        "ok": result.returncode == 0,
    }


def _score(idea) -> int:
    """Impact × (4 - effort) × priority — higher = better candidate for work."""
    return (
        IMPACT_SCORE.get(idea.impacto or "", 1)
        * (4 - EFFORT_SCORE.get(idea.esforco or "", 2))
        * PRIORITY_SCORE.get(idea.priority, 1)
    )


def _days_since_update(idea) -> int:
    return (TODAY - idea.updated_at).days if idea.updated_at else 999


# ── Analysis ──────────────────────────────────────────────────────────────────

def analyze(ideas: list) -> dict:
    active = [i for i in ideas if i.status not in CLOSED]
    closed = [i for i in ideas if i.status in CLOSED]

    by_status: dict[str, list] = {}
    for i in active:
        by_status.setdefault(i.status, []).append(i)

    overdue = [i for i in active if i.due_date and i.due_date < TODAY]
    due_soon = [i for i in active if i.due_date and TODAY <= i.due_date <= TODAY + timedelta(days=3)]
    stale = [i for i in active if _days_since_update(i) >= STALE_DAYS and i.status not in ("concluído", "descartado")]
    no_due = [i for i in active if not i.due_date and i.priority == "alta"]

    # Candidates for the agent to pick up: backlog or approved, scored
    candidates = [
        i for i in ideas
        if i.status in ("backlog", "análise - aprovado", "aguardando desenvolvimento")
    ]
    candidates.sort(key=_score, reverse=True)

    # Todos pending across all ideas
    all_todos = []
    for idea in active:
        for idx, t in enumerate(idea.todos):
            if not t.get("done"):
                all_todos.append({"idea": idea, "idx": idx, "text": t["text"],
                                   "due": t.get("due_date")})

    open_bugs = [i for i in active if getattr(i, "is_bug", False)]

    return {
        "total": len(ideas),
        "active": len(active),
        "closed": len(closed),
        "by_status": by_status,
        "overdue": overdue,
        "due_soon": due_soon,
        "stale": stale,
        "no_due_high": no_due,
        "candidates": candidates[:5],  # top 5
        "pending_todos": len(all_todos),
        "open_bugs": open_bugs,
    }


# ── Report generation ─────────────────────────────────────────────────────────

def _status_line(label: str, ok: bool, detail: str = "") -> str:
    icon = "✅" if ok else "❌"
    return f"- {icon} **{label}**" + (f" — {detail}" if detail else "")


def build_report(tests: dict, data: dict) -> str:
    lines = []
    a = data

    # ── Frontmatter ──
    lines += [
        "---",
        f"date: {TODAY}",
        "type: agent-report",
        "tags: [agent, daily-report]",
        "ai-first: true",
        "---",
        "",
        f"> **For future Claude:** Daily health check for {TODAY} — status only, no action list. "
        "This report proposes nothing and expects no approval: the decision loop moved to the "
        "**Weekly Brief** (`agent/weekly_brief.py`), which Kelvin answers in conversation. "
        "Do not treat anything here as a task to execute. "
        "If he asks you to act on a backlog item, run "
        "`python agent/update_status.py <idea_id> \"em desenvolvimento\"` before starting, "
        "and `python agent/update_status.py <idea_id> \"em validação\"` (or `concluído`) when done.",
        "",
        f"# Agent Report — {TODAY}",
        "",
    ]

    # ── Health check ──
    lines += ["## Health check", ""]
    test_detail = f"{tests['passed']} passed" + (f", {tests['failed']} failed" if tests['failed'] else "") + (f", {tests['errors']} errors" if tests['errors'] else "")
    lines.append(_status_line("Tests", tests["ok"], test_detail))

    vault_ok = BACKLOG_DIR.exists()
    lines.append(_status_line("Vault accessible", vault_ok, str(BACKLOG_DIR) if not vault_ok else f"{a['total']} items"))

    overdue_ok = len(a["overdue"]) == 0
    lines.append(_status_line("No overdue items", overdue_ok,
                               f"{len(a['overdue'])} overdue: {', '.join(i.id for i in a['overdue'])}" if a["overdue"] else ""))

    bugs_ok = len(a["open_bugs"]) == 0
    bug_ids = ", ".join(f"`{i.id}`" for i in a["open_bugs"])
    lines.append(
        f"- {'✅' if bugs_ok else '🐛'} **Open bugs** — "
        + ("none" if bugs_ok else f"{len(a['open_bugs'])} open: {bug_ids}")
    )

    lines += [""]

    # ── Backlog snapshot ──
    lines += ["## Backlog snapshot", ""]
    lines.append(f"- **Total:** {a['total']} items ({a['active']} active, {a['closed']} closed)")
    lines.append(f"- **Pending to-dos across all ideas:** {a['pending_todos']}")
    lines += ["", "**By status:**"]
    for status in VALID_STATUSES:
        group = a["by_status"].get(status, [])
        if group:
            ids = ", ".join(f"`{i.id}`" for i in group)
            lines.append(f"- {STATUS_LABEL.get(status, status)}: {len(group)} — {ids}")
    lines += [""]

    # ── Alerts ──
    alerts = []
    if a["overdue"]:
        for i in a["overdue"]:
            alerts.append(f"🔴 `{i.id}` **{i.title}** — overdue since {i.due_date}")
    if a["due_soon"]:
        for i in a["due_soon"]:
            alerts.append(f"🟡 `{i.id}` **{i.title}** — due {i.due_date}")
    if a["stale"]:
        for i in a["stale"]:
            alerts.append(f"🔵 `{i.id}` **{i.title}** — unchanged for {_days_since_update(i)} days (status: {STATUS_LABEL.get(i.status, i.status)})")
    if a["no_due_high"]:
        for i in a["no_due_high"]:
            alerts.append(f"⚪ `{i.id}` **{i.title}** — high priority with no due date")

    if a["open_bugs"]:
        for i in a["open_bugs"]:
            status_en = STATUS_LABEL.get(i.status, i.status)
            alerts.insert(0, f"🐛 `{i.id}` **{i.title}** — {status_en} _(bug)_")

    if alerts:
        lines += ["## Alerts", ""]
        lines += alerts
        lines += [""]

    # ── Proposed actions: removed in Toolkit 2.0 (idea-066) ──
    # This section used to emit a checkbox list of candidate tasks. Over 86
    # reports it produced 1,986 checkboxes and collected 32 approvals (1.6%,
    # none in the final two weeks) — the loop was writing to nobody. Decisions
    # now live in the Weekly Brief, answered in conversation. This report is a
    # health check: it states, it does not ask.

    if not tests["ok"]:
        lines += [
            "## Failing tests",
            "",
            f"- {tests['failed']} test(s) failing. Run `pytest tests/ -v` for details.",
            "",
        ]

    # Phase 2 analysis section is injected by main() after Ollama runs — placeholder marker
    lines += ["<!-- ANALYSIS_SECTION -->", ""]

    # ── Opportunities ──
    opps = []
    if a["stale"]:
        opps.append(f"- {len(a['stale'])} item(s) unchanged for >{STALE_DAYS} days — consider closing or escalating")
    if a["no_due_high"]:
        opps.append(f"- {len(a['no_due_high'])} high-priority item(s) have no due date — set deadlines")
    high_backlog = [i for i in a["by_status"].get("backlog", []) if i.priority == "alta"]
    if len(high_backlog) > 2:
        opps.append(f"- {len(high_backlog)} high-priority items stuck in Backlog — review for quick wins")

    if opps:
        lines += ["## Opportunities", ""]
        lines += opps
        lines += [""]

    lines += [
        "---",
        f"*Generated by TechColab Backlog agent on {TODAY} at {__import__('datetime').datetime.now().strftime('%H:%M')}.*",
    ]

    return "\n".join(lines)


# ── Claude Pro timeline updater ───────────────────────────────────────────────

_EN_MONTHS = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
}

def _today_timeline_str() -> str:
    return f"{TODAY.day} {_EN_MONTHS[TODAY.month]} {TODAY.year}"


def _get_todays_commits(project_root) -> list[str]:
    """Returns meaningful commit messages made today (excludes auto-update commits)."""
    _SKIP = {"auto-update claude pro report", "auto-update"}
    try:
        result = subprocess.run(
            ["git", "log", f"--since={TODAY.isoformat()} 00:00:00",
             "--until=tomorrow", "--format=%s", "--no-merges"],
            cwd=str(project_root), capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        msgs = []
        for line in result.stdout.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            if any(skip in line for skip in _SKIP):
                continue
            msgs.append(line)
        return msgs
    except Exception:
        return []


def _build_timeline_entry(commits: list[str]) -> tuple[str, str]:
    """Returns (title, detail) for a timeline entry given today's commit messages."""
    _PREFIXES = ("feat:", "fix:", "docs:", "refactor:", "chore:", "test:", "style:", "perf:")

    def _clean(msg: str) -> str:
        for p in _PREFIXES:
            if msg.lower().startswith(p):
                return msg[len(p):].strip()
        return msg

    cleaned = [_clean(c) for c in commits]

    if len(cleaned) == 1:
        title = cleaned[0][0].upper() + cleaned[0][1:]
        detail = ""
    else:
        # Use the longest/most descriptive message as the title
        title_src = max(cleaned, key=len)
        title = title_src[0].upper() + title_src[1:]
        rest = [c for c in cleaned if c != title_src]
        detail = "; ".join(rest)

    return title, detail


def _update_claude_pro_report() -> bool:
    """
    Update reports/claude-pro-timeline.json:
      1. Today's entry from git commits (precise, preferred when commits exist).
      2. Backfill — any recent session dates (last 7 days) not yet in the JSON,
         sourced from JSONL scraping.  This covers no-commit days and past gaps.
    Commits and pushes the JSON if anything was added.
    Returns True if at least one new entry was written, False otherwise.
    """
    project_root = Path(__file__).parent.parent
    json_path = project_root / "reports" / "claude-pro-timeline.json"

    try:
        entries: list = []
        if json_path.exists():
            try:
                entries = json.loads(json_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, ValueError):
                safe_print("[agent] Claude Pro timeline: JSON malformed, starting fresh")
                entries = []

        existing_dates: set[str] = {e.get("date") for e in entries}
        today_iso = TODAY.isoformat()
        new_entries: list = []

        # ── Source 1: git commits for today ──────────────────────────────────
        if today_iso not in existing_dates:
            commits = _get_todays_commits(project_root)
            if commits:
                title, detail = _build_timeline_entry(commits)
                new_entries.append({
                    "date": today_iso,
                    "display_date": _today_timeline_str(),
                    "title": title,
                    "detail": detail,
                })
                existing_dates.add(today_iso)  # prevent double-add via scraping
                safe_print(f"[agent] Claude Pro timeline: commit entry '{title}'")

        # ── Source 2: JSONL session scraping (today + backfill last 7 days) ──
        try:
            from agent.scrape_sessions import get_recent_sessions, sessions_to_timeline_entries
            sessions = get_recent_sessions(days_back=7)
            candidates = sessions_to_timeline_entries(sessions, existing_dates)
            if candidates:
                for c in candidates:
                    new_entries.append(c)
                    safe_print(f"[agent] Claude Pro timeline: session entry '{c['title']}' ({c['date']})")
        except Exception as _scrape_err:
            safe_print(f"[agent] Claude Pro timeline: scraping failed ({_scrape_err})")

        if not new_entries:
            safe_print("[agent] Claude Pro timeline: nothing new to add")
            return False

        # Merge and sort newest first
        all_entries = new_entries + entries
        all_entries.sort(key=lambda e: e.get("date", ""), reverse=True)
        json_path.write_text(
            json.dumps(all_entries, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        safe_print(f"[agent] Claude Pro timeline: {len(new_entries)} new entry/entries added")

        # No git add/commit/push here: reports/*.json is generated data and has
        # been gitignored on purpose since 91c4411 (2026-06-02, "untrack
        # personal/generated data"). The auto-commit was left behind and failed
        # on every run for months, printing a scary traceback over a healthy run.
        return True

    except Exception as exc:
        safe_print(f"[agent] Claude Pro timeline update failed: {exc}")
        return False


# ── Notification ──────────────────────────────────────────────────────────────

def _notify(title: str, message: str):
    """
    Notify Kelvin via a blocking, TopMost MessageBox (not a toast).

    A balloon-tip/toast notification was used here originally, but the
    scripts/send-morning-reminder.ps1 and scripts/send-evening-push.ps1
    incident (2026-08-11) showed toast is silently suppressed by Focus
    Assist while still reporting success from the API — so this daily
    agent notification was almost certainly never actually seen. Switched
    to the same MessageBox pattern that fixed those two scripts: not
    subject to Focus Assist, stays on screen until dismissed.
    """
    esc_title = title.replace("'", "''")
    esc_message = message.replace("'", "''")
    script = (
        f"Add-Type -AssemblyName System.Windows.Forms; "
        f"$form = New-Object System.Windows.Forms.Form; "
        f"$form.TopMost = $true; $form.Opacity = 0; $form.ShowInTaskbar = $false; "
        f"$form.StartPosition = 'CenterScreen'; "
        f"$form.Size = New-Object System.Drawing.Size(0, 0); $form.Show(); "
        f"[System.Windows.Forms.MessageBox]::Show($form, '{esc_message}', '{esc_title}', "
        f"[System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Information) | Out-Null; "
        f"$form.Close()"
    )
    subprocess.Popen(["powershell", "-NonInteractive", "-Command", script],
                     creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)


# ── Project auto-discovery ────────────────────────────────────────────────────

def _folder_to_title(folder: str) -> str:
    """'C--Users-Kelvin-okuda-my-project' → 'My Project'"""
    prefix = "C--Users-Kelvin-okuda-"
    name = folder[len(prefix):] if folder.startswith(prefix) else folder
    return name.replace("-", " ").title()


def _auto_discover_projects(data: dict) -> bool:
    """
    Scan recent Claude Code sessions for project folders not yet mapped to any
    initiative. For each unknown folder, insert a draft skeleton into data['active'].
    Returns True if at least one new draft was added.
    """
    try:
        from agent.scrape_sessions import get_recent_sessions, get_unknown_project_folders
        sessions = get_recent_sessions(days_back=30)
        unknown = get_unknown_project_folders(sessions)
        if not unknown:
            return False

        existing_ids = {
            i.get("id") for section in ("active", "completed")
            for i in data.get(section, [])
        }
        added = False
        for folder in sorted(unknown):
            draft_id = f"draft-{folder}"
            if draft_id in existing_ids:
                continue
            title = _folder_to_title(folder)
            data.setdefault("active", []).append({
                "id": draft_id,
                "number": "??",
                "project_path": folder,
                "status": "draft",
                "title": title,
                "category": "Uncategorized",
                "boss": f"Auto-discovered from Claude Code sessions in `{folder}`.",
                "advance": "Narrative pending — will be auto-generated in Phase 2.",
                "body": "",
                "bullets": [],
                "auto_narrative": True,
            })
            safe_print(f"[agent] Auto-discovered project: {title} ({folder})")
            added = True
        return added
    except Exception as exc:
        safe_print(f"[agent] Auto-discovery failed: {exc}")
        return False


# ── Narrative generation via LLM ─────────────────────────────────────────────

def _generate_narrative_with_ollama(
    initiative: dict,
    sessions: list[dict],
    model: str,
) -> dict | None:
    """
    Ask the configured LLM (Ollama or the NETZSCH gateway — see llm_client.py) to
    generate boss/advance/body/bullets for an initiative.
    Uses the last 8 sessions (titles + first user message) as context.
    Returns a dict with the four fields, or None on any failure.
    """
    from llm_client import build_client

    if not sessions:
        return None

    _tag_re = re.compile(r'<[^>]+>.*?</[^>]+>|<[^>]+/>', re.DOTALL)
    _skip_msg = re.compile(
        r'^(execute (approved|the )?|<command|#\s*/obsidian|use the obsidian)',
        re.IGNORECASE,
    )

    _path_re = re.compile(r'[A-Za-z]:\\[^\s,]+')  # strip Windows paths

    def _clean_msg(text: str) -> str:
        text = _tag_re.sub('', text)
        text = _path_re.sub('', text)
        text = text.split('\n')[0].strip()  # first line only
        return text[:120] if len(text) > 8 else ""

    session_lines = []
    for s in sessions[:8]:
        title = s.get("ai_title") or ""
        msgs  = s.get("user_messages", [])
        clean_msgs = [_clean_msg(m) for m in msgs[:3]]
        clean_msgs = [m for m in clean_msgs if m and not _skip_msg.search(m)]
        msg_text = " | ".join(clean_msgs[:2]) if clean_msgs else ""
        parts = [f"[{s['date']}]"]
        if title and not _skip_msg.search(title):
            parts.append(title)
        if msg_text and msg_text != title:
            parts.append(msg_text)
        if len(parts) > 1:
            session_lines.append(" — ".join(parts).strip())

    context = "\n".join(session_lines)
    init_title = initiative.get("title", "Unknown Project")

    prompt = (
        f'You are a technical writer summarizing a software project for a productivity dashboard.\n'
        f'Project name: "{init_title}"\n\n'
        f'Recent Claude Code work sessions (most recent first):\n{context}\n\n'
        f'Write four fields in English. Be specific — avoid restating the project name.\n'
        f'- boss: 1-2 sentences for a manager — what problem does this solve and for whom?\n'
        f'- advance: 1 sentence — the most recent concrete progress or current status\n'
        f'- body: 1 sentence — technical stack or architecture overview\n'
        f'- bullets: 3-4 bullet points (max 12 words each) listing the most important features or outcomes\n\n'
        f'Return ONLY valid JSON. No markdown, no explanation.\n'
        f'{{"boss": "...", "advance": "...", "body": "...", "bullets": ["...", "...", "..."]}}'
    )

    try:
        client = build_client()
        resp = client.chat.completions.create(
            model=model,
            temperature=0.3,
            timeout=120,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.choices[0].message.content or ""

        # Extract JSON block from response (model may wrap it in markdown)
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if not match:
            return None
        json_str = match.group()
        try:
            result = json.loads(json_str)
        except json.JSONDecodeError:
            # Fix invalid backslash escapes (e.g. Windows paths in model output)
            json_str = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', json_str)
            result = json.loads(json_str)
        if not all(k in result for k in ("boss", "advance", "body", "bullets")):
            return None
        if not isinstance(result["bullets"], list):
            return None
        return result

    except Exception as exc:
        safe_print(f"[agent] Narrative generation failed for '{init_title}': {exc}")
        return None


def _auto_update_narratives(data: dict) -> bool:
    """
    For each active initiative with auto_narrative=true, fetch its recent sessions
    and use Ollama to generate/refresh boss, advance, body and bullets.
    Draft initiatives are promoted (status field removed) when narrative is generated.
    Returns True if anything changed.
    """
    from agent.scrape_sessions import get_recent_sessions

    model   = ANALYSIS_MODEL
    changed = False

    # Build session index keyed by project_folder
    sessions_by_folder: dict[str, list[dict]] = {}
    all_sessions = get_recent_sessions(days_back=30)
    for s in all_sessions:
        folder = s.get("project_folder", "")
        sessions_by_folder.setdefault(folder, []).append(s)

    for init in data.get("active", []):
        if not init.get("auto_narrative"):
            continue
        folder = init.get("project_path", "")
        sessions = sessions_by_folder.get(folder, [])

        if not sessions:
            safe_print(f"[agent] Narrative: no sessions found for '{init.get('title')}' ({folder})")
            continue

        is_draft   = init.get("status") == "draft"
        has_manual = bool(init.get("boss", "").strip())
        # Don't overwrite a manually-written narrative unless it's still a draft
        if has_manual and not is_draft:
            safe_print(f"[agent] Narrative: skipping '{init.get('title')}' (manual narrative preserved)")
            continue

        safe_print(f"[agent] Generating narrative for '{init.get('title')}' ({len(sessions)} sessions)...")
        result = _generate_narrative_with_ollama(init, sessions, model)
        if not result:
            safe_print(f"[agent] Narrative generation failed for '{init.get('title')}'")
            continue

        # Update only fields that actually changed
        updated = False
        for field in ("boss", "advance", "body"):
            if result.get(field) and result[field] != init.get(field):
                init[field] = result[field]
                updated = True
        if result.get("bullets") and result["bullets"] != init.get("bullets"):
            init["bullets"] = result["bullets"]
            updated = True

        # Promote draft → active when narrative is generated
        if updated and init.get("status") == "draft":
            del init["status"]
            safe_print(f"[agent] Draft promoted to active: '{init.get('title')}'")

        if updated:
            changed = True
            safe_print(f"[agent] Narrative updated for '{init.get('title')}'")
        else:
            safe_print(f"[agent] Narrative unchanged for '{init.get('title')}'")

    return changed


# ── Claude Pro data auto-updater ─────────────────────────────────────────────

def _update_claude_pro_data(ideas: list) -> None:
    """
    Patch auto_update=true fields in claude-pro-data.json with live backlog stats.
    Currently updates the 'toolkit' initiative advance text with the real item count.
    Commits and pushes the file if anything changed.
    """
    data_path = ROOT / "reports" / "claude-pro-data.json"
    if not data_path.exists():
        safe_print("[agent] claude-pro-data.json not found — skipping data auto-update")
        return

    try:
        data = json.loads(data_path.read_text(encoding="utf-8"))

        _closed = {"concluído", "descartado", "análise - rejeitado"}
        total_ideas  = len(ideas)
        active_ideas = sum(1 for i in ideas if i.status not in _closed)
        open_bugs    = sum(1 for i in ideas for t in i.todos if t.get("is_bug") and not t.get("done"))

        changed = _auto_discover_projects(data)
        if _auto_update_narratives(data):
            changed = True

        for init in data.get("active", []):
            if init.get("auto_update") and init.get("id") == "toolkit":
                bug_note = f" · {open_bugs} open bugs" if open_bugs else ""
                new_advance = (
                    f"App in production with {total_ideas} backlog items "
                    f"({active_ideas} active{bug_note}). "
                    "Dark mode, kanban, filters, bug tracking, Claude agent and Claude Pro report integrated."
                )
                if init.get("advance") != new_advance:
                    init["advance"] = new_advance
                    changed = True

        if changed:
            data["last_updated"] = TODAY.isoformat()
            data_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            safe_print(f"[agent] claude-pro-data.json updated (backlog: {total_ideas} items, {active_ideas} active)")
            # Gitignored generated data — see the note in _update_claude_pro_report.
        else:
            safe_print("[agent] claude-pro-data.json: nothing changed")

    except Exception as exc:
        safe_print(f"[agent] claude-pro-data update failed: {exc}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    """Run the daily report. Returns a process exit code (0 = healthy)."""
    safe_print(f"[agent] Running daily report for {TODAY}")

    # Health: tests
    safe_print("[agent] Running tests...")
    tests = _run_tests()
    safe_print(f"[agent] Tests: {tests['summary']}")

    # Load backlog
    safe_print("[agent] Loading backlog...")
    store = BacklogStore(BACKLOG_DIR)
    ideas = store.load_all()
    safe_print(f"[agent] {len(ideas)} ideas loaded")

    # Analyze
    data = analyze(ideas)

    # Build report
    report_md = build_report(tests, data)

    # Phase 2: analyze ideas under review via Ollama
    under_review = [i for i in ideas if i.status == "em análise"]
    phase2_error: str | None = None
    if under_review:
        safe_print(f"[agent] Phase 2: analyzing {len(under_review)} idea(s) under review...")
        try:
            from agent.analysis_agent import analyze_all, build_report_section
            analyses = analyze_all(ideas)
            crashed = [a for a in analyses if a.get("worker_error")]
            if crashed:
                phase2_error = (
                    f"{len(crashed)}/{len(analyses)} worker(s) crashed "
                    f"({crashed[0]['worker_error']})"
                )
            analysis_section = build_report_section(analyses)
            if analysis_section:
                report_md = report_md.replace("<!-- ANALYSIS_SECTION -->", analysis_section)
        except Exception as _ae:
            phase2_error = f"{type(_ae).__name__}: {_ae}"
            safe_print(f"[agent] Phase 2 analysis failed: {phase2_error}")
            # Never swallow the whole section — leave a flag in the report so a
            # dead analysis phase is visible in Obsidian, not just in the log.
            report_md = report_md.replace(
                "<!-- ANALYSIS_SECTION -->",
                "## Ideas under review\n\n"
                f"> [!failure] Phase 2 did not run — {phase2_error}\n"
                f"> {len(under_review)} idea(s) under review were left unanalysed. "
                "See `logs/agent-last.log`.\n",
            )
    else:
        report_md = report_md.replace("<!-- ANALYSIS_SECTION -->", "")

    if phase2_error:
        safe_print(f"[agent] PHASE 2 FAILED: {phase2_error}")

    # Write report
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / f"report-{TODAY}.md"
    report_path.write_text(report_md, encoding="utf-8")
    safe_print(f"[agent] Report written: {report_path}")

    # Update Claude Pro Report timeline (commits for today + session backfill for last 7 days)
    safe_print("[agent] Updating Claude Pro Report timeline...")
    _update_claude_pro_report()

    # Auto-patch claude-pro-data.json (backlog count, open bugs)
    safe_print("[agent] Updating Claude Pro data (backlog stats)...")
    _update_claude_pro_data(ideas)

    # Process queued recordings (decoupled recorder) + reprocess failed ones.
    # Heavy Whisper+LLM work runs here, off the user's working hours.
    #
    # The guard below matters more than the trigger time. Whisper takes all 12
    # cores for hours: on 2026-08-26 a run that started at 17:30 was still going
    # at 19:20 with the machine at 100% CPU and 705 MB RAM free, and transcription
    # crawled at 6x slower than realtime because it was fighting Kelvin's own
    # session. Task Scheduler catch-up makes this worse, not better — a missed
    # night fires at next logon, which is exactly 07:30. So the job decides for
    # itself whether now is an acceptable time, regardless of why it was started.
    # Manual runs (`python process.py queue`) are unaffected; this only guards the
    # scheduled path. Override with QUEUE_ANYTIME=1.
    _hour = datetime.now().hour
    if os.environ.get("QUEUE_ANYTIME") != "1" and 7 <= _hour < 18:
        safe_print(f"[agent] Fila de gravacoes ADIADA: {_hour}h esta dentro do "
                   f"horario de trabalho (07-18h). Whisper tomaria a maquina "
                   f"por horas. Rode a mao se precisar agora: "
                   f"python call-recorder/process.py queue")
        _skip_queue = True
    else:
        _skip_queue = False

    safe_print("[agent] Processing queued recordings + sweeping failed ones...")
    try:
        if _skip_queue:
            raise RuntimeError("adiado pelo guard de horario de trabalho")
        import sys as _sys
        _cr = str(Path(__file__).parent.parent / "call-recorder")
        if _cr not in _sys.path:
            _sys.path.insert(0, _cr)
        import process as _proc
        _q = _proc.cmd_queue()
        if _q["processed"]:
            safe_print(f"[agent] Queue: processed {len(_q['processed'])} recording(s)")
        # Failures used to be dropped on the floor here: only "processed" was
        # ever printed. On 2026-08-26 a 43-min call transcribed to 98% dots and
        # the run still reported success, because nothing read this list.
        if _q["failed"]:
            safe_print(f"[agent] !! Queue: {len(_q['failed'])} recording(s) FAILED "
                       f"- job kept in recordings/ for retry:")
            for _f in _q["failed"]:
                safe_print(f"[agent]    {_f}")
        if _q["skipped"]:
            safe_print(f"[agent] Queue: {len(_q['skipped'])} orphan job(s) dropped")
        _sw = _proc.cmd_sweep()
        if _sw["reprocessed"]:
            safe_print(f"[agent] Reprocessed {len(_sw['reprocessed'])} call(s): {_sw['reprocessed']}")
    except Exception as _e:
        safe_print(f"[agent] Call queue/sweep skipped: {_e}")

    # Audio retention: enforce RECORDINGS_RETENTION_DAYS every day.
    # record.prune_old_recordings() was only ever called from record.py, i.e. only
    # when a NEW recording was made. After the last recording on 2026-08-11 the
    # policy simply stopped running and 1.08 GB of already-transcribed .wav piled
    # up, 3x past its own 7-day window. Cleanup must not depend on the user
    # happening to record something.
    safe_print("[agent] Pruning old recordings...")
    try:
        import sys as _sys
        _crr = str(Path(__file__).parent.parent / "call-recorder")
        if _crr not in _sys.path:
            _sys.path.insert(0, _crr)
        import record as _record
        _rec_dir = Path(__file__).parent.parent / "call-recorder" / "recordings"
        _n = _record.prune_old_recordings(str(_rec_dir), _record.RECORDINGS_RETENTION_DAYS)
        safe_print(
            f"[agent] Recordings: {_n} file(s) older than "
            f"{_record.RECORDINGS_RETENTION_DAYS} days removed"
        )
    except Exception as _e:
        safe_print(f"[agent] Recording prune skipped: {_e}")

    # Log hygiene: truncate streamlit.log if it grew large (it is not rotated).
    try:
        _log = Path(__file__).parent.parent / "streamlit.log"
        if _log.exists() and _log.stat().st_size > 20 * 1024 * 1024:  # > 20 MB
            _log.write_text("", encoding="utf-8")
            safe_print("[agent] Truncated streamlit.log (>20MB)")
    except Exception:
        pass

    # Pre-generate 1:1 agendas for the Team tab (graceful if Ollama is down)
    safe_print("[agent] Generating 1:1 agendas...")
    try:
        from team_agenda import generate_all
        _ag = generate_all()
        safe_print(f"[agent] Agendas: {len(_ag['ok'])} ok, {len(_ag['failed'])} skipped")
    except Exception as _e:
        safe_print(f"[agent] Agenda generation skipped: {_e}")

    # Action Dashboard: consolidate open action items into Action-Dashboard.md (idea-031).
    # Personal output only — a local vault note + the toast below (no team channel yet).
    safe_print("[agent] Generating Action Dashboard...")
    _dash = None
    try:
        import sys as _sys
        _crd = str(Path(__file__).parent.parent / "call-recorder")
        if _crd not in _sys.path:
            _sys.path.insert(0, _crd)
        import process as _procd
        _dash = _procd.cmd_dashboard()
        safe_print(f"[agent] Dashboard: {_dash['total']} open actions ({_dash['overdue']} overdue)")
    except Exception as _e:
        safe_print(f"[agent] Dashboard generation skipped: {_e}")

    # Weekly brief — written on the first agent run of each ISO week, so it
    # does not depend on the machine being up on a Monday (Toolkit 2.0, idea-066).
    brief_written = False
    try:
        from agent.weekly_brief import generate as _gen_brief, week_id as _wid
        brief_written, _bp = _gen_brief()
        if brief_written:
            safe_print(f"[agent] Weekly brief written for {_wid()}: {_bp}")
        else:
            safe_print(f"[agent] Weekly brief for {_wid()} already exists, skipped.")
    except Exception as _be:
        # A failed brief must not take the health check down with it.
        safe_print(f"[agent] Weekly brief failed: {type(_be).__name__}: {_be}")

    # Notify (Windows toast — local, only the current user sees it)
    all_good = tests["ok"] and not data["overdue"] and not phase2_error
    status_label = "All good" if all_good else "Action needed"
    status_emoji = "OK" if all_good else "WARN"
    msg = f"{data['active']} active items, {data['pending_todos']} pending to-dos, {len(data['stale'])} stale"
    if brief_written:
        msg = "Weekly brief ready | " + msg
    if _dash:
        msg += f" | actions: {_dash['overdue']} overdue, {_dash['today']} today"
    if phase2_error:
        msg = f"PHASE 2 FAILED: {phase2_error} | " + msg
    _notify(f"TechColab Agent - {status_label}", msg)
    safe_print(f"[agent] Done. [{status_emoji}] {status_label}")

    # Non-zero exit so Task Scheduler's "Last Run Result" flags a broken
    # analysis phase instead of reporting a green 0x0 over a no-op run.
    return 1 if phase2_error else 0


if __name__ == "__main__":
    sys.exit(main())
