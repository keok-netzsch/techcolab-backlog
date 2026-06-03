"""views/dashboard.py — Dashboard page (CC activity, backlog metrics, deadline calendar)."""

import calendar as _cal_mod
import json
import re
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

import streamlit as st

from backlog.cache import load_ideas
from backlog.schema import VALID_PRIORITIES, VALID_STATUSES
from components.ui import (
    EFFORT_LABEL,
    IMPACT_LABEL,
    PRIORITY_LABEL,
    PRIORITY_NUM,
    STATUS_COLOR,
    STATUS_LABEL,
    sdot,
)
from config import EXTRACTION_MODEL, OLLAMA_BASE_URL, VAULT_ROOT

# ── Claude Code stats loader ──────────────────────────────────────────────────

def _load_full_cc_stats() -> dict:
    msgs_by_day:         Counter = Counter()
    msgs_by_hour:        Counter = Counter()
    msgs_by_day_hour:    dict    = {}
    tokens_by_day:       Counter = Counter()
    output_by_day:       Counter = Counter()
    cache_read = cache_create = 0
    cache_read_by_day:   Counter = Counter()
    cache_create_by_day: Counter = Counter()
    model_counts: Counter = Counter()
    sessions: set = set()
    projects: Counter = Counter()

    _hist = Path.home() / ".claude" / "history.jsonl"
    if _hist.exists():
        try:
            with open(_hist, encoding="utf-8") as _hf:
                for _line in _hf:
                    try:
                        _e = json.loads(_line)
                        _p = _e.get("project", "")
                        if _p:
                            projects[Path(_p).name] += 1
                    except Exception:
                        continue
        except Exception:
            pass

    _pdir = Path.home() / ".claude" / "projects"
    if _pdir.exists():
        for _jf in _pdir.glob("**/*.jsonl"):
            sessions.add(_jf.stem)
            try:
                with open(_jf, encoding="utf-8") as _sf:
                    for _line in _sf:
                        try:
                            _e    = json.loads(_line)
                            _ts   = _e.get("timestamp", "")
                            if not _ts:
                                continue
                            _dobj = datetime.fromisoformat(_ts.replace("Z", "+00:00"))
                            _d    = _dobj.date()
                            _etype = _e.get("type", "")
                            if _etype == "user":
                                _msg = _e.get("message", _e)
                                _cnt = _msg.get("content", "")
                                if isinstance(_cnt, str) and _cnt.strip():
                                    msgs_by_day[_d] += 1
                                    msgs_by_hour[_dobj.hour] += 1
                                    if _d not in msgs_by_day_hour:
                                        msgs_by_day_hour[_d] = Counter()
                                    msgs_by_day_hour[_d][_dobj.hour] += 1
                            elif _etype == "assistant":
                                _mod = _e.get("message", {}).get("model", "")
                                if _mod and _mod != "<synthetic>":
                                    model_counts[_mod] += 1
                                _usage = _e.get("message", {}).get("usage")
                                if _usage:
                                    _inp = _usage.get("input_tokens", 0)
                                    _out = _usage.get("output_tokens", 0)
                                    _cr  = _usage.get("cache_read_input_tokens", 0)
                                    _cc2 = _usage.get("cache_creation_input_tokens", 0)
                                    tokens_by_day[_d]          += _inp + _out + _cr + _cc2
                                    output_by_day[_d]          += _out
                                    cache_read                 += _cr
                                    cache_create               += _cc2
                                    cache_read_by_day[_d]      += _cr
                                    cache_create_by_day[_d]    += _cc2
                        except Exception:
                            continue
            except Exception:
                continue

    return dict(
        sessions=len(sessions),
        msgs_by_day=msgs_by_day,
        msgs_by_hour=msgs_by_hour,
        msgs_by_day_hour=msgs_by_day_hour,
        tokens_by_day=tokens_by_day,
        output_by_day=output_by_day,
        cache_read=cache_read,
        cache_create=cache_create,
        cache_read_by_day=cache_read_by_day,
        cache_create_by_day=cache_create_by_day,
        models=model_counts,
        projects=projects,
    )


def _fmt_model(m: str) -> str:
    m2 = m.lower().removeprefix("claude-")
    m2 = re.sub(r"-\d{8,}$", "", m2)
    parts = m2.split("-")
    if len(parts) >= 3:
        return f"{parts[0].capitalize()} {parts[1]}.{parts[2]}"
    if len(parts) == 2:
        return f"{parts[0].capitalize()} {parts[1]}"
    return m2.capitalize()


def _fmt_tok(n: int) -> str:
    if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
    if n >= 1_000:     return f"{n/1_000:.1f}K"
    return str(n)


def _compute_streaks(active_days):
    if not active_days:
        return 0, 0
    _sd = sorted(active_days)
    _max_s = _cur_s = 1
    for _i in range(1, len(_sd)):
        if (_sd[_i] - _sd[_i - 1]).days == 1:
            _cur_s += 1
            _max_s = max(_max_s, _cur_s)
        else:
            _cur_s = 1
    _today2 = date.today()
    _streak = 0
    _start = _today2 if _today2 in active_days else (
        _today2 - timedelta(days=1) if (_today2 - timedelta(days=1)) in active_days else None
    )
    if _start:
        _dd = _start
        while _dd in active_days:
            _streak += 1
            _dd -= timedelta(days=1)
    return _streak, _max_s


def _fun_tagline(total_tokens: int) -> str:
    _refs = [
        (95_000,  "The Hobbit"),
        (100_000, "Harry Potter and the Philosopher's Stone"),
        (120_000, "1984 by Orwell"),
        (163_000, "Pride and Prejudice"),
        (775_000, "War and Peace"),
    ]
    for _tok, _name in _refs:
        if total_tokens >= _tok * 1.5:
            _ratio = round(total_tokens / _tok)
            return f'You used ~{_ratio}&times; more tokens than <em>{_name}</em>.'
    if total_tokens >= 50_000:
        return 'You have accumulated enough tokens to write a novel.'
    return f'You have accumulated {_fmt_tok(total_tokens)} tokens so far.'


# ── Report dialog ─────────────────────────────────────────────────────────────

@st.dialog("Generate period report", width="large")
def _report_dialog():
    today = date.today()
    preset = st.selectbox("Period", [
        "Last 7 days", "Last 30 days", "Current week",
        "Current month", "Current year", "Custom",
    ])
    if preset == "Last 7 days":
        start, end = today - timedelta(days=7), today
    elif preset == "Last 30 days":
        start, end = today - timedelta(days=30), today
    elif preset == "Current week":
        start = today - timedelta(days=today.weekday()); end = today
    elif preset == "Current month":
        start = today.replace(day=1); end = today
    elif preset == "Current year":
        start = today.replace(month=1, day=1); end = today
    else:
        col_s, col_e = st.columns(2)
        start = col_s.date_input("From", value=today - timedelta(days=30), format="DD/MM/YYYY")
        end   = col_e.date_input("To",   value=today,                      format="DD/MM/YYYY")

    if st.button("Generate report", type="primary"):
        log_dir = VAULT_ROOT / "Log"
        entries = {"CRIADA": [], "ALTERADA": [], "CONCLUÍDA": [], "TO-DO": []}
        current = start
        while current <= end:
            log_file = log_dir / f"diario-{current.isoformat()}.md"
            if log_file.exists():
                for line in log_file.read_text(encoding="utf-8").splitlines():
                    for label in entries:
                        if f"`{label}`" in line:
                            entries[label].append(line.strip())
            current += timedelta(days=1)

        total_events = sum(len(v) for v in entries.values())
        period_str   = f"{start.strftime('%d/%m/%Y')} to {end.strftime('%d/%m/%Y')}"
        report_md    = f"# Report — {period_str}\n\n"
        report_md   += f"**Period:** {period_str}  \n**Total events:** {total_events}\n\n"
        report_md   += "| Type | Count |\n|---|---|\n"
        for label, items in entries.items():
            report_md += f"| {label} | {len(items)} |\n"
        for label, items in entries.items():
            if items:
                report_md += f"\n## {label} ({len(items)})\n"
                for item in items:
                    report_md += f"{item}\n"

        st.markdown(report_md)
        st.divider()
        col_save, _ = st.columns([2, 3])
        with col_save:
            if st.button("💾 Save to vault"):
                fname = f"report-{start.isoformat()}-{end.isoformat()}.md"
                out   = log_dir / fname
                fm    = f"---\ndate: {today.isoformat()}\ntype: report\nperiodo: {period_str}\ntags: [report, backlog]\n---\n\n"
                out.write_text(fm + report_md, encoding="utf-8")
                st.success(f"Saved to Log/{fname}")


# ── Main render ───────────────────────────────────────────────────────────────

def render() -> None:
    dark_mode = st.query_params.get("dark", "1") == "1"
    page      = st.query_params.get("page", "Dashboard")

    st.markdown('<h1 style="margin-bottom:0.4rem">Dashboard</h1>', unsafe_allow_html=True)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # SECTION 1 — Claude Code Activity
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    st.subheader("Claude Code Activity")
    st.caption("Real activity from session files `~/.claude/projects/`")

    if "cc_window" not in st.session_state:
        st.session_state["cc_window"] = 0

    _all_stats = _load_full_cc_stats()

    _w = st.session_state.get("cc_window", 0)
    _pc1, _pc2, _pc3, _pc4 = st.columns([6, 1, 1, 1])
    with _pc2:
        if st.button("All", type="primary" if _w == 0 else "secondary",
                     use_container_width=True, key="cc_all"):
            st.session_state["cc_window"] = 0; st.rerun()
    with _pc3:
        if st.button("30d", type="primary" if _w == 30 else "secondary",
                     use_container_width=True, key="cc_30d"):
            st.session_state["cc_window"] = 30; st.rerun()
    with _pc4:
        if st.button("7d", type="primary" if _w == 7 else "secondary",
                     use_container_width=True, key="cc_7d"):
            st.session_state["cc_window"] = 7; st.rerun()

    if _w > 0:
        _cutoff_disp = date.today() - timedelta(days=_w - 1)
        _msgs_by_day = {d: c for d, c in _all_stats["msgs_by_day"].items()   if d >= _cutoff_disp}
        _tk_total    = {d: c for d, c in _all_stats["tokens_by_day"].items() if d >= _cutoff_disp}
        _tk_out      = {d: c for d, c in _all_stats["output_by_day"].items() if d >= _cutoff_disp}
        _cr_total    = sum(v for d, v in _all_stats["cache_read_by_day"].items()   if d >= _cutoff_disp)
        _cc_total    = sum(v for d, v in _all_stats["cache_create_by_day"].items() if d >= _cutoff_disp)
        _peak_hours  = Counter()
        for _d2, _hc in _all_stats["msgs_by_day_hour"].items():
            if _d2 >= _cutoff_disp:
                _peak_hours += _hc
    else:
        _msgs_by_day = dict(_all_stats["msgs_by_day"])
        _tk_total    = dict(_all_stats["tokens_by_day"])
        _tk_out      = dict(_all_stats["output_by_day"])
        _cr_total    = _all_stats["cache_read"]
        _cc_total    = _all_stats["cache_create"]
        _peak_hours  = _all_stats["msgs_by_hour"]
    _cc_projects = _all_stats["projects"]

    if not _all_stats["msgs_by_day"] and not _all_stats["tokens_by_day"]:
        st.info("No data found in `~/.claude/`.")
    else:
        _total_msgs    = sum(_msgs_by_day.values())
        _total_tk_val  = sum(_tk_total.values())
        _active_days   = set(_msgs_by_day.keys())
        _streak_cur, _streak_max = _compute_streaks(_active_days)
        _peak_h        = max(_peak_hours, key=_peak_hours.get) if _peak_hours else 0
        _fav_mod       = max(_all_stats["models"], key=_all_stats["models"].get) if _all_stats["models"] else ""
        _fav_mod_str   = _fmt_model(_fav_mod) if _fav_mod else "—"
        _total_out     = sum(_tk_out.values())
        _cache_pct     = round(_cr_total / (_cr_total + _cc_total) * 100) if (_cr_total + _cc_total) > 0 else 0
        _num_projects  = len(_cc_projects)

        _sg_html = (
            '<style>'
            '.cc-sg{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin:.5rem 0}'
            '.cc-sc{background:#F9FAFB;border:1px solid #E5E7EB;border-radius:8px;padding:8px 12px}'
            '.cc-sl{font-size:.7rem;color:#6B7280;font-weight:500;margin-bottom:2px;white-space:nowrap}'
            '.cc-sv{font-size:1.2rem;font-weight:700;color:#111827;line-height:1.2}'
            '</style>'
            '<div class="cc-sg">'
            f'<div class="cc-sc"><div class="cc-sl">Sessions</div><div class="cc-sv">{_all_stats["sessions"]}</div></div>'
            f'<div class="cc-sc"><div class="cc-sl">Messages</div><div class="cc-sv">{_total_msgs:,}</div></div>'
            f'<div class="cc-sc"><div class="cc-sl">Active days</div><div class="cc-sv">{len(_active_days)}</div></div>'
            f'<div class="cc-sc"><div class="cc-sl">Peak hour</div><div class="cc-sv">{_peak_h:02d}h</div></div>'
            f'<div class="cc-sc"><div class="cc-sl">Total de tokens</div><div class="cc-sv">{_fmt_tok(_total_tk_val)}</div></div>'
            f'<div class="cc-sc"><div class="cc-sl">Output gerado</div><div class="cc-sv">{_fmt_tok(_total_out)}</div></div>'
            f'<div class="cc-sc"><div class="cc-sl">Cache hits</div><div class="cc-sv">{_fmt_tok(_cr_total)}</div></div>'
            f'<div class="cc-sc"><div class="cc-sl">Cache efficiency</div><div class="cc-sv">{_cache_pct}%</div></div>'
            f'<div class="cc-sc"><div class="cc-sl">Current streak</div><div class="cc-sv">{_streak_cur}d</div></div>'
            f'<div class="cc-sc"><div class="cc-sl">Longest streak</div><div class="cc-sv">{_streak_max}d</div></div>'
            f'<div class="cc-sc"><div class="cc-sl">Modelo favorito</div><div class="cc-sv" style="font-size:.9rem">{_fav_mod_str}</div></div>'
            f'<div class="cc-sc"><div class="cc-sl">Projects</div><div class="cc-sv">{_num_projects}</div></div>'
            '</div>'
        )
        st.markdown(_sg_html, unsafe_allow_html=True)

        # ── Contribution heatmap ──────────────────────────────────────────────
        _today_d  = date.today()
        _hm_start = _today_d - timedelta(days=364)
        _hm_start = _hm_start - timedelta(days=_hm_start.weekday())

        def _hm_clr(n):
            if n == 0:  return "#1A2030" if dark_mode else "#E9ECEF"
            if n <= 2:  return "#064E3B" if dark_mode else "#A7F3D0"
            if n <= 6:  return "#065F46" if dark_mode else "#34D399"
            if n <= 14: return "#047857" if dark_mode else "#059669"
            return "#02B793"

        _hm_weeks = []
        _cur = _hm_start
        while _cur <= _today_d:
            _wk = []
            for _dow in range(7):
                _d2 = _cur + timedelta(days=_dow)
                _n2 = _all_stats["msgs_by_day"].get(_d2, 0) if _d2 <= _today_d else 0
                _wk.append((_d2 if _d2 <= _today_d else None, _n2))
            _hm_weeks.append(_wk)
            _cur += timedelta(days=7)

        _mo_labels = [""] * len(_hm_weeks)
        _last_mo = -1
        for _wi2, _wk2 in enumerate(_hm_weeks):
            for _d3, _ in _wk2:
                if _d3 and _d3.month != _last_mo:
                    _mo_labels[_wi2] = _d3.strftime("%b")
                    _last_mo = _d3.month
                    break

        _mo_html   = "".join(f'<div style="min-width:12px;font-size:9px;color:#9CA3AF;text-align:left">{m}</div>' for m in _mo_labels)
        _dow_html  = "".join(f'<div style="height:12px;font-size:9px;color:#9CA3AF;line-height:12px">{lb}</div>' for lb in ["Mon", "", "Wed", "", "Fri", "", ""])
        _cells_html = ""
        for _wk3 in _hm_weeks:
            _cells_html += '<div style="display:flex;flex-direction:column;gap:1px">'
            for _d4, _n4 in _wk3:
                if _d4 is None:
                    _cells_html += '<div style="width:11px;height:11px"></div>'
                else:
                    _border = "2px solid #047857" if _d4 == _today_d else "none"
                    _tip    = f"{_d4.strftime('%d/%b')}: {_n4} msg"
                    _cells_html += (f'<div title="{_tip}" style="width:11px;height:11px;border-radius:2px;'
                                    f'background:{_hm_clr(_n4)};border:{_border}"></div>')
            _cells_html += "</div>"

        st.markdown(
            '<div style="margin:.75rem 0 .25rem;overflow-x:auto">'
            f'<div style="display:flex;gap:1px;margin-left:26px;margin-bottom:2px">{_mo_html}</div>'
            '<div style="display:flex;gap:3px">'
            f'<div style="display:flex;flex-direction:column;gap:1px;padding-right:2px">{_dow_html}</div>'
            f'<div style="display:flex;gap:1px">{_cells_html}</div>'
            '</div></div>',
            unsafe_allow_html=True,
        )

        # ── Meta / tagline ────────────────────────────────────────────────────
        _total_all_tk = sum(_all_stats["tokens_by_day"].values())
        _meta_parts = []
        if _total_all_tk > 0:
            _meta_parts.append(f"<em>{_fun_tagline(_total_all_tk)}</em>")
        if _cc_projects:
            _proj_str = "  ·  ".join(f"<b>{n}</b> {c}" for n, c in sorted(_cc_projects.items(), key=lambda x: -x[1])[:4])
            _meta_parts.append(f"Projects: {_proj_str}")
        if _meta_parts:
            st.markdown(f'<p style="font-size:.75rem;color:#9CA3AF;margin:.1rem 0 .8rem">{"  ·  ".join(_meta_parts)}</p>', unsafe_allow_html=True)

        # ── Diagnostic ────────────────────────────────────────────────────────
        _last14_msgs      = sum(_all_stats["msgs_by_day"].get(date.today() - timedelta(days=i), 0) for i in range(14))
        _avg_day          = _last14_msgs / 14
        _total_tk_sum     = sum(_all_stats["tokens_by_day"].values())
        _total_msgs_all   = sum(_all_stats["msgs_by_day"].values())
        _avg_tk_per_prompt = (_total_tk_sum / _total_msgs_all) if _total_msgs_all > 0 else 0
        _cache_pct_diag   = round(_cr_total / (_cr_total + _cc_total) * 100) if (_cr_total + _cc_total) > 0 else 0

        _issues: list[tuple[str, str]] = []
        _opps:   list[tuple[str, str]] = []

        if _avg_day < 5:
            _issues.append((
                f"**Very low frequency** — {_avg_day:.1f} prompts/day on average. "
                "Claude Code is not yet integrated into the daily workflow.",
                "Bring smaller tasks: email reviews, drafts, quick data analysis, script generation. "
                "The habit forms through daily use, not just large projects.",
            ))
        elif _avg_day < 10:
            _issues.append((
                f"**Frequency below potential** — {_avg_day:.1f} prompts/day. "
                "There is room to expand usage to more types of tasks.",
                "Identify recurring tasks you still do manually and try delegating them to Claude.",
            ))

        if _avg_tk_per_prompt > 0 and _avg_tk_per_prompt < 3_000:
            _issues.append((
                f"**Underused context** — average {_avg_tk_per_prompt/1000:.1f}K tokens/prompt. "
                "Very short sessions make poor use of the 200K context available.",
                "Include the full file, not just the snippet. Describe the project, give examples. "
                "Claude responds proportionally to the context it receives.",
            ))

        if _cache_pct_diag < 30 and (_cr_total + _cc_total) > 10_000:
            _issues.append((
                f"**Underused cache** — {_cache_pct_diag}% efficiency. "
                "Few sessions reuse context from previous sessions.",
                "Open longer sessions instead of many short ones on the same topic. "
                "Use /clear only when switching subjects, not between related subtasks.",
            ))

        if _avg_day >= 5 and _avg_tk_per_prompt >= 10_000:
            _opps.append((
                "Deep session pattern",
                f"User makes {_avg_day:.1f} prompts/day with an average of {_avg_tk_per_prompt/1000:.0f}K tokens each. "
                "Identify where longer sessions would add even more value vs. where current depth is sufficient.",
            ))
        if _cache_pct_diag >= 60:
            _opps.append(("High context reuse", f"Cache efficiency at {_cache_pct_diag}%. Suggest how to structure recurring projects to further maximize this pattern."))
        if len(_cc_projects) >= 3:
            _top_proj = ", ".join(n for n, _ in sorted(_cc_projects.items(), key=lambda x: -x[1])[:3])
            _opps.append(("Multi-project", f"Usage distributed across {len(_cc_projects)} projects ({_top_proj}). Identify whether centralizing context across projects makes sense or if separate is better."))

        _ni, _no = len(_issues), len(_opps)
        _s_color = "#EF4444" if _ni else "#059669"
        _s_icon  = "⚠" if _ni else "✓"
        _s_label = f"{_ni} {'issue' if _ni == 1 else 'issues'}" if _ni else "No issues"
        _o_label = f"{_no} {'opportunity' if _no == 1 else 'opportunities'}"
        st.markdown(
            f'<p style="font-size:.78rem;margin:.4rem 0 .3rem">'
            f'<span style="color:{_s_color}">{_s_icon} {_s_label}</span>'
            f'<span style="color:#9CA3AF">  ·  {_o_label}</span></p>',
            unsafe_allow_html=True,
        )

        if _issues or _opps:
            with st.expander("Details", expanded=False):
                for _err, _fix in _issues:
                    st.markdown(f'<div style="margin:.4rem 0;padding:.5rem .75rem;border-radius:6px;border-left:3px solid #EF4444;background:rgba(239,68,68,.05)"><span style="font-size:.7rem;color:#EF4444;font-weight:700;text-transform:uppercase;letter-spacing:.04em">Issue</span><br>{_err}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div style="margin:-.2rem 0 .5rem;padding:.5rem .75rem;border-radius:6px;border-left:3px solid #059669;background:rgba(5,150,105,.05)"><span style="font-size:.7rem;color:#059669;font-weight:700;text-transform:uppercase;letter-spacing:.04em">How to fix</span><br>{_fix}</div>', unsafe_allow_html=True)
                if _opps:
                    _opp_title_clr  = "#E2E8F0" if dark_mode else "#111827"
                    _opp_detail_clr = "#94A3B8" if dark_mode else "#6B7280"
                    for _opp_title, _opp_detail in _opps:
                        st.markdown(f'<div style="margin:.4rem 0;padding:.5rem .75rem;border-radius:6px;border-left:3px solid #6366F1;background:rgba(99,102,241,.05)"><span style="font-size:.7rem;color:#6366F1;font-weight:700;text-transform:uppercase;letter-spacing:.04em">Opportunity</span><br><b style="color:{_opp_title_clr}">{_opp_title}</b>  <span style="font-size:.85rem;color:{_opp_detail_clr}">{_opp_detail}</span></div>', unsafe_allow_html=True)
                    _opp_ctx_prompt = "\n".join(f"- {t}: {d}" for t, d in _opps)
                    _metrics_summary = (
                        f"Prompts/day (14d): {_avg_day:.1f} | "
                        f"Tokens/prompt: {_avg_tk_per_prompt/1000:.1f}K | "
                        f"Cache: {_cache_pct_diag}% | "
                        f"Projects: {', '.join(list(_cc_projects.keys())[:3])}"
                    )
                    if st.button("Run Ollama analysis", key="cc_ollama_btn", type="primary"):
                        _prompt = (
                            "You are an AI productivity consultant. "
                            "Analyze the Claude Code usage pattern below and provide actionable insights.\n\n"
                            f"Real metrics (last 14 days):\n{_metrics_summary}\n\n"
                            f"Identified opportunities:\n{_opp_ctx_prompt}\n\n"
                            "For each opportunity: explain when to use Claude in that context and when NOT to. "
                            "Be specific and practical. Maximum 200 words total. Respond in English."
                        )
                        try:
                            from openai import OpenAI as _OAI
                            _client = _OAI(base_url=OLLAMA_BASE_URL, api_key="ollama")
                            with st.spinner("Ollama analyzing..."):
                                _resp = _client.chat.completions.create(
                                    model=EXTRACTION_MODEL,
                                    messages=[{"role": "user", "content": _prompt}],
                                    temperature=0.4,
                                    max_tokens=350,
                                )
                            st.markdown(_resp.choices[0].message.content)
                        except Exception:
                            st.warning(f"Ollama not available (`{OLLAMA_BASE_URL}`). Start the service with `ollama serve` to use this analysis.")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # SECTION 2 — Backlog summary
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    st.divider()
    ideas_all = load_ideas()
    todos_all = [t for idea in ideas_all for t in idea.todos]

    total       = len(ideas_all)
    active      = sum(1 for i in ideas_all if i.status not in ("concluído", "descartado"))
    concluidas  = sum(1 for i in ideas_all if i.status == "concluído")
    todos_done  = sum(1 for t in todos_all if t["done"])
    todos_pending = sum(1 for t in todos_all if not t["done"])
    bugs_open   = sum(1 for t in todos_all if t.get("is_bug") and not t["done"])

    st.markdown(
        '<style>'
        '.cc-sg{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin:.5rem 0}'
        '.cc-sc{background:#F9FAFB;border:1px solid #E5E7EB;border-radius:8px;padding:8px 12px}'
        '.cc-sl{font-size:.7rem;color:#6B7280;font-weight:500;margin-bottom:2px;white-space:nowrap}'
        '.cc-sv{font-size:1.2rem;font-weight:700;color:#111827;line-height:1.2}'
        '</style>'
        '<div class="cc-sg" style="grid-template-columns:repeat(6,1fr)">'
        f'<div class="cc-sc"><div class="cc-sl">Total ideas</div><div class="cc-sv">{total}</div></div>'
        f'<div class="cc-sc"><div class="cc-sl">Active</div><div class="cc-sv">{active}</div></div>'
        f'<div class="cc-sc"><div class="cc-sl">Done</div><div class="cc-sv">{concluidas}</div></div>'
        f'<div class="cc-sc"><div class="cc-sl">Open to-dos</div><div class="cc-sv">{todos_pending}</div></div>'
        f'<div class="cc-sc"><div class="cc-sl">Completed to-dos</div><div class="cc-sv">{todos_done}</div></div>'
        f'<div class="cc-sc"><div class="cc-sl">Open bugs</div><div class="cc-sv" style="color:{"#EF4444" if bugs_open else "#111827"}">{bugs_open}</div></div>'
        '</div>',
        unsafe_allow_html=True,
    )

    st.divider()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # SECTION 3 — Deadline Calendar
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    if "cal_year"  not in st.session_state: st.session_state.cal_year  = date.today().year
    if "cal_month" not in st.session_state: st.session_state.cal_month = date.today().month

    _cal_today = date.today()
    _cy = st.session_state.cal_year
    _cm = st.session_state.cal_month

    st.subheader("Deadline Calendar")

    _cc1, _cc2, _cc3, _cc4, _cc5 = st.columns([1, 2, 1, 1, 5])
    _MONTHS_EN = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    with _cc1:
        if st.button("◀", key="cal_prev", use_container_width=True):
            if _cm == 1: st.session_state.cal_month = 12; st.session_state.cal_year -= 1
            else:        st.session_state.cal_month -= 1
            st.rerun()
    with _cc2:
        st.markdown(f"<p style='text-align:center;font-weight:600;padding:.35rem 0;margin:0'>{_MONTHS_EN[_cm-1]} {_cy}</p>", unsafe_allow_html=True)
    with _cc3:
        if st.button("▶", key="cal_next", use_container_width=True):
            if _cm == 12: st.session_state.cal_month = 1; st.session_state.cal_year += 1
            else:         st.session_state.cal_month += 1
            st.rerun()
    with _cc5:
        _cal_mode_qs = st.query_params.get("cal_mode", "ideas")
        _dot_on  = "●"; _dot_off = "○"
        _clr_on  = "#02B793"; _clr_off = "#94A3B8" if dark_mode else "#9CA3AF"
        _lbl_clr = "#E2E8F0" if dark_mode else "#374151"
        _cal_legs = ""
        for _lbl, _val in [("Backlog items", "ideas"), ("To-dos", "todos")]:
            _sel = _cal_mode_qs == _val
            _d   = _dot_on if _sel else _dot_off
            _dc  = _clr_on if _sel else _clr_off
            _cal_legs += (
                f'<form method="get" action="" style="display:inline-flex;align-items:center;gap:4px;margin:0 8px 0 0;padding:0">'
                f'<input type="hidden" name="page" value="{page}">'
                f'<input type="hidden" name="dark" value="{"1" if dark_mode else "0"}">'
                f'<input type="hidden" name="cal_mode" value="{_val}">'
                f'<button type="submit" style="background:none;border:none;cursor:pointer;padding:0;display:inline-flex;align-items:center;gap:5px">'
                f'<span style="color:{_dc};font-size:1rem">{_d}</span>'
                f'<span style="color:{_lbl_clr};font-size:0.82rem">{_lbl}</span>'
                f'</button></form>'
            )
        st.markdown(f'<div style="display:flex;align-items:center;height:100%;padding-top:6px">{_cal_legs}</div>', unsafe_allow_html=True)
    _cal_mode = _cal_mode_qs if _cal_mode_qs in ("ideas", "todos") else "ideas"

    _CLOSED_CAL = {"concluído", "descartado", "análise - rejeitado"}
    _PRIO_ICON  = {"alta": "⭐", "média": "·", "baixa": "·"}
    _cal_map: dict = {}

    if _cal_mode == "ideas":
        for _ci in ideas_all:
            if _ci.due_date and _ci.status not in _CLOSED_CAL:
                _cal_map.setdefault(_ci.due_date, []).append(_ci)
    else:
        for _ci in ideas_all:
            for _ct in _ci.todos:
                if not _ct.get("done") and _ct.get("due_date"):
                    try:
                        _ctd = date.fromisoformat(_ct["due_date"])
                        _cal_map.setdefault(_ctd, []).append({"idea": _ci, "todo": _ct})
                    except (ValueError, TypeError):
                        pass

    def _chip_cls(d):
        if d < _cal_today:             return "cal-overdue"
        if d == _cal_today:            return "cal-today"
        if (d - _cal_today).days <= 7: return "cal-soon"
        return "cal-future"

    _DOW   = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    _weeks = _cal_mod.Calendar(firstweekday=6).monthdatescalendar(_cy, _cm)
    _month_items = {d: v for d, v in _cal_map.items() if d.month == _cm and d.year == _cy}

    if dark_mode:
        _c_border = "#1F2937"; _c_td_bg = "#0E1117"; _c_out_bg = "#060810"
        _c_out_dnum = "#1E293B"; _c_in_dnum = "#64748B"
        _c_th_border = "#2D3748"; _c_th_color = "#475569"
        _c_fut_bg = "#1A1D2E"; _c_fut_bc = "#2D3748"; _c_fut_clr = "#64748B"
        _c_more_clr = "#475569"
    else:
        _c_border = "#F3F4F6"; _c_td_bg = "transparent"; _c_out_bg = "#F1F5F9"
        _c_out_dnum = "#D1D5DB"; _c_in_dnum = "#9CA3AF"
        _c_th_border = "#E5E7EB"; _c_th_color = "#9CA3AF"
        _c_fut_bg = "#F9FAFB"; _c_fut_bc = "#E5E7EB"; _c_fut_clr = "#6B7280"
        _c_more_clr = "#9CA3AF"

    _cal_css = (
        "<style>"
        ".cal-wrap{overflow-x:auto;margin-top:.5rem}"
        ".cal-tbl{width:100%;border-collapse:collapse;table-layout:fixed}"
        f".cal-th{{font-family:'DM Mono',monospace;font-size:.65rem;font-weight:500;letter-spacing:.08em;text-transform:uppercase;color:{_c_th_color};text-align:center;padding:6px 2px;border-bottom:1px solid {_c_th_border}}}"
        f".cal-td{{vertical-align:top;border:1px solid {_c_border}!important;background:{_c_td_bg}!important;padding:4px;min-height:72px;width:14.28%}}"
        f".cal-td-out{{background:{_c_out_bg}!important;opacity:{'0.5' if dark_mode else '1'}}}"
        f".cal-td-out .cal-dnum{{color:{_c_out_dnum}!important}}"
        f".cal-td:not(.cal-td-out) .cal-dnum{{color:{_c_in_dnum}!important}}"
        f".cal-dnum{{font-size:.7rem;color:{_c_in_dnum};margin-bottom:3px;display:block}}"
        ".cal-dnum-cur{font-size:.7rem;color:#02B793;font-weight:700;margin-bottom:3px;display:block}"
        ".cal-chip{display:block;font-size:.65rem;border-radius:3px;padding:2px 5px;margin-bottom:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;border-left:2px solid;line-height:1.4}"
        + (".cal-td-today{background:rgba(2,183,147,.06)!important;border-color:#02B793}"
           ".cal-overdue{background:rgba(239,68,68,.12);border-color:#EF4444;color:#EF4444}"
           ".cal-today{background:rgba(245,158,11,.12);border-color:#F59E0B;color:#F59E0B}"
           ".cal-soon{background:rgba(2,183,147,.1);border-color:#02B793;color:#02B793}"
           if dark_mode else
           ".cal-td-today{background:rgba(2,183,147,.04)!important;border-color:#02B793}"
           ".cal-overdue{background:#FEE2E2;border-color:#EF4444;color:#EF4444}"
           ".cal-today{background:#FEF3C7;border-color:#F59E0B;color:#D97706}"
           ".cal-soon{background:rgba(2,183,147,.08);border-color:#02B793;color:#007167}"
        ) +
        f".cal-future{{background:{_c_fut_bg};border-color:{_c_fut_bc};color:{_c_fut_clr}}}"
        f".cal-more{{font-size:.6rem;color:{_c_more_clr};display:block;padding-left:5px}}"
        "</style>"
    )
    _th_row   = "<thead><tr>" + "".join(f'<th class="cal-th">{d}</th>' for d in _DOW) + "</tr></thead>"
    _body_rows = []
    for _week in _weeks:
        _cells = []
        for _day in _week:
            _is_cur   = (_day.month == _cm)
            _is_today = (_day == _cal_today)
            _td_cls   = "cal-td" + (" cal-td-out" if not _is_cur else "") + (" cal-td-today" if _is_today else "")
            _dn_cls   = "cal-dnum-cur" if _is_today else "cal-dnum"
            _cell     = [f'<td class="{_td_cls}"><span class="{_dn_cls}">{_day.day}</span>']
            if _is_cur:
                _day_items = _cal_map.get(_day, [])
                _cc_cls    = _chip_cls(_day)
                for _it in _day_items[:3]:
                    if _cal_mode == "ideas":
                        _icon = _PRIO_ICON.get(_it.priority, "·")
                        _lbl  = f"{_icon} {_it.id} · {_it.title[:20]}{'…' if len(_it.title) > 20 else ''}"
                    else:
                        _ttxt = _it["todo"]["text"]
                        _lbl  = f"{_ttxt[:22]}{'…' if len(_ttxt) > 22 else ''} · {_it['idea'].id}"
                    _safe = _lbl.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
                    _cell.append(f'<span class="cal-chip {_cc_cls}" title="{_safe}">{_safe}</span>')
                if len(_day_items) > 3:
                    _cell.append(f'<span class="cal-more">+{len(_day_items) - 3} more</span>')
            _cell.append("</td>")
            _cells.append("".join(_cell))
        _body_rows.append("<tr>" + "".join(_cells) + "</tr>")

    if not _month_items:
        st.caption(f"No deadlines scheduled for {_MONTHS_EN[_cm-1]} {_cy}.")
    else:
        st.markdown(
            _cal_css + '<div class="cal-wrap"><table class="cal-tbl">' + _th_row
            + "<tbody>" + "".join(_body_rows) + "</tbody></table></div>",
            unsafe_allow_html=True,
        )

    st.divider()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # SECTION 4 — Detailed analysis
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    with st.expander("Detailed analysis · Report", expanded=False):
        _today_d = date.today()
        _week_end = _today_d + timedelta(days=7)
        _due_soon: list[tuple] = []
        for _t in todos_all:
            if _t["done"]:
                continue
            _td = _t.get("due_date")
            if _td:
                try:
                    _d = date.fromisoformat(str(_td)) if not isinstance(_td, date) else _td
                    if _d <= _week_end:
                        _due_soon.append((_d, _t))
                except Exception:
                    pass
        _due_soon.sort(key=lambda x: x[0])

        _bar_track = "#1E293B" if dark_mode else "#E5E7EB"
        _txt_clr   = "#CBD5E0" if dark_mode else "#374151"
        def _bar(pct: float) -> str:
            return (
                f'<div style="height:6px;background:{_bar_track};border-radius:999px;margin:3px 0 10px">'
                f'<div style="width:{max(2, int(pct*100))}%;height:100%;'
                f'background:linear-gradient(90deg,#02B793,#0AD4A8);border-radius:999px"></div></div>'
            )

        col_left, col_right, col_due = st.columns(3)

        with col_left:
            st.subheader("By status")
            status_counts = {}
            for i in ideas_all:
                status_counts[i.status] = status_counts.get(i.status, 0) + 1
            for status in VALID_STATUSES:
                count = status_counts.get(status, 0)
                if count:
                    icon = STATUS_COLOR.get(status, sdot("backlog"))
                    pct  = count / total if total else 0
                    st.markdown(f'<div style="color:{_txt_clr}">{icon} <b>{STATUS_LABEL.get(status, status)}</b> — {count}</div>' + _bar(pct), unsafe_allow_html=True)

        with col_right:
            st.subheader("By priority")
            prio_counts = {}
            for i in ideas_all:
                prio_counts[i.priority] = prio_counts.get(i.priority, 0) + 1
            for p in VALID_PRIORITIES:
                count = prio_counts.get(p, 0)
                badge = PRIORITY_NUM.get(p, "")
                pct   = count / total if total else 0
                st.markdown(f'<div style="color:{_txt_clr}">{badge} <b>{PRIORITY_LABEL.get(p, p)}</b> — {count}</div>' + _bar(pct), unsafe_allow_html=True)

        with col_due:
            st.subheader("Due this week")
            if not _due_soon:
                st.caption("No to-dos due today or this week.")
            else:
                for _d, _t in _due_soon:
                    _is_overdue = _d < _today_d
                    _date_str   = "Hoje" if _d == _today_d else _d.strftime("%d/%m")
                    _clr        = "#EF4444" if _is_overdue else ("#F59E0B" if _d == _today_d else "#6B7280")
                    _bug_b      = (' <span style="background:#FEE2E2;color:#B91C1C;font-size:8px;font-weight:700;padding:1px 4px;border-radius:3px">BUG</span>' if _t.get("is_bug") else "")
                    _border_clr = "rgba(255,255,255,0.07)" if dark_mode else "rgba(0,0,0,0.06)"
                    st.markdown(
                        f'<div style="padding:5px 0;border-bottom:1px solid {_border_clr}">'
                        f'<span style="font-size:0.7rem;font-weight:600;color:{_clr}">{_date_str}</span>'
                        f'&nbsp;<span style="font-size:0.81rem;color:{_txt_clr}">{_t["text"][:48]}</span>{_bug_b}'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

        st.divider()
        col_area, col_score = st.columns(2)

        with col_area:
            st.subheader("By area")
            area_counts = {}
            for i in ideas_all:
                area = i.area or "—"
                area_counts[area] = area_counts.get(area, 0) + 1
            for area, count in sorted(area_counts.items(), key=lambda x: -x[1]):
                pct = count / total if total else 0
                st.markdown(f'<div style="color:{_txt_clr}">🏷️ <b>{area}</b> — {count}</div>' + _bar(pct), unsafe_allow_html=True)

        with col_score:
            st.subheader("Scoring: Impact × Effort")
            scored = [i for i in ideas_all if i.impacto and i.esforco]
            if not scored:
                st.info("No ideas with impact and effort filled in yet.")
            else:
                impact_val = {"alta": 3, "média": 2, "baixa": 1}
                effort_val = {"baixo": 3, "médio": 2, "alto": 1}
                def _score(idea):
                    return impact_val.get(idea.impacto, 0) * effort_val.get(idea.esforco, 0)
                ranked = sorted(scored, key=_score, reverse=True)
                _h0, _h1, _h2 = st.columns([1, 5, 3])
                _h0.caption("Score"); _h1.caption("Idea"); _h2.caption("Impact · Effort")
                for idea in ranked[:8]:
                    s = _score(idea)
                    _clean_title = idea.title.replace("**", "").strip()
                    _c0, _c1, _c2 = st.columns([1, 5, 3])
                    _c0.markdown(f"**{s}**")
                    _c1.markdown(f"`{idea.id}` {_clean_title[:38]}")
                    _c2.caption(f"{IMPACT_LABEL.get(idea.impacto, idea.impacto)} · {EFFORT_LABEL.get(idea.esforco, idea.esforco)}")

        st.divider()
        st.subheader("Period report")
        if st.button("📋 Generate period report"):
            _report_dialog()
