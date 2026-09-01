"""views/english_coach.py — English Coach page."""

import re
from collections import Counter, defaultdict

import streamlit as st

from config import EC_DIR

# CEFR ladder, weakest first — used to name the next level and to consolidate
# a level out of the session history instead of trusting the last row.
_CEFR = ["A1", "A2", "B1", "B2", "C1", "C2"]

# How many recent rated sessions vote on the consolidated level. A single reading
# must not redefine the level, in either direction: on 2026-09-01 a third pass over
# an already-rated recording came back B2 against eight C1 readings, carrying the
# coach's own "low confidence" flag, and the page displayed it as the current level
# because it took the last row of progress.md. The window does not decide which
# reading is right — it stops one reading from deciding alone, and the disagreement
# is surfaced instead of being averaged away.
_LEVEL_WINDOW = 6


def _next_level(level: str) -> str | None:
    if level in _CEFR and level != _CEFR[-1]:
        return _CEFR[_CEFR.index(level) + 1]
    return None


def _parse_dims(scores_str: str) -> dict:
    """'Gramática: 7 | Vocabulário: 6 | …' → {'Gramática': 7.0, …}"""
    out = {}
    for part in scores_str.split(" | "):
        if ": " in part:
            name, val = part.rsplit(": ", 1)
            try:
                out[name.strip()] = float(val.strip())
            except ValueError:
                pass
    return out


def _error_categories(sessions_dir) -> Counter:
    """Count the bold category labels under '## Errors to Fix' across all sessions.

    The coach writes each error as '**Category** — _quoted span_', so the
    categories are countable without an LLM. This is the closest thing to an
    objective answer to "what keeps coming back".
    """
    cats: Counter = Counter()
    if not sessions_dir.exists():
        return cats
    for f in sorted(sessions_dir.glob("*_english-coach.md")):
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        block = re.search(r"## Errors to Fix\n(.*?)(?=\n## |\Z)", text, re.S)
        if not block:
            continue
        for m in re.finditer(r"^\*\*(.+?)\*\*\s+—", block.group(1), re.M):
            cats[m.group(1).strip()] += 1
    return cats


def _load_targets(ec_dir) -> dict:
    """The prescribe-then-verify ledger written by call-recorder/coach_targets.py.

    Read-only here. The page shows what was assigned and whether it is being
    used; nothing on this screen edits the ledger.
    """
    import json
    p = ec_dir / "targets.json"
    if not p.exists():
        return {"targets": []}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"targets": []}
    data.setdefault("targets", [])
    return data


def render() -> None:
    dark_mode    = st.query_params.get("dark", "1") == "1"
    _EC_DIR      = EC_DIR
    _EC_PROGRESS = _EC_DIR / "progress.md"
    _EC_SESSIONS = _EC_DIR / "sessions"

    st.markdown('<h1 style="margin-bottom:0.4rem">English Coach</h1>', unsafe_allow_html=True)
    st.caption("English practice session history · AI-rated")

    if not _EC_DIR.exists() or not _EC_PROGRESS.exists():
        st.info(
            "No sessions recorded yet. "
            "Run **english-coach.ps1** via Raycast (Win+Space → English Coach) to start your first session.",
            icon="🎙️",
        )
        return

    # ── Parse progress table ──────────────────────────────────────────────
    _prog_text = _EC_PROGRESS.read_text(encoding="utf-8")
    _prog_rows = []
    for _line in _prog_text.splitlines():
        if not _line.startswith("|"):
            continue
        _cols = [_c.strip() for _c in _line.strip("|").split("|")]
        if len(_cols) < 9:
            continue
        if not re.match(r"\d{4}-\d{2}-\d{2}", _cols[0]):
            continue
        _om = re.match(r"([\d.]+)/10", _cols[1])
        if not _om:
            continue
        _topic_raw    = _cols[8] if len(_cols) > 8 else ""
        _tt_m         = re.match(r"\[(\w+)\](.*)", _topic_raw)
        _topic_type_p = _tt_m.group(1).lower() if _tt_m else ""
        _topic_clean  = _tt_m.group(2).strip() if _tt_m else _topic_raw
        _scores_str   = " | ".join(_cols[3:8])
        _prog_rows.append({
            "date":       _cols[0],
            "overall":    float(_om.group(1)),
            "level":      _cols[2],
            "scores":     _scores_str,
            "topic":      _topic_clean,
            "topic_type": _topic_type_p,
        })

    # progress.md is append-ordered, not date-ordered (2026-08-27 sits above
    # 2026-08-26 today). Everything downstream assumes chronology, so sort here.
    _prog_rows.sort(key=lambda r: r["date"])

    if _prog_rows:
        _latest = _prog_rows[-1]
        _avg    = sum(r["overall"] for r in _prog_rows) / len(_prog_rows)
        _best   = max(r["overall"] for r in _prog_rows)

        # ── Consolidated level ────────────────────────────────────────────
        _window       = [r["level"] for r in _prog_rows[-_LEVEL_WINDOW:] if r["level"] in _CEFR]
        _level        = Counter(_window).most_common(1)[0][0] if _window else _latest["level"]
        _at_level     = sum(1 for r in _prog_rows if r["level"] == _level)
        _next_lvl     = _next_level(_level)
        _level_argues = _latest["level"] != _level

        _accent   = "#02B793"
        _fg_sub   = "#94A3B8" if dark_mode else "rgba(76,77,88,0.60)"
        _hero_bg  = "rgba(2,183,147,0.07)" if dark_mode else "rgba(2,183,147,0.04)"

        _next_html = (
            f'<div style="font-size:12px;color:{_fg_sub};margin-top:2px">'
            f'Next level: <strong>{_next_lvl}</strong></div>'
            if _next_lvl else ""
        )
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:26px;padding:18px 24px;'
            f'background:{_hero_bg};border-left:4px solid {_accent};border-radius:0 8px 8px 0;'
            f'margin-bottom:18px">'
            f'  <div style="line-height:1">'
            f'    <div style="font-family:\'DM Mono\',monospace;font-size:10px;font-weight:600;'
            f'letter-spacing:.14em;text-transform:uppercase;color:{_accent};margin-bottom:6px">'
            f'Current level</div>'
            f'    <div style="font-size:76px;font-weight:700;letter-spacing:-0.03em;'
            f'color:{_accent}">{_level}</div>'
            f'  </div>'
            f'  <div style="border-left:1px solid rgba(148,163,184,0.28);padding-left:24px">'
            f'    <div style="font-size:13px;color:{_fg_sub}">'
            f'Consolidated from <strong>{_at_level} of {len(_prog_rows)}</strong> rated sessions '
            f'— not from the last one alone.</div>'
            f'    {_next_html}'
            f'  </div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        if _level_argues:
            st.caption(
                f"⚠️ The most recent session ({_latest['date']}) came back **{_latest['level']}**, "
                f"against **{_level}** in the rest of the window. A single reading does not move "
                f"the level — check that session before treating it as a change."
            )

        # ── KPIs ─────────────────────────────────────────────────────────
        _k1, _k2, _k3, _k4 = st.columns(4)
        _k1.metric("Sessions", len(_prog_rows))
        _k2.metric("Latest score", f"{_latest['overall']:.1f}/10", help=f"Session of {_latest['date']}")
        _k3.metric("Overall average", f"{_avg:.1f}/10")
        _k4.metric("Best score", f"{_best:.1f}/10")

        # ── Topic type breakdown ──────────────────────────────────────────
        _typed_rows = [_r for _r in _prog_rows if _r.get("topic_type")]
        if _typed_rows:
            _type_data: dict = defaultdict(list)
            for _r in _typed_rows:
                _type_data[_r["topic_type"]].append(_r["overall"])
            st.markdown("**Sessions by type**")
            _tc_cols = st.columns(min(len(_type_data), 6))
            for _ti, (_tt, _tscores) in enumerate(sorted(_type_data.items())):
                _tavg = sum(_tscores) / len(_tscores)
                _tc_cols[_ti].metric(
                    _tt.title(),
                    f"{_tavg:.1f}/10",
                    help=f"{len(_tscores)} session(s)",
                )

        st.divider()

        # ── What's missing to level up ────────────────────────────────────
        _dim_avgs: dict = defaultdict(list)
        for _r in _prog_rows:
            for _dname, _dval in _parse_dims(_r["scores"]).items():
                _dim_avgs[_dname].append(_dval)
        _dim_mean = {k: sum(v) / len(v) for k, v in _dim_avgs.items() if v}

        if _dim_mean:
            _target_lbl = f"for {_next_lvl}" if _next_lvl else "to consolidate"
            st.subheader(f"What's missing {_target_lbl}")
            st.caption(
                "Consolidated across every rated session — the ceiling is set by the "
                "weakest dimensions, not by the average."
            )

            _ceiling = max(_dim_mean.values())
            _ranked  = sorted(_dim_mean.items(), key=lambda kv: kv[1])

            _th = ("padding:7px 12px;text-align:left;font-weight:500;font-size:12px;"
                   f"color:{_fg_sub};border-bottom:1px solid "
                   f"{'#2D3748' if dark_mode else 'rgba(76,77,88,0.18)'};white-space:nowrap")
            _td = ("padding:7px 12px;font-size:13px;border-bottom:1px solid "
                   f"{'rgba(45,55,72,0.5)' if dark_mode else 'rgba(76,77,88,0.07)'};"
                   "vertical-align:middle")

            _rows_html = ""
            for _dname, _dval in _ranked:
                _gap  = _ceiling - _dval
                _fill = int(round(_dval * 10))
                _bar  = (f'<div style="height:6px;width:120px;border-radius:3px;'
                         f'background:rgba(148,163,184,0.22);overflow:hidden">'
                         f'<div style="height:100%;width:{_fill}%;background:{_accent}"></div></div>')
                _gap_txt = "— your ceiling" if _gap < 0.05 else f"−{_gap:.1f} vs ceiling"
                _gap_col = _fg_sub if _gap < 0.05 else ("#F59E0B" if _gap < 0.7 else "#EF4444")
                _rows_html += (
                    f'<tr><td style="{_td};font-weight:500">{_dname}</td>'
                    f'<td style="{_td}">{_dval:.1f}</td>'
                    f'<td style="{_td}">{_bar}</td>'
                    f'<td style="{_td};color:{_gap_col};font-size:12px">{_gap_txt}</td></tr>'
                )
            st.markdown(
                f'<table style="width:100%;border-collapse:collapse;margin-bottom:14px">'
                f'<thead><tr>'
                f'<th style="{_th}">Dimension</th><th style="{_th}">Average</th>'
                f'<th style="{_th}"></th><th style="{_th}">Distance</th>'
                f'</tr></thead><tbody>{_rows_html}</tbody></table>',
                unsafe_allow_html=True,
            )

            _weak = [d for d, _ in _ranked[:2]]
            _top  = _ranked[-1][0]
            st.markdown(
                f"**Read:** {_top} is already carrying the level. What holds you at "
                f"**{_level}** is **{_weak[0]}** and **{_weak[1]}** — that is where the "
                f"next level is won, not in more practice hours."
            )

            # ── Targets: the "how", and whether it is happening ───────────────
            _tdata   = _load_targets(_EC_DIR)
            _active  = [t for t in _tdata["targets"] if t.get("status") == "active"]
            _done    = [t for t in _tdata["targets"] if t.get("status") == "achieved"]
            if _active or _done:
                st.markdown("**What to do about it**")
                st.caption(
                    "Assigned by the coach after a session, then checked against the "
                    "words you actually said in the next ones. Counting is a literal "
                    "match on your own lines — no model decides whether you used it."
                )
                _trows = ""
                for _t in sorted(_active, key=lambda x: -len(x.get("sessions", []))):
                    _need  = 2
                    _hits  = _t.get("streak", 0)
                    _label = (f"Use <strong>{_t['target']}</strong>" if _t["kind"] == "use"
                              else f"Stop saying <strong>{_t['target']}</strong>")
                    if _t.get("instead_of"):
                        _label += (f" <span style='color:{_fg_sub}'>"
                                   f"{'instead of' if _t['kind'] == 'use' else '→'} "
                                   f"{_t['instead_of']}</span>")
                    _pips = "".join(
                        f'<span style="display:inline-block;width:9px;height:9px;'
                        f'border-radius:50%;margin-right:4px;background:'
                        f'{_accent if i < _hits else "rgba(148,163,184,0.3)"}"></span>'
                        for i in range(_need)
                    )
                    _n_sessions = len(_t.get("sessions", []))
                    _note = (f'<span style="color:#EF4444">not moving after '
                             f'{_n_sessions} sessions</span>' if _t.get("stuck")
                             else f'<span style="color:{_fg_sub}">{_n_sessions} '
                                  f'session(s) checked</span>')
                    _trows += (f'<tr><td style="{_td}">{_label}</td>'
                               f'<td style="{_td};white-space:nowrap">{_pips}</td>'
                               f'<td style="{_td};font-size:12px">{_note}</td></tr>')
                if _trows:
                    st.markdown(
                        f'<table style="width:100%;border-collapse:collapse;'
                        f'margin-bottom:10px"><thead><tr>'
                        f'<th style="{_th}">Target</th>'
                        f'<th style="{_th}">Progress</th>'
                        f'<th style="{_th}"></th>'
                        f'</tr></thead><tbody>{_trows}</tbody></table>',
                        unsafe_allow_html=True,
                    )
                if _done:
                    st.caption("Retired (used consistently): "
                               + " · ".join(f"**{t['target']}**" for t in _done[-8:]))
            else:
                st.caption(
                    "No targets assigned yet — the coach starts one after the next "
                    "session it evaluates."
                )

            # Recurring error categories — countable, no LLM involved.
            _cats = _error_categories(_EC_SESSIONS)
            if _cats:
                st.markdown("**Recurring error types**")
                st.caption("Counted from the 'Errors to Fix' block of every session file.")
                _cat_html = ""
                _cat_max  = _cats.most_common(1)[0][1]
                for _cname, _ccount in _cats.most_common(6):
                    _cw = int(round(_ccount / _cat_max * 100))
                    _cat_html += (
                        f'<tr><td style="{_td};font-weight:500">{_cname}</td>'
                        f'<td style="{_td};width:100%">'
                        f'<div style="height:6px;width:{_cw}%;min-width:6px;border-radius:3px;'
                        f'background:{_accent};opacity:.75"></div></td>'
                        f'<td style="{_td};text-align:right;font-family:monospace;font-size:12px">'
                        f'{_ccount}×</td></tr>'
                    )
                st.markdown(
                    f'<table style="width:100%;border-collapse:collapse">'
                    f'<tbody>{_cat_html}</tbody></table>',
                    unsafe_allow_html=True,
                )

            st.divider()

        # ── Score trend chart ─────────────────────────────────────────────
        import altair as _alt
        import pandas as _pd

        _chart_src = _pd.DataFrame([{"date": r["date"], "score": r["overall"]} for r in _prog_rows])
        _overall_chart = (
            _alt.Chart(_chart_src)
            .mark_line(point=True, color="#3B82F6", strokeWidth=2)
            .encode(
                x=_alt.X("date:O", axis=_alt.Axis(labelAngle=-30, title=None)),
                y=_alt.Y("score:Q",
                          scale=_alt.Scale(domain=[0, 10]),
                          axis=_alt.Axis(title="Score (0–10)", tickCount=5)),
                tooltip=[
                    _alt.Tooltip("date:O", title="Date"),
                    _alt.Tooltip("score:Q", title="Overall", format=".1f"),
                ],
            )
            .properties(height=200)
        )
        st.subheader("Score progression")
        st.altair_chart(_overall_chart, use_container_width=True)

        # ── English Curves — per-dimension trend ──────────────────────────
        _dim_rows = []
        for _r in _prog_rows:
            _row_d: dict = {"date": _r["date"]}
            _row_d.update(_parse_dims(_r["scores"]))
            _dim_rows.append(_row_d)

        if _dim_rows and len(_dim_rows) >= 2:
            _dim_df = _pd.DataFrame(_dim_rows)
            _dim_cols = [c for c in _dim_df.columns if c != "date" and _dim_df[c].notna().any()]
            if _dim_cols:
                _dim_long = _dim_df.melt(
                    id_vars=["date"], value_vars=_dim_cols,
                    var_name="Dimension", value_name="Score"
                ).dropna(subset=["Score"])
                if not _dim_long.empty:
                    _curves_chart = (
                        _alt.Chart(_dim_long)
                        .mark_line(point=True, strokeWidth=1.8)
                        .encode(
                            x=_alt.X("date:O", axis=_alt.Axis(labelAngle=-30, title=None)),
                            y=_alt.Y("Score:Q",
                                     scale=_alt.Scale(domain=[0, 10]),
                                     axis=_alt.Axis(title="Score (0–10)", tickCount=5)),
                            color=_alt.Color("Dimension:N",
                                             legend=_alt.Legend(title="Dimension")),
                            tooltip=["date:O", "Dimension:N",
                                     _alt.Tooltip("Score:Q", format=".1f")],
                        )
                        .properties(height=220)
                    )
                    st.subheader("English Curves")
                    st.caption("Per-dimension score evolution across sessions.")
                    st.altair_chart(_curves_chart, use_container_width=True)

        st.divider()

    # ── Recent sessions ───────────────────────────────────────────────────
    st.subheader("Recent sessions")

    _session_files = sorted(_EC_SESSIONS.glob("*_english-coach.md"), reverse=True) if _EC_SESSIONS.exists() else []

    if not _session_files:
        st.info("No session files found.")
    else:
        # Fingerprint every recording chronologically FIRST, so "the original" is
        # the earliest rating of that recording — the display list is newest-first.
        _first_rating: dict = {}
        for _af in sorted(_session_files):
            _afm_m = re.match(r"^---\n(.*?)\n---", _af.read_text(encoding="utf-8", errors="replace"), re.DOTALL)
            if not _afm_m:
                continue
            import yaml as _yaml0
            _afm = _yaml0.safe_load(_afm_m.group(1)) or {}
            _afp = (_afm.get("duration_min"), _afm.get("words_total"))
            if all(_afp) and _afp not in _first_rating:
                _first_rating[_afp] = _afm.get("date", _af.stem[:10])

        for _sf in _session_files[:10]:
            _stext = _sf.read_text(encoding="utf-8")
            _fm_m  = re.match(r"^---\n(.*?)\n---", _stext, re.DOTALL)
            if not _fm_m:
                continue
            import yaml as _yaml
            _sfm = _yaml.safe_load(_fm_m.group(1))
            _s_date       = _sfm.get("date", _sf.stem[:10])
            _s_overall    = _sfm.get("overall", "?")
            _s_level      = _sfm.get("level", "?")
            _s_topic_type = _sfm.get("topic_type", "")
            _s_body       = _stext[_fm_m.end():].strip()
            _summary_m    = re.search(r"> (.+)", _s_body)
            _summary      = _summary_m.group(1) if _summary_m else ""
            _type_badge   = f" · {_s_topic_type.title()}" if _s_topic_type else ""

            # Confidence lives in the body ("**CEFR Level:** B2 ⚠️ low confidence"),
            # not in the frontmatter — reading it from the frontmatter silently
            # never fired the badge.
            _conf_m     = re.search(r"\*\*CEFR Level:\*\*[^\n]*?(low|medium|high) confidence", _s_body)
            _conf_badge = " ⚠️ low confidence" if _conf_m and _conf_m.group(1) == "low" else ""

            # Same recording rated more than once: the duration+word-count pair is
            # the recording's fingerprint. A re-run is not a new data point.
            _fp = (_sfm.get("duration_min"), _sfm.get("words_total"))
            _dup_badge = ""
            if all(_fp) and _first_rating.get(_fp) not in (None, _s_date):
                _dup_badge = f" · 🔁 re-analysis of the {_first_rating[_fp]} recording"

            with st.expander(
                f"**{_s_date}** — {_s_overall}/10 · {_s_level}{_conf_badge}{_type_badge}{_dup_badge}"
                f"  _{_summary[:80]}_"
            ):
                _body_display = re.split(r"\n## (?:Evaluated excerpt|Full transcript|Transcript)\b", _s_body)[0]
                st.markdown(_body_display, unsafe_allow_html=False)
                st.caption(f"Full transcript saved in Obsidian · Areas/English-Learning/sessions/{_sf.name}")

    if _prog_rows:
        st.divider()
        st.subheader("Full log")
        st.markdown(_prog_text)
