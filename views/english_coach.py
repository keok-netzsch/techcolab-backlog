"""views/english_coach.py — English Coach page."""

import re

import streamlit as st

from config import EC_DIR


def render() -> None:
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

    if _prog_rows:
        # ── KPIs ─────────────────────────────────────────────────────────
        _latest   = _prog_rows[-1]
        _avg      = sum(r["overall"] for r in _prog_rows) / len(_prog_rows)
        _best     = max(r["overall"] for r in _prog_rows)
        _k1, _k2, _k3, _k4 = st.columns(4)
        _k1.metric("Sessions", len(_prog_rows))
        _k2.metric("Latest score", f"{_latest['overall']:.1f}/10")
        _k3.metric("Overall average", f"{_avg:.1f}/10")
        _k4.metric("Best score", f"{_best:.1f}/10")
        _k1.caption(f"Current level: **{_latest['level']}**")

        # ── Topic type breakdown ──────────────────────────────────────────
        _typed_rows = [_r for _r in _prog_rows if _r.get("topic_type")]
        if _typed_rows:
            from collections import defaultdict
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
            for _part in _r["scores"].split(" | "):
                if ": " in _part:
                    _dname, _dval = _part.rsplit(": ", 1)
                    try:
                        _row_d[_dname.strip()] = int(_dval.strip())
                    except ValueError:
                        pass
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
                                     _alt.Tooltip("Score:Q", format=".0f")],
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
            _s_level_conf = _sfm.get("level_confidence", "")
            _s_topic_type = _sfm.get("topic_type", "")
            _s_body       = _stext[_fm_m.end():].strip()
            _summary_m    = re.search(r"> (.+)", _s_body)
            _summary      = _summary_m.group(1) if _summary_m else ""
            _type_badge   = f" · {_s_topic_type.title()}" if _s_topic_type else ""
            _conf_badge   = " ⚠️" if _s_level_conf == "low" else ""

            with st.expander(f"**{_s_date}** — {_s_overall}/10 · {_s_level}{_conf_badge}{_type_badge}  _{_summary[:80]}_"):
                _body_display = re.split(r"\n## (?:Evaluated excerpt|Full transcript|Transcript)\b", _s_body)[0]
                st.markdown(_body_display, unsafe_allow_html=False)
                st.caption(f"Full transcript saved in Obsidian · Areas/English-Learning/sessions/{_sf.name}")

    if _prog_rows:
        st.divider()
        st.subheader("Full log")
        st.markdown(_prog_text)
