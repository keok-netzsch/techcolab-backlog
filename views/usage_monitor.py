"""NETZSCH AI Gateway budget monitor.

The API key is read only from NETZSCH_LLM_API_KEY. It is never displayed,
persisted, or sent anywhere except the configured internal gateway.
"""

from __future__ import annotations

import html
import json
import math
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import altair as alt
import pandas as pd
import requests
import streamlit as st

from components.ui import _STAT_GRID_CSS, stat_grid

_KEY_INFO_URL = "https://litellm.chatbot.netzsch.com/key/info"
_HISTORY_FILE = Path(__file__).parent.parent / "logs" / "ai-usage-history.jsonl"
_RESET_NOTE_FILE = Path(__file__).parent.parent / "logs" / "ai-usage-reset-note.txt"
_DOC_PATH = Path(__file__).parent.parent / "assets" / "Developer-Handbook-V2.pdf"
_INTERESTING_FIELDS = (
    "spend",
    "max_budget",
    "budget_duration",
    "budget_reset_at",
    "tpm_limit",
    "rpm_limit",
)

# The gateway API returns null for these — values as communicated by the NBS
# team / the AI Gateway Developer Handbook, not sourced from the API itself.
MONTHLY_BUDGET = 100.0
GATEWAY_RPM_LIMIT = 100
GATEWAY_TPM_LIMIT = 500_000

# How far back the local snapshot history is kept and read for the charts.
# Calendar-month cycles align with the actual reset: confirmed with NBS (Patrick
# Palarz, 2026-08-03) that the budget resets on the 1st of each month. The gateway
# itself never returns budget_reset_at, so this alignment is not API-verified, but
# it is a confirmed fact from the platform team, not a guess.
HISTORY_RETENTION_DAYS = 90
PROJECTION_WINDOW_DAYS = 3

# Fallback estimated Opus $/1M-input-token rate, back-calculated from a real measured
# call on 2026-07-16 (11,922 input + 176,594 cache-write + 273,666 cache-read + 6,093
# output tokens = $0.34), using Anthropic's published cache-pricing ratios (cache-write
# = 1.25x input, cache-read = 0.1x input, output = 5x input). NOT an official rate —
# /model/info and /spend/logs both return 403 for this key (admin-only endpoints).
# Opus only; other models on this gateway (GPT-5.4, Sonnet, etc.) haven't been
# measured this way yet. scripts/recalc_opus_price.py refreshes this weekly (passive
# correlation from local usage, no live test calls) — see _OPUS_PRICE_FILE below.
OPUS_ESTIMATED_PRICE_PER_MILLION_INPUT = 1.17  # USD, estimated 2026-07-16
_OPUS_PRICE_FILE = Path(__file__).parent.parent / "logs" / "opus-price-estimate.json"


def _load_opus_price_estimate() -> dict[str, Any]:
    """Read the weekly-recalculated Opus price, falling back to the hardcoded one."""
    fallback = {
        "price_per_million_input_tokens": OPUS_ESTIMATED_PRICE_PER_MILLION_INPUT,
        "computed_at": "2026-07-16",
        "contaminated": False,
    }
    try:
        return {**fallback, **json.loads(_OPUS_PRICE_FILE.read_text(encoding="utf-8"))}
    except (OSError, json.JSONDecodeError):
        return fallback


def _find_field(data: Any, name: str) -> Any:
    """Find a gateway field regardless of which wrapper version returns it."""
    if isinstance(data, dict):
        if data.get(name) is not None:
            return data[name]
        for value in data.values():
            found = _find_field(value, name)
            if found is not None:
                return found
    elif isinstance(data, list):
        for value in data:
            found = _find_field(value, name)
            if found is not None:
                return found
    return None


def normalize_key_info(payload: dict[str, Any]) -> dict[str, Any]:
    """Extract stable display fields from LiteLLM key-info responses."""
    return {field: _find_field(payload, field) for field in _INTERESTING_FIELDS}


def get_key_info(api_key: str) -> dict[str, Any]:
    # The corporate shell may expose a local proxy that is not reachable from
    # this desktop app. The NETZSCH gateway is an internal HTTPS endpoint, so
    # connect to it directly rather than inheriting generic proxy variables.
    session = requests.Session()
    session.trust_env = False
    response = session.get(
        _KEY_INFO_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


def _save_snapshot(values: dict[str, Any]) -> None:
    _HISTORY_FILE.parent.mkdir(exist_ok=True)
    entry = {"checked_at": datetime.now().astimezone().isoformat(), **values}
    with _HISTORY_FILE.open("a", encoding="utf-8") as history:
        history.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _load_history() -> list[dict[str, Any]]:
    try:
        if not _HISTORY_FILE.exists():
            return []
        text = _HISTORY_FILE.read_text(encoding="utf-8")
    except OSError:
        return []
    entries: list[dict[str, Any]] = []
    for line in text.splitlines():
        try:
            entry = json.loads(line)
            if isinstance(entry, dict) and entry.get("checked_at"):
                entries.append(entry)
        except json.JSONDecodeError:
            continue
    cutoff = datetime.now().astimezone() - timedelta(days=HISTORY_RETENTION_DAYS)
    kept = []
    for entry in entries:
        try:
            if datetime.fromisoformat(entry["checked_at"]) >= cutoff:
                kept.append(entry)
        except (KeyError, TypeError, ValueError):
            continue
    return kept


def _load_reset_note() -> str:
    try:
        return _RESET_NOTE_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _save_reset_note(note: str) -> None:
    _RESET_NOTE_FILE.parent.mkdir(exist_ok=True)
    _RESET_NOTE_FILE.write_text(note, encoding="utf-8")


def _period_baseline(daily: pd.DataFrame) -> float:
    """Last recorded spend before the 1st of the current calendar month.

    The gateway's "spend" is a lifetime counter that never resets on its own
    (budget_duration/budget_reset_at are always null - confirmed 2026-08-03).
    The monthly reset (1st of each month, confirmed with NBS/Patrick Palarz) is
    a process outside the gateway, so "spend this month" is derived locally:
    current spend minus whatever had already accumulated by the end of last
    month. Recomputes itself every month from history - nothing to maintain.
    """
    if daily.empty:
        return 0.0
    period_start = datetime.now().astimezone().date().replace(day=1)
    before = daily[daily["date"] < period_start]
    if before.empty:
        return 0.0
    return float(before.iloc[-1]["spend"])


def _this_period_only(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Snapshots from the 1st of the current calendar month onward, so burn-rate
    pace reflects this month's activity rather than being dragged by last month."""
    period_start = datetime.now().astimezone().date().replace(day=1)
    kept = []
    for entry in history:
        try:
            if datetime.fromisoformat(entry["checked_at"]).date() >= period_start:
                kept.append(entry)
        except (KeyError, TypeError, ValueError):
            continue
    return kept


def _burn_rate(
    history: list[dict[str, Any]], baseline: float = 0.0, budget: float = MONTHLY_BUDGET
) -> tuple[float | None, float | None]:
    """Spend/day and estimated days left before `budget` is reached this period.

    `history` entries carry the raw (lifetime) gateway spend; `baseline` converts
    the *last* one to a period-relative remaining balance. The daily pace itself
    doesn't need adjusting - a delta between two raw cumulative values already
    equals the period delta, baseline cancels out.
    """
    if len(history) < 2:
        return None, None
    first, last = history[0], history[-1]
    try:
        t0 = datetime.fromisoformat(first["checked_at"])
        t1 = datetime.fromisoformat(last["checked_at"])
        spend0 = float(first.get("spend"))
        spend1 = float(last.get("spend"))
    except (KeyError, TypeError, ValueError):
        return None, None
    days = max((t1 - t0).total_seconds() / 86400, 1 / 24)
    spend_delta = spend1 - spend0
    if days < 0.5 or spend_delta <= 0:
        return None, None
    per_day = spend_delta / days
    period_spend1 = max(0.0, spend1 - baseline)
    remaining = max(0.0, budget - period_spend1)
    days_left = remaining / per_day if per_day > 0 else None
    return per_day, days_left


def _month_end(day: date) -> date:
    next_month = day.replace(day=28) + timedelta(days=4)
    return next_month - timedelta(days=next_month.day)


def _daily_spend(history: list[dict[str, Any]]) -> pd.DataFrame:
    """Collapse snapshots to one row per day: end-of-day cumulative spend + that day's delta."""
    rows = []
    for entry in history:
        spend = _as_float(entry.get("spend"))
        if spend is None:
            continue
        try:
            checked_at = datetime.fromisoformat(entry["checked_at"])
        except (KeyError, TypeError, ValueError):
            continue
        rows.append({"date": checked_at.date(), "checked_at": checked_at, "spend": spend})
    if not rows:
        return pd.DataFrame(columns=["date", "spend", "day_spend"])
    df = pd.DataFrame(rows).sort_values("checked_at")
    daily = df.groupby("date", as_index=False).last()[["date", "spend"]].sort_values("date").reset_index(drop=True)
    day_spend = daily["spend"].diff()
    day_spend.iloc[0] = daily["spend"].iloc[0]
    daily["day_spend"] = day_spend.clip(lower=0)
    return daily


def _current_month_series(daily: pd.DataFrame) -> pd.DataFrame:
    if daily.empty:
        return daily
    today = datetime.now().astimezone().date()
    return daily[daily["date"] >= today.replace(day=1)].reset_index(drop=True)


def _project_current_month(daily: pd.DataFrame, month_df: pd.DataFrame) -> pd.DataFrame | None:
    """Straight-line projection to month end from a trailing moving-average pace."""
    if month_df.empty:
        return None
    today = datetime.now().astimezone().date()
    recent = daily[daily["date"] <= today].tail(PROJECTION_WINDOW_DAYS)
    if recent.empty:
        return None
    avg_daily = recent["day_spend"].mean()
    if not avg_daily or avg_daily <= 0:
        return None
    last_date = month_df["date"].max()
    month_end = _month_end(last_date)
    if last_date >= month_end:
        return None
    last_spend = float(month_df.loc[month_df["date"] == last_date, "spend"].iloc[0])
    n_days = (month_end - last_date).days
    rows = [{"date": last_date, "spend": last_spend}]
    rows += [{"date": last_date + timedelta(days=i), "spend": last_spend + avg_daily * i} for i in range(1, n_days + 1)]
    return pd.DataFrame(rows)


def _monthly_totals(daily: pd.DataFrame) -> pd.DataFrame:
    """Approximate per-calendar-month spend as the increase in the cumulative counter.

    This is a proxy: the gateway never reports the real budget_reset_at, so a reset
    that lands mid-month will show up as a dip inside that month rather than a clean
    cutoff. Floored at 0 so a reset never reads as negative spend.
    """
    if daily.empty:
        return pd.DataFrame(columns=["month", "total"])
    df = daily.copy()
    df["month"] = df["date"].apply(lambda d: d.replace(day=1))
    monthly = df.groupby("month", as_index=False)["spend"].last().sort_values("month").reset_index(drop=True)
    monthly["prev_spend"] = monthly["spend"].shift(1).fillna(0.0)
    monthly["total"] = (monthly["spend"] - monthly["prev_spend"]).clip(lower=0)
    return monthly[["month", "total"]]


def _suggest_monthly_limit(daily: pd.DataFrame) -> dict[str, float] | None:
    """Rough heuristic for what monthly budget would cover the observed pace.

    Uses the higher of the whole-history daily average and the last-7-days average
    (so an accelerating pace isn't masked by a slow start), projects it to a 30-day
    month, and adds a 20% buffer. Needs at least 3 days of data to mean anything.
    """
    if daily.empty or len(daily) < 3:
        return None
    span_days = (daily["date"].max() - daily["date"].min()).days + 1
    if span_days <= 0:
        return None
    total_spend = float(daily["day_spend"].sum())
    avg_daily = total_spend / span_days
    recent = daily.tail(7)
    recent_avg = float(recent["day_spend"].mean()) if not recent.empty else avg_daily
    pace = max(avg_daily, recent_avg)
    projected_30d = pace * 30
    suggested = math.ceil(projected_30d * 1.2 / 25) * 25
    return {
        "avg_daily": avg_daily,
        "recent_avg": recent_avg,
        "projected_30d": projected_30d,
        "suggested": float(suggested),
        "span_days": float(span_days),
    }


_CHART_AXIS_KW = dict(
    grid=True,
    # Low-alpha gray instead of a solid hex: a light-mode-tuned solid color (e.g. #F3F4F6)
    # reads as a near-white line on Streamlit's dark background. Opacity keeps it subtle
    # against either surface without needing to detect the active theme.
    gridColor="rgba(148,163,184,0.14)",
    domainColor="rgba(148,163,184,0.35)",
    tickColor="rgba(148,163,184,0.35)",
    labelColor="#6B7280",
    labelFontSize=10,
    titleColor="#6B7280",
    titleFontSize=11,
)


def _render_month_chart(month_df: pd.DataFrame, projected_df: pd.DataFrame | None, budget: float) -> None:
    actual = alt.Chart(month_df).mark_area(
        line={"color": "#02B793", "strokeWidth": 2},
        color="#02B793",
        opacity=0.16,
        interpolate="monotone",
    ).encode(
        x=alt.X("date:T", title=None),
        y=alt.Y("spend:Q", title="Spend (USD)", scale=alt.Scale(zero=True)),
        tooltip=[alt.Tooltip("date:T", title="Date"), alt.Tooltip("spend:Q", title="Spend", format="$.2f")],
    )
    budget_rule = alt.Chart(pd.DataFrame({"y": [budget]})).mark_rule(
        strokeDash=[4, 4], color="#9CA3AF", strokeWidth=1.5,
    ).encode(y="y:Q")
    layers = [actual, budget_rule]

    if projected_df is not None and len(projected_df) > 1:
        projected = alt.Chart(projected_df).mark_line(
            strokeDash=[5, 4], color="#02B793", opacity=0.55, strokeWidth=2, interpolate="monotone",
        ).encode(
            x="date:T",
            y="spend:Q",
            tooltip=[
                alt.Tooltip("date:T", title="Date (projected)"),
                alt.Tooltip("spend:Q", title="Projected spend", format="$.2f"),
            ],
        )
        layers.append(projected)

    chart = (
        alt.layer(*layers)
        .properties(height=220)
        .configure_view(strokeWidth=0)
        .configure_axis(**_CHART_AXIS_KW)
    )
    st.altair_chart(chart, use_container_width=True)
    legend_bits = [
        '<span style="color:#02B793">■</span> Actual spend',
        f'<span style="color:#9CA3AF">- - -</span> Budget ({_money(budget)})',
    ]
    if projected_df is not None and len(projected_df) > 1:
        legend_bits.append('<span style="color:#02B793;opacity:.55">- - -</span> Projected (3-day avg pace)')
    st.markdown(
        f'<p style="font-size:.72rem;color:#6B7280;margin:.2rem 0 0">{"  ·  ".join(legend_bits)}</p>',
        unsafe_allow_html=True,
    )


def _render_monthly_history_chart(monthly: pd.DataFrame, budget: float) -> None:
    df = monthly.copy()
    df["month_label"] = df["month"].apply(lambda d: d.strftime("%b %Y"))
    bars = alt.Chart(df).mark_bar(
        color="#02B793", cornerRadiusTopLeft=3, cornerRadiusTopRight=3, size=28,
    ).encode(
        x=alt.X("month_label:N", title=None, sort=list(df["month_label"])),
        y=alt.Y("total:Q", title="Spend (USD)", scale=alt.Scale(zero=True)),
        tooltip=[alt.Tooltip("month_label:N", title="Month"), alt.Tooltip("total:Q", title="Total spend", format="$.2f")],
    )
    budget_rule = alt.Chart(pd.DataFrame({"y": [budget]})).mark_rule(
        strokeDash=[4, 4], color="#9CA3AF", strokeWidth=1.5,
    ).encode(y="y:Q")
    chart = (
        alt.layer(bars, budget_rule)
        .properties(height=180)
        .configure_view(strokeWidth=0)
        .configure_axis(**_CHART_AXIS_KW)
    )
    st.altair_chart(chart, use_container_width=True)
    st.markdown(
        f'<p style="font-size:.72rem;color:#6B7280;margin:.2rem 0 0">'
        f'<span style="color:#02B793">■</span> Spend per calendar month  ·  '
        f'<span style="color:#9CA3AF">- - -</span> Budget ({_money(budget)})  ·  '
        'resets 1st of month, confirmed with NBS</p>',
        unsafe_allow_html=True,
    )


def _money(value: Any) -> str:
    if value is None:
        return "Not provided"
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return str(value)


def _value(value: Any) -> str:
    return "Not provided" if value is None else html.escape(str(value))


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fmt_checked_at(value: Any) -> str:
    """Compact timestamp for the checks table — the raw ISO string (with microseconds
    and UTC offset) is what made that table read so wide."""
    if not value:
        return "Not provided"
    try:
        return datetime.fromisoformat(str(value)).strftime("%b %d, %H:%M")
    except ValueError:
        return html.escape(str(value))


def render() -> None:
    st.subheader("AI Usage")
    st.markdown(_STAT_GRID_CSS, unsafe_allow_html=True)
    st.markdown(
        '<p style="font-size:.75rem;color:#9CA3AF;margin:.1rem 0 .8rem">'
        "NETZSCH AI Gateway budget · manual refresh · local history only"
        "</p>",
        unsafe_allow_html=True,
    )

    api_key = os.getenv("NETZSCH_LLM_API_KEY")
    if not api_key:
        st.markdown(
            '<div style="margin:.4rem 0;padding:.5rem .75rem;border-radius:6px;'
            'border-left:3px solid #EF4444;background:rgba(239,68,68,.05)">'
            '<span style="font-size:.7rem;color:#EF4444;font-weight:700;'
            'text-transform:uppercase;letter-spacing:.04em">Connection needed</span><br>'
            'NETZSCH_LLM_API_KEY is not available to this app process. Set it as a user environment '
            'variable, then restart the Toolkit. The key is never shown or saved here.'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    _col_refresh, _col_doc = st.columns([1, 3])
    with _col_refresh:
        refresh_clicked = st.button("Refresh balance", type="primary", use_container_width=False)
    with _col_doc:
        if _DOC_PATH.exists():
            st.download_button(
                "📄 Documentation",
                data=_DOC_PATH.read_bytes(),
                file_name=_DOC_PATH.name,
                mime="application/pdf",
            )

    if refresh_clicked:
        try:
            with st.spinner("Checking the gateway…"):
                snapshot = normalize_key_info(get_key_info(api_key))
            st.session_state["ai_usage_snapshot"] = snapshot
        except requests.RequestException as error:
            st.markdown(
                '<div style="margin:.4rem 0;padding:.5rem .75rem;border-radius:6px;'
                'border-left:3px solid #EF4444;background:rgba(239,68,68,.05)">'
                '<span style="font-size:.7rem;color:#EF4444;font-weight:700;'
                'text-transform:uppercase;letter-spacing:.04em">Refresh failed</span><br>'
                f'{html.escape(str(error))}'
                '</div>',
                unsafe_allow_html=True,
            )
        else:
            try:
                _save_snapshot(snapshot)
            except OSError as error:
                st.markdown(
                    '<div style="margin:.4rem 0;padding:.5rem .75rem;border-radius:6px;'
                    'border-left:3px solid #F59E0B;background:rgba(245,158,11,.05)">'
                    '<span style="font-size:.7rem;color:#F59E0B;font-weight:700;'
                    'text-transform:uppercase;letter-spacing:.04em">History not saved</span><br>'
                    f'Balance refreshed, but the local history file could not be updated: {html.escape(str(error))}'
                    '</div>',
                    unsafe_allow_html=True,
                )

    snapshot = st.session_state.get("ai_usage_snapshot")
    history = _load_history()
    daily = _daily_spend(history)
    if snapshot is None and history:
        snapshot = history[-1]

    if snapshot is None:
        st.markdown(
            '<div style="margin:.4rem 0;padding:.5rem .75rem;border-radius:6px;'
            'border-left:3px solid #6366F1;background:rgba(99,102,241,.05)">'
            '<span style="font-size:.7rem;color:#6366F1;font-weight:700;'
            'text-transform:uppercase;letter-spacing:.04em">Ready</span><br>'
            'Select Refresh balance to retrieve the current budget from the internal gateway.'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    spend = snapshot.get("spend")
    max_budget = snapshot.get("max_budget")
    budget_is_estimated = max_budget is None
    if budget_is_estimated:
        max_budget = MONTHLY_BUDGET

    baseline = _period_baseline(daily)
    period_spend = max(0.0, (_as_float(spend) or 0.0) - baseline)

    percent = None
    try:
        if float(max_budget) > 0:
            percent = min(100, max(0, period_spend / float(max_budget) * 100))
    except (TypeError, ValueError):
        pass

    remaining = "Not provided"
    try:
        remaining = _money(float(max_budget) - period_spend)
    except (TypeError, ValueError):
        pass

    reset_at = snapshot.get("budget_reset_at")
    reset_is_local_note = reset_at is None

    per_day, days_left = _burn_rate(_this_period_only(history), baseline, float(max_budget))
    opus_price = _load_opus_price_estimate()
    computed_at = _value(opus_price.get("computed_at"))[:10]
    current_budget = _as_float(max_budget) or MONTHLY_BUDGET
    suggestion = _suggest_monthly_limit(daily)

    _ROW1_HEIGHT = 190

    _col_budget, _col_cost, _col_pace, _col_current, _col_suggested = st.columns(5)

    with _col_budget:
        with st.container(height=_ROW1_HEIGHT, border=True):
            label = "Budget this month" + (" · as informed by you" if budget_is_estimated else "")
            st.markdown(f'<div class="cc-sl">{html.escape(label)}</div>', unsafe_allow_html=True)
            percent_text = f"{percent:.0f}% used" if percent is not None else "—"
            st.markdown(
                stat_grid(
                    [{"label": percent_text, "value": _money(period_spend), "vstyle": "font-size:1.6rem;font-weight:800"}],
                    columns=1,
                ),
                unsafe_allow_html=True,
            )
            st.caption(f"{remaining} remaining".replace("$", "\\$"))

    with _col_cost:
        with st.container(height=_ROW1_HEIGHT, border=True):
            st.markdown('<div class="cc-sl">Cost per million tokens</div>', unsafe_allow_html=True)
            st.markdown(
                stat_grid(
                    [{
                        "label": f"Claude Opus (est. {computed_at})",
                        "value": _money(opus_price["price_per_million_input_tokens"]),
                        "vstyle": "font-size:1.6rem;font-weight:800",
                    }],
                    columns=1,
                ),
                unsafe_allow_html=True,
            )
            st.caption(
                "⚠ Estimate skewed this week (Codex activity in window)."
                if opus_price.get("contaminated")
                else "Estimate — gateway pricing endpoints return 403 for this key."
            )

    with _col_pace:
        with st.container(height=_ROW1_HEIGHT, border=True):
            st.markdown('<div class="cc-sl">Consumption pace</div>', unsafe_allow_html=True)
            pace_value = f"{_money(per_day)}/day" if per_day is not None else "—"
            st.markdown(
                stat_grid([{"label": "Spend pace", "value": pace_value, "vstyle": "font-size:1.6rem;font-weight:800"}], columns=1),
                unsafe_allow_html=True,
            )
            if per_day is None:
                st.caption("Need 2+ checks on different days.")
            else:
                note = (
                    f"~{days_left:.0f} days until budget reached.".replace("$", "\\$")
                    if days_left is not None
                    else "Negligible pace."
                )
                st.caption(note)

    with _col_current:
        with st.container(height=_ROW1_HEIGHT, border=True):
            st.markdown('<div class="cc-sl">Current budget</div>', unsafe_allow_html=True)
            st.markdown(
                stat_grid([{"label": "This month", "value": _money(current_budget), "vstyle": "font-size:1.6rem;font-weight:800"}], columns=1),
                unsafe_allow_html=True,
            )
            st.caption("Informal cap from NBS." if budget_is_estimated else "From the gateway.")

    with _col_suggested:
        with st.container(height=_ROW1_HEIGHT, border=True):
            st.markdown('<div class="cc-sl">Suggested for your pace</div>', unsafe_allow_html=True)
            suggested_value = _money(suggestion["suggested"]) if suggestion is not None else "—"
            st.markdown(
                stat_grid([{"label": "30-day + buffer", "value": suggested_value, "vstyle": "font-size:1.6rem;font-weight:800"}], columns=1),
                unsafe_allow_html=True,
            )
            st.caption("Needs 3+ days of history." if suggestion is None else "Heuristic — see note below.")

    if suggestion is not None:
        if suggestion["suggested"] > current_budget:
            card_label, card_color = "Opportunity", "#6366F1"
            action_text = (
                f'Your pace projects to about {html.escape(_money(suggestion["projected_30d"]))} over a '
                f'30-day month. Consider asking NBS for a {html.escape(_money(suggestion["suggested"]))} '
                "limit so you don't get blocked mid-month."
            )
        else:
            card_label, card_color = "On track", "#059669"
            action_text = (
                f'Your current budget already covers your pace '
                f'({html.escape(_money(suggestion["projected_30d"]))} projected over 30 days) with room to spare.'
            )
        st.markdown(
            f'<div style="margin:.4rem 0 0;padding:.5rem .75rem;border-radius:6px;'
            f'border-left:3px solid {card_color};background:rgba(0,0,0,.03)">'
            f'<span style="font-size:.7rem;color:{card_color};font-weight:700;'
            f'text-transform:uppercase;letter-spacing:.04em">{card_label}</span><br>'
            f'<span style="font-size:.78rem;color:#6B7280">{action_text}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<p style="font-size:.7rem;color:#9CA3AF;margin:.4rem 0 0">'
            f'Based on {suggestion["span_days"]:.0f} days observed: '
            f'{html.escape(_money(suggestion["avg_daily"]))}/day average, '
            f'{html.escape(_money(suggestion["recent_avg"]))}/day over the last 7 days · '
            "30-day projection with a 20% buffer, rounded to the nearest $25. "
            "Rough heuristic on a small sample — revisit as more history accumulates."
            "</p>",
            unsafe_allow_html=True,
        )

    with st.expander("Gateway limits & budget reset", expanded=False):
        rpm_limit = snapshot.get("rpm_limit")
        tpm_limit = snapshot.get("tpm_limit")
        limits_are_fixed = rpm_limit is None and tpm_limit is None
        if rpm_limit is None:
            rpm_limit = GATEWAY_RPM_LIMIT
        if tpm_limit is None:
            tpm_limit = GATEWAY_TPM_LIMIT
        st.markdown(
            stat_grid(
                [
                    ("Requests per minute", f"{rpm_limit:,}"),
                    ("Tokens per minute", f"{tpm_limit:,}"),
                    ("Budget period", _value(snapshot.get("budget_duration"))),
                ],
                columns=3,
            ),
            unsafe_allow_html=True,
        )
        if limits_are_fixed:
            st.caption("Fixed limits from the AI Gateway Developer Handbook — the API doesn't return them.")

        if reset_is_local_note:
            saved_note = _load_reset_note()
            st.markdown(
                stat_grid(
                    [{"label": "Budget reset", "value": saved_note or "1st of every calendar month", "vstyle": "font-size:1.4rem"}],
                    columns=1,
                ),
                unsafe_allow_html=True,
            )
            st.caption(
                "Confirmed with NBS (Patrick Palarz, 2026-08-03): resets on the 1st of each calendar "
                "month. Not returned by the API (budget_reset_at is always null) — this is a "
                "manually confirmed fact, not a guess."
            )
            with st.expander("Different for your key? Override here", expanded=False):
                note_input = st.text_input(
                    "Reset note",
                    value=saved_note,
                    placeholder="e.g. 2026-08-15",
                    label_visibility="collapsed",
                )
                if st.button("Save", key="save_reset_note"):
                    try:
                        _save_reset_note(note_input.strip())
                        st.rerun()
                    except OSError as error:
                        st.markdown(
                            '<div style="margin:.4rem 0;padding:.5rem .75rem;border-radius:6px;'
                            'border-left:3px solid #F59E0B;background:rgba(245,158,11,.05)">'
                            f'Could not save the note: {html.escape(str(error))}</div>',
                            unsafe_allow_html=True,
                        )
        else:
            st.markdown(
                stat_grid([{"label": "Budget reset", "value": _value(reset_at), "vstyle": "font-size:1.4rem"}], columns=1),
                unsafe_allow_html=True,
            )

    chart_budget = _as_float(max_budget) or MONTHLY_BUDGET
    month_df = _current_month_series(daily)

    st.subheader("Spend this month")
    if month_df.empty:
        st.caption("Need at least one check this month to chart spend.")
    else:
        projected_df = _project_current_month(daily, month_df)
        _render_month_chart(month_df, projected_df, chart_budget)

    monthly = _monthly_totals(daily)
    st.subheader("Monthly history")
    if monthly.empty:
        st.caption("Not enough history yet to compare months.")
    else:
        _render_monthly_history_chart(monthly, chart_budget)

    if history:
        st.subheader("Recent checks")
        recent = history[-10:]
        spends = [_as_float(entry.get("spend")) for entry in recent]
        deltas: list[float | None] = [None]
        for i in range(1, len(recent)):
            deltas.append(spends[i] - spends[i - 1] if spends[i] is not None and spends[i - 1] is not None else None)

        _table_col, _ = st.columns([2, 1])
        with _table_col:
            _h0, _h1, _h2 = st.columns([2, 1, 2])
            _h0.caption("Checked at")
            _h1.caption("Spent")
            _h2.caption("Since previous check")
            for entry, delta in reversed(list(zip(recent, deltas))):
                _c0, _c1, _c2 = st.columns([2, 1, 2])
                _c0.markdown(
                    f'<span style="font-size:.78rem;color:#6B7280">{_fmt_checked_at(entry.get("checked_at"))}</span>',
                    unsafe_allow_html=True,
                )
                _c1.markdown(f'<span style="font-size:.78rem">{_money(entry.get("spend"))}</span>', unsafe_allow_html=True)
                if delta is None:
                    _c2.markdown('<span style="font-size:.78rem;color:#9CA3AF">—</span>', unsafe_allow_html=True)
                elif delta > 0:
                    _c2.markdown(f'<span style="font-size:.78rem;color:#EF4444">+{_money(delta)}</span>', unsafe_allow_html=True)
                else:
                    _c2.markdown(f'<span style="font-size:.78rem;color:#9CA3AF">{_money(0)}</span>', unsafe_allow_html=True)
