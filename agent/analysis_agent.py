"""
agent/analysis_agent.py — Phase 2: analysis agent for ideas in "em análise" status.

For each idea under review, calls Ollama to produce a structured analysis:
  - decision:        "approve" | "reject" | "adjust"
  - reasoning:       2-3 sentences explaining the decision
  - suggested_todos: list of concrete next steps (if approved or adjusted)

Results are returned as a list of dicts for inclusion in the daily report.
Can also be called standalone to trigger analysis on demand.

Usage:
    python agent/analysis_agent.py
"""

import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from config import EXTRACTION_MODEL, OLLAMA_BASE_URL


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ollama_base() -> str:
    url = OLLAMA_BASE_URL.rstrip("/")
    return url[:-3] if url.endswith("/v1") else url


def _call_ollama(prompt: str, model: str, timeout: int = 90) -> str | None:
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.2},
    }).encode()
    try:
        req = urllib.request.Request(
            f"{_ollama_base()}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read()).get("response", "")
    except Exception as exc:
        print(f"[analysis_agent] Ollama error: {exc}")
        return None


def _extract_json(raw: str) -> dict | None:
    if not raw:
        return None
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        fixed = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', match.group())
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            return None


# ── Core analysis ─────────────────────────────────────────────────────────────

def analyze_idea(idea, model: str | None = None) -> dict:
    """
    Run Ollama analysis on a single idea.
    Returns a result dict with keys: idea_id, title, decision, reasoning,
    suggested_todos, raw_ok (bool).
    """
    model = model or EXTRACTION_MODEL

    todos_text = "\n".join(
        f"  - {'[x]' if t.get('done') else '[ ]'} {t['text']}"
        for t in (idea.todos or [])
    ) or "  (none)"

    prompt = (
        "You are a product analyst reviewing a backlog idea.\n"
        "Your job: decide if this idea should be approved, rejected, or adjusted.\n\n"
        f"Title: {idea.title}\n"
        f"Area: {idea.area or 'not specified'}\n"
        f"Priority: {idea.priority}\n"
        f"Impact: {idea.impacto or 'not specified'}\n"
        f"Effort: {idea.esforco or 'not specified'}\n"
        f"Description: {idea.description or '(none)'}\n"
        f"Notes: {idea.notes or '(none)'}\n"
        f"Existing to-dos:\n{todos_text}\n\n"
        "Return ONLY valid JSON with these fields:\n"
        "- decision: one of \"approve\", \"reject\", \"adjust\"\n"
        "- reasoning: 2-3 sentences explaining the decision (focus on value, risk, effort)\n"
        "- suggested_todos: list of 2-4 concrete next-step strings (empty list if rejecting)\n\n"
        '{"decision": "...", "reasoning": "...", "suggested_todos": ["...", "..."]}'
    )

    raw = _call_ollama(prompt, model)
    result = _extract_json(raw) if raw else None

    if result and result.get("decision") in ("approve", "reject", "adjust"):
        return {
            "idea_id":        idea.id,
            "title":          idea.title,
            "decision":       result["decision"],
            "reasoning":      result.get("reasoning", ""),
            "suggested_todos": result.get("suggested_todos", []) if isinstance(result.get("suggested_todos"), list) else [],
            "raw_ok":         True,
        }

    return {
        "idea_id":        idea.id,
        "title":          idea.title,
        "decision":       "unknown",
        "reasoning":      "Ollama did not return a valid analysis.",
        "suggested_todos": [],
        "raw_ok":         False,
    }


def analyze_all(ideas: list, model: str | None = None) -> list[dict]:
    """
    Analyze all ideas with status 'em análise'.
    Returns list of analysis dicts, one per idea.
    """
    under_review = [i for i in ideas if i.status == "em análise"]
    if not under_review:
        return []

    results = []
    for idea in under_review:
        print(f"[analysis_agent] Analyzing {idea.id}: {idea.title[:50]}...")
        r = analyze_idea(idea, model)
        results.append(r)
        icon = {"approve": "✅", "reject": "❌", "adjust": "🔄"}.get(r["decision"], "❓")
        print(f"[analysis_agent]   → {icon} {r['decision']}")
    return results


# ── Report section builder ────────────────────────────────────────────────────

_DECISION_LABEL = {
    "approve": "✅ Approve → move to **Approved**",
    "reject":  "❌ Reject → move to **Rejected**",
    "adjust":  "🔄 Adjust → refine before approving",
    "unknown": "❓ Analysis unavailable",
}

_DECISION_STATUS = {
    "approve": "análise - aprovado",
    "reject":  "análise - rejeitado",
    "adjust":  "em análise",
}


def build_report_section(analyses: list[dict]) -> str:
    """Build the '## Ideas under review' markdown section for the daily report."""
    if not analyses:
        return ""

    lines = [
        "## Ideas under review",
        "",
        "> Phase 2 analysis — Ollama reviewed each idea and suggested a decision.",
        "> Check the boxes to apply the suggested status change.",
        "> For 'Adjust' items, to-dos are suggestions — edit before accepting.",
        "",
    ]

    for r in analyses:
        label = _DECISION_LABEL.get(r["decision"], "❓ Unknown")
        lines += [
            f"### `{r['idea_id']}` — {r['title']}",
            "",
            f"**Recommendation:** {label}",
            "",
            f"> {r['reasoning']}",
            "",
        ]

        if r["suggested_todos"]:
            lines.append("**Suggested next steps:**")
            for todo in r["suggested_todos"]:
                lines.append(f"- [ ] {todo}")
            lines.append("")

        # Action checkbox (apply decision)
        target_status = _DECISION_STATUS.get(r["decision"])
        if target_status and r["decision"] != "unknown":
            lines.append(
                f"- [ ] Apply: move `{r['idea_id']}` → status `{target_status}`"
            )
            if r["suggested_todos"] and r["decision"] in ("approve", "adjust"):
                lines.append(
                    f"- [ ] Add suggested to-dos to `{r['idea_id']}`"
                )
        lines.append("")

    return "\n".join(lines)


# ── Standalone entry point ────────────────────────────────────────────────────

def main():
    from backlog.store import BacklogStore
    from config import BACKLOG_DIR

    print("[analysis_agent] Loading backlog...")
    store = BacklogStore(BACKLOG_DIR)
    ideas = store.load_all()

    analyses = analyze_all(ideas)
    if not analyses:
        print("[analysis_agent] No ideas in 'em análise' status.")
        return

    section = build_report_section(analyses)
    print("\n" + section)


if __name__ == "__main__":
    main()
