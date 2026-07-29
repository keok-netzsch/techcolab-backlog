"""Recalculate the estimated Opus $/1M-input-token rate shown on the AI Usage page.

Passive correlation only — no live API calls, no new gateway spend. Scans this
machine's claude-netzsch session logs (~/.claude-netzsch/projects/**/*.jsonl) for
Opus turns in the last 7 days, sums their token usage, and divides into the AI
Usage page's own spend-history delta over the same window (using the same
cache-pricing ratios as the original 2026-07-16 estimate: cache-write = 1.25x
input, cache-read = 0.1x input, output = 5x input).

Writes the result to logs/opus-price-estimate.json for views/usage_monitor.py to
read. Falls back to the hardcoded 2026-07-16 estimate if this file doesn't exist
or the window has no Opus data.

Known limitation (accepted tradeoff, chosen 2026-07-19 — see AI/sessions/2026-07-19
in the vault): this only produces a correct number if nothing besides Opus billed
against the gateway key during the window. If Codex (GPT-5.4) or another user
shared the key in that time, the computed rate is wrong with no hard error raised.
As a best-effort (not exhaustive) safety net, this script checks for Codex
activity in the same window and flags `contaminated: true` if found — the app
should show that estimate with a visible warning rather than as a clean number.

Scheduled to run weekly via Windows Task Scheduler (see
scripts/register-opus-price-task.ps1).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_HOME = Path.home()
_CLAUDE_NETZSCH_PROJECTS = _HOME / ".claude-netzsch" / "projects"
_CODEX_NETZSCH_SESSIONS = _HOME / ".codex-netzsch" / "sessions"
_SPEND_HISTORY = Path(__file__).parent.parent / "logs" / "ai-usage-history.jsonl"
_OUTPUT_FILE = Path(__file__).parent.parent / "logs" / "opus-price-estimate.json"

_WINDOW_DAYS = 7
_CACHE_WRITE_RATIO = 1.25
_CACHE_READ_RATIO = 0.1
_OUTPUT_RATIO = 5.0


def _opus_turns_in_window(since: datetime) -> list[dict[str, Any]]:
    turns = []
    if not _CLAUDE_NETZSCH_PROJECTS.exists():
        return turns
    for jsonl_path in _CLAUDE_NETZSCH_PROJECTS.rglob("*.jsonl"):
        try:
            lines = jsonl_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("type") != "assistant":
                continue
            msg = obj.get("message", {})
            if msg.get("model") != "claude-opus-4-8":
                continue
            usage = msg.get("usage")
            if not usage:
                continue
            try:
                ts = datetime.fromisoformat(obj["timestamp"].replace("Z", "+00:00"))
            except (KeyError, ValueError):
                continue
            if ts < since:
                continue
            turns.append(usage)
    return turns


def _codex_activity_in_window(since: datetime) -> bool:
    if not _CODEX_NETZSCH_SESSIONS.exists():
        return False
    for jsonl_path in _CODEX_NETZSCH_SESSIONS.rglob("*.jsonl"):
        try:
            mtime = datetime.fromtimestamp(jsonl_path.stat().st_mtime, tz=timezone.utc)
        except OSError:
            continue
        if mtime >= since:
            return True
    return False


def _spend_delta_in_window(since: datetime) -> float | None:
    if not _SPEND_HISTORY.exists():
        return None
    entries = []
    for line in _SPEND_HISTORY.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        try:
            ts = datetime.fromisoformat(obj["checked_at"])
        except (KeyError, ValueError):
            continue
        spend = obj.get("spend")
        if spend is None:
            continue
        entries.append((ts, float(spend)))
    entries.sort(key=lambda e: e[0])
    windowed = [e for e in entries if e[0] >= since]
    if len(windowed) < 2:
        return None
    return windowed[-1][1] - windowed[0][1]


def main() -> None:
    since = datetime.now(timezone.utc) - timedelta(days=_WINDOW_DAYS)
    turns = _opus_turns_in_window(since)
    spend_delta = _spend_delta_in_window(since)

    if not turns or spend_delta is None or spend_delta <= 0:
        print("Not enough data in the last 7 days to recalculate — leaving existing estimate untouched.")
        return

    total_input = sum(t.get("input_tokens", 0) for t in turns)
    total_cache_write = sum(t.get("cache_creation_input_tokens", 0) for t in turns)
    total_cache_read = sum(t.get("cache_read_input_tokens", 0) for t in turns)
    total_output = sum(t.get("output_tokens", 0) for t in turns)

    weighted_tokens = (
        total_input
        + total_cache_write * _CACHE_WRITE_RATIO
        + total_cache_read * _CACHE_READ_RATIO
        + total_output * _OUTPUT_RATIO
    )
    if weighted_tokens <= 0:
        print("Zero weighted tokens — leaving existing estimate untouched.")
        return

    price_per_token = spend_delta / weighted_tokens
    price_per_million = round(price_per_token * 1_000_000, 4)

    result = {
        "price_per_million_input_tokens": price_per_million,
        "computed_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "window_days": _WINDOW_DAYS,
        "opus_turns_sampled": len(turns),
        "spend_delta_usd": round(spend_delta, 4),
        "contaminated": _codex_activity_in_window(since),
    }
    _OUTPUT_FILE.parent.mkdir(exist_ok=True)
    _OUTPUT_FILE.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Wrote {_OUTPUT_FILE}: ${price_per_million}/1M input tokens "
          f"({len(turns)} Opus turns, contaminated={result['contaminated']})")


if __name__ == "__main__":
    main()
