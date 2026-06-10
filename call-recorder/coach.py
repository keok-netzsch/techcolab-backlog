"""
coach.py — English coach: evaluates an English speech transcript with a local LLM.

Usage:
  python coach.py --transcript path/to/transcript.txt [--topic "optional topic"]

Requires: Ollama running locally (ollama serve) with qwen2.5-coder pulled.
Saves: per-session note + progress log in the Obsidian vault.
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import requests

# Vault root — override with env var TECHCOLAB_VAULT_ROOT; fallback below.
VAULT = os.environ.get(
    "TECHCOLAB_VAULT_ROOT",
    os.path.join(os.path.expanduser("~"), "OneDrive - NETZSCH", "Documents", "TechColab_D&A_KO"),
)
COACH_DIR = Path(VAULT) / "Areas" / "English-Learning"
SESSIONS_DIR = COACH_DIR / "sessions"
PROGRESS_FILE = COACH_DIR / "progress.md"

OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5-coder:latest"  # better structured/JSON output than llama3.2:3b

DIMENSIONS = ["grammar", "vocabulary", "fluency", "structure", "register"]
DIM_PT = {
    "grammar":    "Gramática",
    "vocabulary": "Vocabulário",
    "fluency":    "Fluência",
    "structure":  "Estrutura",
    "register":   "Registro",
}

TOPIC_TYPES = ["meeting", "presentation", "technical", "casual", "negotiation", "interview"]
TOPIC_TYPE_LABELS = {
    "meeting":      "Meeting",
    "presentation": "Presentation",
    "technical":    "Technical",
    "casual":       "Casual",
    "negotiation":  "Negotiation",
    "interview":    "Interview",
}

# Context-specific calibration injected into the evaluation prompt.
TOPIC_TYPE_GUIDANCE = {
    "meeting":      ("Multi-participant meeting. Fluency: short reactive turns are normal, not a deficiency. "
                     "Structure baseline = 5 (conversational). Vocabulary: domain terms show competence."),
    "presentation": ("Prepared presentation. Structure is critical: evaluate signposting, logical flow, opening/closing. "
                     "Fluency: complete sentences expected. Register: formal throughout."),
    "technical":    ("Technical discussion. Vocabulary: jargon (APIs, pipelines, metrics) = competence, not limited range; "
                     "evaluate the glue language between technical terms. Register: semi-formal OK."),
    "casual":       ("Casual conversation. Informal register, contractions, colloquialisms are appropriate — do not penalise. "
                     "Structure: minimal. Fluency: naturalness and idiomaticity are the focus."),
    "negotiation":  ("Negotiation. Register: formal and diplomatic — penalise casual slips. "
                     "Structure: reward hedging ('I understand your concern', 'what if we consider'), clear position-stating."),
    "interview":    ("Professional interview. Structure: STAR answers expected. Register: formal, no contractions. "
                     "Vocabulary: breadth and precision matter. Fluency: complete, coherent sentences expected."),
}


def _check_ollama():
    """Fail fast if Ollama is not reachable."""
    try:
        requests.get("http://localhost:11434/", timeout=3)
    except requests.exceptions.ConnectionError:
        print("[ERROR] Ollama not found at localhost:11434.")
        print("        Start with: ollama serve")
        sys.exit(1)


def _clean_transcript(transcript: str) -> str:
    """Remove Whisper hallucination loops at end of recording (e.g. repeated 'Let's go')."""
    lines = transcript.splitlines()
    if len(lines) < 10:
        return transcript
    # Find where trailing repeated short phrases start
    # A "spam block" = any phrase < 30 chars repeated 5+ times in the last 20% of lines
    tail_start = int(len(lines) * 0.8)
    tail = lines[tail_start:]
    from collections import Counter
    tail_texts = [ln.split("] ", 1)[-1].strip() for ln in tail if "] " in ln]
    if not tail_texts:
        return transcript
    counts = Counter(tail_texts)
    spam_phrases = {phrase for phrase, n in counts.items() if n >= 5 and len(phrase) < 30}
    if not spam_phrases:
        return transcript
    # Drop all lines (from any position) that match a spam phrase
    cleaned = [ln for ln in lines if ln.split("] ", 1)[-1].strip() not in spam_phrases]
    return "\n".join(cleaned)


def _transcript_stats(transcript: str) -> dict:
    """Extract duration and word count from a timestamped transcript."""
    import re as _re
    lines = [ln for ln in transcript.splitlines() if "] " in ln]
    word_count = sum(len(ln.split("] ", 1)[-1].split()) for ln in lines)
    duration_sec = 0
    if lines:
        last_ts = _re.search(r"\[(\d+\.?\d*)s\]", lines[-1])
        if last_ts:
            duration_sec = float(last_ts.group(1))
    return {"words": word_count, "duration_min": round(duration_sec / 60, 1), "lines": len(lines)}


def _sample_excerpt(transcript: str, target_chars: int = 5000) -> str:
    """Return a representative sample: first half + middle half.

    Taking only the first N chars biases against speakers who warm up slowly
    and undersamples vocabulary used later in the conversation.
    For short transcripts the full text is returned unchanged.
    """
    if len(transcript) <= target_chars:
        return transcript
    half = target_chars // 2
    # Beginning slice
    beginning = transcript[:half]
    # Middle slice — start near the centre of the transcript
    mid_start = max(half + 1, len(transcript) // 2 - half // 2)
    middle_raw = transcript[mid_start: mid_start + half]
    # Drop partial first line of the middle slice to avoid cut-off timestamps
    mid_lines = middle_raw.splitlines()
    if len(mid_lines) > 1:
        mid_lines = mid_lines[1:]
    middle = "\n".join(mid_lines)
    return beginning + "\n\n[... middle of transcript ...]\n\n" + middle


def _evaluate(transcript: str, topic: str, topic_type: str = "") -> dict:
    """Send transcript to Ollama and return structured evaluation dict."""
    # ── Session header ────────────────────────────────────────────────────────
    if topic_type:
        type_label  = TOPIC_TYPE_LABELS.get(topic_type, topic_type.title())
        session_header = f"Session type: **{type_label}**" + (f" — {topic}" if topic else "")
    else:
        session_header = f"Topic / context: {topic}" if topic else "Session type: professional business meeting"

    # ── Sampling ──────────────────────────────────────────────────────────────
    excerpt         = _sample_excerpt(transcript)
    stats_full      = _transcript_stats(transcript)
    stats_excerpt   = _transcript_stats(excerpt)
    coverage_pct    = round(stats_excerpt["words"] / max(stats_full["words"], 1) * 100)
    evaluated_words = stats_excerpt["words"]

    # ── Confidence tier (for vocabulary/level reliability) ────────────────────
    if evaluated_words < 150:
        confidence_note = (
            "SAMPLE SIZE WARNING: fewer than 150 speaker words are visible. "
            "Vocabulary and CEFR level estimates have VERY LOW reliability. "
            "Set level_confidence to 'low'. Avoid penalising vocabulary range."
        )
    elif evaluated_words < 400:
        confidence_note = (
            "SAMPLE SIZE: 150–400 words visible. "
            "Vocabulary and CEFR level estimates have MEDIUM reliability. "
            "Set level_confidence to 'medium'. Be conservative on vocabulary scores."
        )
    else:
        confidence_note = (
            "SAMPLE SIZE: 400+ words visible. "
            "Vocabulary and CEFR level estimates have HIGH reliability. "
            "Set level_confidence to 'high'."
        )

    # ── Context-specific guidance ─────────────────────────────────────────────
    type_guidance = TOPIC_TYPE_GUIDANCE.get(topic_type, "")

    context_block = (
        f"RECORDING CONTEXT:\n"
        f"- Total duration: {stats_full['duration_min']} min\n"
        f"- Total words in transcript: ~{stats_full['words']} "
        f"(multi-participant recording — NOT all words belong to the target speaker)\n"
        f"- Words in evaluated sample: ~{evaluated_words} ({coverage_pct}% of recording)\n"
        f"- Sample strategy: beginning + middle of transcript to maximise vocabulary coverage\n"
        f"- {confidence_note}"
    )

    # ── Per-dimension rubric (compact — keep prompt size manageable for CPU LLMs) ─
    rubric = (
        "SCORING RULES (apply strictly before grading):\n"
        "Grammar: evaluate patterns only — isolated slips and sentence fragments in reactive speech are NOT errors.\n"
        "Vocabulary: domain/technical terms (APIs, KPIs, data pipelines) signal expertise, NOT limited range. "
        "Evaluate variety and precision of the NON-technical vocabulary (connectors, hedging, explanations). "
        "Low word count due to short turns ≠ poor range.\n"
        "Fluency: you read TEXT, not audio — assess textual proxies only: sentence variety (simple vs. compound/complex), "
        "connector richness (beyond 'and/but/so'), idiomaticity. Do NOT penalise short reactive turns in meetings.\n"
        "Structure: in meetings the baseline is 5/10 — conversational by design. Score UP for signposting; "
        "score DOWN only for incoherent ideas. For presentations/interviews: evaluate seriously.\n"
        "Register: most reliable score — be confident even on short samples."
    )

    prompt = f"""You are an expert English language coach evaluating a non-native speaker (B1–C1 range, Brazilian Portuguese L1) in a professional context.
Your goal is ACCURATE, FAIR evaluation — neither inflated nor artificially harsh.
IMPORTANT: All text fields in your JSON response (summary, explanation, tip, example, strengths, alternatives, corrected) MUST be written in English only. Never respond in Portuguese.

{session_header}

{context_block}

{f"CONTEXT-SPECIFIC CALIBRATION:\\n{type_guidance}" if type_guidance else ""}

{rubric}

Transcript sample:
---
{excerpt}
---

Return this exact JSON structure (all fields required):
{{
  "scores": {{
    "grammar": <integer 0-10>,
    "vocabulary": <integer 0-10>,
    "fluency": <integer 0-10>,
    "structure": <integer 0-10>,
    "register": <integer 0-10>
  }},
  "overall": <number 0-10, weighted average — for meetings weight grammar/register more; for presentations weight structure/fluency more>,
  "level": "<A1|A2|B1|B2|C1|C2>",
  "level_confidence": "<low|medium|high>",
  "summary": "<2-3 sentences: overall assessment, strongest point, key growth area>",
  "errors": [
    {{
      "type": "<grammar|vocabulary|fluency|structure|register>",
      "original": "<exact phrase from transcript>",
      "corrected": "<corrected version>",
      "explanation": "<why it is wrong and how to fix it>"
    }}
  ],
  "strengths": ["<strength 1>", "<strength 2>"],
  "improvement_tips": [
    {{
      "dimension": "<grammar|vocabulary|fluency|structure|register>",
      "tip": "<concrete, actionable tip specific to what was seen in the transcript>",
      "example": "<example showing the improvement>"
    }}
  ],
  "vocabulary_suggestions": [
    {{
      "used": "<word or phrase the speaker used>",
      "alternatives": ["<more precise or natural alternative>", "<another option>"]
    }}
  ]
}}

Rules:
- Report only PATTERNS, not isolated one-off slips.
- If fewer than 2 clear errors of a type exist, do not list that error type.
- errors list: max 5 items, most impactful first.
- improvement_tips: max 3 items, one per dimension, highest leverage first.
- vocabulary_suggestions: max 4 items."""

    payload = {
        "model":  OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",
    }
    r = requests.post(OLLAMA_URL, json=payload, timeout=1200)  # warm ~14min; cold start adds ~5min
    r.raise_for_status()
    raw = r.json()["response"].strip()

    return json.loads(raw)


def _score_bar(score) -> str:
    """Accept int or float — always returns 10-char bar."""
    filled = int(round(float(score) / 10 * 10))
    filled = max(0, min(10, filled))   # clamp to [0,10]
    return "█" * filled + "░" * (10 - filled)


def _render_session(ev: dict, transcript: str, topic: str, session_dt: datetime, topic_type: str = "") -> str:
    stats = _transcript_stats(transcript)
    excerpt = _sample_excerpt(transcript)
    excerpt_stats = _transcript_stats(excerpt)
    coverage_pct = round(excerpt_stats["words"] / max(stats["words"], 1) * 100)

    lines = [
        "---",
        f"date: {session_dt.strftime('%Y-%m-%d')}",
        f"time: {session_dt.strftime('%H:%M')}",
        "type: english-coach-session",
        "lang: en",
        f"overall: {ev['overall']}",
        f"level: {ev['level']}",
        f"duration_min: {stats['duration_min']}",
        f"words_total: {stats['words']}",
        f"words_evaluated: {excerpt_stats['words']}",
        f"topic_type: {topic_type}" if topic_type else "topic_type: ''",
        "tags: [english-coach]",
        "---",
        "",
        f"# English Coach Session — {session_dt.strftime('%Y-%m-%d')}",
        "",
        f"> {ev['summary']}",
        "",
        f"**Recording:** {stats['duration_min']} min · {stats['words']} words total · "
        f"{excerpt_stats['words']} words evaluated ({coverage_pct}% of transcript)",
        "",
        "## Scores",
        "",
        "| Dimension | Score | Bar |",
        "|-----------|-------|-----|",
    ]
    for dim in DIMENSIONS:
        s = ev["scores"].get(dim, 0)
        lines.append(f"| {DIM_PT[dim]} | {s}/10 | `{_score_bar(s)}` |")
    lines.append(f"| **Overall** | **{ev['overall']}/10** | `{_score_bar(int(round(ev['overall'])))}` |")
    lines.append("")
    _conf = ev.get("level_confidence", "")
    _conf_badge = {"low": " ⚠️ low confidence", "medium": " · medium confidence", "high": ""}.get(_conf, "")
    lines.append(f"**CEFR Level:** {ev['level']}{_conf_badge}")
    lines.append("")

    if ev.get("strengths"):
        lines += ["## Strengths", ""]
        for s in ev["strengths"]:
            lines.append(f"- {s}")
        lines.append("")

    if ev.get("errors"):
        lines += ["## Errors to Fix", ""]
        for e in ev["errors"]:
            lines.append(f"**{e['type'].title()}** — _{e['original']}_")
            lines.append(f"→ **{e['corrected']}**")
            lines.append(f"  {e['explanation']}")
            lines.append("")

    if ev.get("improvement_tips"):
        lines += ["## Improvement Tips", ""]
        for t in ev["improvement_tips"]:
            lines.append(f"**{DIM_PT.get(t['dimension'], t['dimension'])}:** {t['tip']}")
            if t.get("example"):
                lines.append(f"> Example: _{t['example']}_")
            lines.append("")

    if ev.get("vocabulary_suggestions"):
        lines += ["## Vocabulary Upgrades", ""]
        for v in ev["vocabulary_suggestions"]:
            alts = " / ".join(f"_{a}_" for a in v["alternatives"])
            lines.append(f"- _{v['used']}_ → {alts}")
        lines.append("")

    if topic or topic_type:
        topic_display = topic or ""
        if topic_type:
            type_label = TOPIC_TYPE_LABELS.get(topic_type, topic_type.title())
            topic_display = f"**[{type_label}]** {topic_display}".strip()
        lines += ["## Topic", "", topic_display, ""]

    # Evaluated excerpt — sampled beginning + middle
    lines += [
        "## Evaluated excerpt",
        "",
        f"> {excerpt_stats['words']} words sampled ({coverage_pct}% of transcript) — beginning + middle.",
        "",
        "```",
        excerpt.strip(),
        "```",
        "",
    ]

    lines += ["## Full transcript", "", "```", transcript.strip(), "```", ""]

    return "\n".join(lines)


def _update_index(ev: dict, session_dt: datetime, topic: str, topic_type: str = ""):
    """Update Areas/English-Learning/_index.md Current Status section after each session."""
    import re as _re
    index_file = COACH_DIR / "_index.md"
    if not index_file.exists():
        return

    scores = ev.get("scores", {})
    if scores:
        best_dim  = max(scores, key=lambda d: scores.get(d, 0))
        worst_dim = min(scores, key=lambda d: scores.get(d, 0))
        best_label  = DIM_PT.get(best_dim, best_dim.title())
        worst_label = DIM_PT.get(worst_dim, worst_dim.title())
        best_score  = scores[best_dim]
        worst_score = scores[worst_dim]
    else:
        best_label = worst_label = "—"
        best_score = worst_score = 0

    date_str   = session_dt.strftime("%Y-%m-%d")
    level      = ev.get("level", "—")
    overall    = ev.get("overall", 0)

    topic_display = topic or "—"
    if topic_type:
        type_label    = TOPIC_TYPE_LABELS.get(topic_type, topic_type)
        topic_display = f"[{type_label}] {topic_display}" if topic else f"[{type_label}]"

    new_status = (
        f"## Current Status\n\n"
        f"- **Level:** {level} (as of {date_str})\n"
        f"- **Last session:** {date_str} — topic: {topic_display} — overall score: {overall}/10\n"
        f"- **Strongest dimension:** {best_label} ({best_score}/10)\n"
        f"- **Focus area:** {worst_label} ({worst_score}/10)\n"
    )

    content = index_file.read_text(encoding="utf-8")
    # Replace the Current Status block up to the next heading
    content = _re.sub(
        r"## Current Status\n[\s\S]*?(?=\n## |\Z)",
        new_status + "\n",
        content,
    )
    # Update inline level reference in the frontmatter quote
    content = _re.sub(
        r"Current level: [A-Z]\d[^\n]*",
        f"Current level: {level} (as of {date_str})",
        content,
    )
    index_file.write_text(content, encoding="utf-8")


def _append_progress(ev: dict, session_dt: datetime, topic: str, topic_type: str = ""):
    COACH_DIR.mkdir(parents=True, exist_ok=True)

    scores_inline = " | ".join(
        f"{DIM_PT[d]}: {ev['scores'].get(d, 0)}" for d in DIMENSIONS
    )
    topic_cell = topic or "—"
    if topic_type:
        type_label = TOPIC_TYPE_LABELS.get(topic_type, topic_type)
        topic_cell = f"[{type_label}] {topic_cell}" if topic else f"[{type_label}]"
    row = (
        f"| {session_dt.strftime('%Y-%m-%d')} | {ev['overall']}/10 | {ev['level']} "
        f"| {scores_inline} | {topic_cell} |\n"
    )

    if not PROGRESS_FILE.exists():
        header = (
            "# English Coach — Progress Log\n\n"
            "| Date | Overall | Level | Scores | Topic |\n"
            "|------|---------|-------|--------|-------|\n"
        )
        PROGRESS_FILE.write_text(header + row, encoding="utf-8")
    else:
        existing = PROGRESS_FILE.read_text(encoding="utf-8")
        PROGRESS_FILE.write_text(existing + row, encoding="utf-8")


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="English coach — evaluate transcript")
    parser.add_argument("--transcript", required=True, help="Path to .txt transcript")
    parser.add_argument("--topic", default="", help="Optional topic/context hint (free text)")
    parser.add_argument(
        "--topic-type",
        default="",
        choices=TOPIC_TYPES + [""],
        dest="topic_type",
        help=f"Structured session type: {', '.join(TOPIC_TYPES)}",
    )
    parser.add_argument(
        "--date",
        default="",
        help="Override session date (YYYY-MM-DD). Useful when processing a recording made on a previous day.",
    )
    args = parser.parse_args()

    _check_ollama()

    transcript_path = Path(args.transcript)
    if not transcript_path.exists():
        print(f"[ERROR] Transcript not found: {transcript_path}")
        sys.exit(1)

    transcript = transcript_path.read_text(encoding="utf-8").strip()
    if not transcript:
        print("[ERROR] Transcript is empty.")
        sys.exit(1)

    original_lines = len(transcript.splitlines())
    transcript = _clean_transcript(transcript)
    cleaned_lines = len(transcript.splitlines())
    if cleaned_lines < original_lines:
        print(f"[coach] Removed {original_lines - cleaned_lines} hallucination lines from transcript.")

    now = datetime.now()
    if args.date:
        try:
            from datetime import date as _date_cls
            override_date = _date_cls.fromisoformat(args.date)
            now = datetime.combine(override_date, now.time())
            print(f"[coach] Date override: {args.date}")
        except ValueError:
            print(f"[ERROR] Invalid --date format '{args.date}'. Expected YYYY-MM-DD.")
            sys.exit(1)

    session_dt = now.strftime("%Y-%m-%d_%H-%M")
    session_display = now.strftime("%Y-%m-%d %H:%M")

    stats = _transcript_stats(transcript)
    sample = _sample_excerpt(transcript)
    sample_stats = _transcript_stats(sample)
    print(f"\n[coach] Recording: {stats['duration_min']} min · {stats['words']} words total · "
          f"{sample_stats['words']} words sampled for evaluation")
    if args.topic_type:
        print(f"[coach] Session type: {TOPIC_TYPE_LABELS.get(args.topic_type, args.topic_type)}")
    try:
        ev = _evaluate(transcript, args.topic, args.topic_type)
    except json.JSONDecodeError as e:
        print(f"[ERROR] Ollama returned invalid JSON: {e}")
        sys.exit(1)

    # Print summary to terminal
    print(f"\n{'='*60}")
    print(f"  ENGLISH COACH REPORT — {session_display}")
    print(f"{'='*60}")
    print(f"  Overall: {ev['overall']}/10  ({ev['level']})")
    print(f"  {_score_bar(int(round(ev['overall'])))} ")
    print("")
    for dim in DIMENSIONS:
        s = ev["scores"].get(dim, 0)
        print(f"  {DIM_PT[dim]:<12} {s:>2}/10  {_score_bar(s)}")
    print("")
    print(f"  {ev['summary']}")
    if ev.get("errors"):
        print(f"\n  Top issue: {ev['errors'][0]['type'].title()} — {ev['errors'][0]['original']}")
        print(f"  → {ev['errors'][0]['corrected']}")
    print(f"{'='*60}\n")

    # Save session note
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    session_file = SESSIONS_DIR / f"{session_dt}_english-coach.md"
    session_md = _render_session(ev, transcript, args.topic, now, args.topic_type)
    session_file.write_text(session_md, encoding="utf-8")
    print(f"[coach] Session note saved: {session_file}")

    # Append to progress log
    _append_progress(ev, now, args.topic, args.topic_type)
    print(f"[coach] Progress log updated: {PROGRESS_FILE}")

    # Update English-Learning index with latest status
    _update_index(ev, now, args.topic, args.topic_type)
    print(f"[coach] Index updated: {COACH_DIR / '_index.md'}")

    print(f"\nSESSION_FILE:{session_file}")


if __name__ == "__main__":
    main()
