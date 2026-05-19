"""
agent/daily_report.py — Phase 1: daily analysis, health check, and report generation.

Runs automatically (via Task Scheduler). Reads the backlog, executes tests,
detects opportunities, and writes a structured report to the vault.
The user reviews the report in Obsidian, checks the actions they approve,
and then opens a Claude Code session to execute Phase 2.

Usage:
    python agent/daily_report.py
"""

import re
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

# ── Ensure project root is in sys.path ────────────────────────────────────────
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from config import BACKLOG_DIR, VAULT_ROOT, EXTRACTION_MODEL, CLAUDE_PRO_REPORT_HTML, CLAUDE_PRO_START_DATE
from backlog.store import BacklogStore
from backlog.schema import VALID_STATUSES

TODAY = date.today()
REPORTS_DIR = VAULT_ROOT / "Backlog - to do - app" / "agent-reports"

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
STALE_DAYS = 7  # flag items unchanged for this many days


# ── Helpers ───────────────────────────────────────────────────────────────────

def _run_tests() -> dict:
    """Run pytest and return a summary dict."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(ROOT / "tests"), "-q", "--tb=no"],
        capture_output=True, text=True, cwd=str(ROOT),
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
        f"> **For future Claude:** Daily agent report for {TODAY}. "
        "Check the **Proposed actions** section for items the user has approved (checked boxes). "
        "Execute only those. Do not act on unchecked items.",
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

    if alerts:
        lines += ["## Alerts", ""]
        lines += alerts
        lines += [""]

    # ── Proposed actions ──
    lines += [
        "## Proposed actions",
        "",
        "> Check the boxes you approve. Then open a Claude Code session and say:",
        '> *"Execute the approved items from today\'s agent report."*',
        "",
    ]

    if a["candidates"]:
        lines.append("### Tasks to pick up")
        lines.append("")
        for i in a["candidates"]:
            pico = PRIORITY_ICON.get(i.priority, "⭐")
            effort = i.esforco or "?"
            status_en = STATUS_LABEL.get(i.status, i.status)
            pending_todos = [t for t in i.todos if not t.get("done")]
            if pending_todos:
                # One checkbox per pending to-do, grouped under the idea
                lines.append(f"**`{i.id}`** {pico} _{i.title}_ — {status_en}, effort: {effort}")
                for t in pending_todos:
                    due = f" _(due {t['due_date']})_" if t.get("due_date") else ""
                    lines.append(f"- [ ] {t['text']}{due}")
            else:
                # Idea has no to-dos — propose advancing status
                lines.append(
                    f"- [ ] **`{i.id}`** {pico} {i.title} — move to next status"
                    f" _(currently: {status_en}, effort: {effort})_"
                )
            lines.append("")

    if not tests["ok"]:
        lines += [
            "### Fix failing tests",
            "",
            f"- [ ] **Fix tests** — {tests['failed']} test(s) failing. Run `pytest tests/ -v` for details.",
            "",
        ]

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


# ── Claude Pro Report updater ─────────────────────────────────────────────────

def _update_claude_pro_report() -> bool:
    """
    Update date fields in the Claude Pro Report HTML (local file inside the project).
    The file is committed to the techcolab-backlog repo — no separate external repo needed.
    Returns True on success, False on any error (non-fatal — agent continues).
    """
    html_path = CLAUDE_PRO_REPORT_HTML
    if not html_path.exists():
        print(f"[agent] Claude Pro Report HTML not found: {html_path} — skipping")
        return False

    try:
        html = html_path.read_text(encoding="utf-8")

        # Compute days since adoption
        start = date.fromisoformat(CLAUDE_PRO_START_DATE)
        days_since = (TODAY - start).days

        # Formatted date in Brazilian format
        today_br = TODAY.strftime("%d/%m/%Y")

        # Update "Atualizado em" in header (meta column)
        html = re.sub(
            r"Atualizado em: \d{2}/\d{2}/\d{4}",
            f"Atualizado em: {today_br}",
            html,
        )

        # Update "Dias desde adoção" stat number
        html = re.sub(
            r'(<div class="stat-number">)\d+(</div>\s*<div class="stat-label">Dias desde adoção)',
            rf"\g<1>{days_since}\g<2>",
            html,
        )

        # Update footer date
        html = re.sub(
            r"Relatório atualizado em \d{2}/\d{2}/\d{4}",
            f"Relatório atualizado em {today_br}",
            html,
        )

        html_path.write_text(html, encoding="utf-8")

        # Git commit and push from the project root (reports/ is inside techcolab-backlog)
        project_root = html_path.parent.parent  # reports/ → project root
        subprocess.run(["git", "add", str(html_path)], cwd=str(project_root), check=True)
        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=str(project_root),
        )
        if result.returncode != 0:
            subprocess.run(
                ["git", "commit", "-m", f"chore: auto-update claude pro report to {TODAY}"],
                cwd=str(project_root), check=True,
            )
            subprocess.run(["git", "push"], cwd=str(project_root), check=True)
            print(f"[agent] Claude Pro Report updated and pushed ({today_br}, {days_since} days)")
        else:
            print(f"[agent] Claude Pro Report: no date changes needed")

        return True

    except Exception as exc:
        print(f"[agent] Claude Pro Report update failed: {exc}")
        return False


# ── Notification ──────────────────────────────────────────────────────────────

def _notify(title: str, message: str):
    """Send a Windows toast notification via PowerShell."""
    script = (
        f"Add-Type -AssemblyName System.Windows.Forms; "
        f"$n = New-Object System.Windows.Forms.NotifyIcon; "
        f"$n.Icon = [System.Drawing.SystemIcons]::Information; "
        f"$n.Visible = $true; "
        f"$n.ShowBalloonTip(8000, '{title}', '{message}', "
        f"[System.Windows.Forms.ToolTipIcon]::Info); "
        f"Start-Sleep -Seconds 9; $n.Dispose()"
    )
    subprocess.Popen(["powershell", "-NonInteractive", "-Command", script],
                     creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"[agent] Running daily report for {TODAY}")

    # Health: tests
    print("[agent] Running tests...")
    tests = _run_tests()
    print(f"[agent] Tests: {tests['summary']}")

    # Load backlog
    print("[agent] Loading backlog...")
    store = BacklogStore(BACKLOG_DIR)
    ideas = store.load_all()
    print(f"[agent] {len(ideas)} ideas loaded")

    # Analyze
    data = analyze(ideas)

    # Build report
    report_md = build_report(tests, data)

    # Write report
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / f"report-{TODAY}.md"
    report_path.write_text(report_md, encoding="utf-8")
    print(f"[agent] Report written: {report_path}")

    # Update Claude Pro Report
    print("[agent] Updating Claude Pro Report...")
    _update_claude_pro_report()

    # Notify
    all_good = tests["ok"] and not data["overdue"]
    status_label = "All good" if all_good else "Action needed"
    status_emoji = "OK" if all_good else "WARN"
    msg = f"{data['active']} active items, {data['pending_todos']} pending to-dos, {len(data['candidates'])} tasks proposed"
    _notify(f"TechColab Agent - {status_label}", msg)
    print(f"[agent] Done. [{status_emoji}] {status_label}")


if __name__ == "__main__":
    main()
