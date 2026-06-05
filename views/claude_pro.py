"""views/claude_pro.py — Claude Pro page (initiatives, timeline, tools)."""

import json
from datetime import date
from pathlib import Path

import streamlit as st

from config import CLAUDE_PRO_START_DATE

_REPORTS_DIR = Path(__file__).parent.parent / "reports"
_DATA_JSON = _REPORTS_DIR / "claude-pro-data.json"



def render() -> None:
    dark_mode = st.query_params.get("dark", "1") == "1"

    # ── Load data ─────────────────────────────────────────────────────────────
    _cp_data_updated = ""
    _CP_EXEC: dict = {}
    if _DATA_JSON.exists():
        try:
            _cp_raw       = json.loads(_DATA_JSON.read_text(encoding="utf-8"))
            _CP_ACTIVE    = _cp_raw.get("active", [])
            _CP_COMPLETED = _cp_raw.get("completed", [])
            _CP_TOOLS     = [tuple(t) for t in _cp_raw.get("tools", [])]
            _cp_data_updated = _cp_raw.get("last_updated", "")
            _CP_EXEC      = _cp_raw.get("exec_summary", {})
        except Exception as _e:
            st.warning(f"⚠ Could not load claude-pro-data.json: {_e}")
            _CP_ACTIVE = _CP_COMPLETED = []
            _CP_TOOLS = []
    else:
        st.warning("⚠ claude-pro-data.json not found. Run the daily agent to generate it.")
        _CP_ACTIVE = _CP_COMPLETED = []
        _CP_TOOLS = []

    _cp_start = date.fromisoformat(CLAUDE_PRO_START_DATE)
    _cp_days  = (date.today() - _cp_start).days

    # ── Page-scoped CSS ───────────────────────────────────────────────────────
    st.markdown("""<style>
    .cp-header{background:#4C4D58;padding:36px 48px;border-radius:8px;
               display:grid;grid-template-columns:1fr auto;gap:24px;align-items:end;margin-bottom:1.5rem}
    .cp-org{font-family:'DM Mono',monospace;font-size:11px;font-weight:500;letter-spacing:.14em;
            text-transform:uppercase;color:#02B793;margin-bottom:8px}
    .cp-h1{font-size:clamp(22px,3vw,34px);font-weight:700;line-height:1.2;letter-spacing:-.02em;
           background:linear-gradient(135deg,#fff 0%,#0AD4A8 100%);
           -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;margin:0}
    .cp-meta{text-align:right;font-family:'DM Mono',monospace;font-size:11px;
             color:rgba(255,255,255,.45);line-height:1.9;letter-spacing:.04em}
    .cp-meta strong{color:rgba(255,255,255,.9);font-weight:500}
    .cp-stat-strip{display:grid;grid-template-columns:repeat(4,1fr);gap:2px;margin-bottom:1.5rem}
    .cp-stat-box{background:white;border:1px solid rgba(76,77,88,.12);padding:20px 24px;border-radius:4px}
    .cp-stat-num{font-size:36px;font-weight:700;letter-spacing:-.03em;line-height:1;margin-bottom:4px;
                 background:linear-gradient(135deg,#007167,#8AC6BD);
                 -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
    .cp-stat-lbl{font-size:13px;color:rgba(76,77,88,.55)}
    .cp-exec{background:rgba(2,183,147,.05);border:1px solid rgba(2,183,147,.35);
             border-left:4px solid #02B793;border-radius:6px;padding:24px 28px;margin-bottom:1.5rem}
    .cp-exec-lbl{font-family:'DM Mono',monospace;font-size:10px;font-weight:500;letter-spacing:.14em;
                 text-transform:uppercase;color:#02B793;margin-bottom:10px}
    .cp-exec-lead{font-size:15px;color:#2A2A2A;margin-bottom:14px;line-height:1.6}
    .cp-exec-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px 28px;list-style:none;padding:0;margin:0}
    .cp-exec-grid li{font-size:14px;color:#4A4A4A;position:relative;padding-left:14px}
    .cp-exec-grid li::before{content:'';position:absolute;left:0;top:.3em;width:4px;height:1em;
                              background:#02B793;border-radius:2px}
    .cp-exec-grid li strong{color:#2A2A2A;font-weight:500}
    .cp-sect-lbl{font-family:'DM Mono',monospace;font-size:10px;font-weight:500;letter-spacing:.18em;
                 text-transform:uppercase;color:rgba(76,77,88,.55);margin:1.5rem 0 .4rem;
                 display:flex;align-items:center;gap:12px}
    .cp-sect-lbl::after{content:'';flex:1;height:1px;background:rgba(76,77,88,.12)}
    .cp-boss{background:rgba(2,183,147,.05);border-left:3px solid #02B793;
             border-radius:0 4px 4px 0;padding:10px 14px;margin-bottom:10px}
    .cp-boss-lbl{font-family:'DM Mono',monospace;font-size:9px;font-weight:500;letter-spacing:.14em;
                 text-transform:uppercase;color:#02B793;margin-bottom:4px}
    .cp-boss-p{font-size:13px;color:#2A2A2A;line-height:1.6;margin:0}
    .cp-boss-adv{margin-top:5px;font-size:12px;color:rgba(76,77,88,.55)}
    .cp-boss-adv strong{color:#007167;font-weight:500}
    .cp-body-ul{list-style:none;padding:0;margin:6px 0 0}
    .cp-body-ul li{position:relative;padding-left:14px;margin-bottom:3px;font-size:13px;color:rgba(76,77,88,.8)}
    .cp-body-ul li::before{content:'';position:absolute;left:0;top:.6em;width:4px;height:4px;
                            border-radius:50%;background:rgba(76,77,88,.25)}
    .cp-badge-prog{font-family:'DM Mono',monospace;font-size:10px;font-weight:500;letter-spacing:.08em;
                   text-transform:uppercase;padding:3px 9px;border-radius:999px;
                   background:#fdf0e0;color:#b5640a;display:inline-block;margin-right:4px}
    .cp-badge-done{font-family:'DM Mono',monospace;font-size:10px;font-weight:500;letter-spacing:.08em;
                   text-transform:uppercase;padding:3px 9px;border-radius:999px;
                   background:rgba(2,183,147,.09);color:#007167;display:inline-block;margin-right:4px}
    .cp-badge-cfg{font-family:'DM Mono',monospace;font-size:10px;font-weight:500;letter-spacing:.08em;
                  text-transform:uppercase;padding:3px 9px;border-radius:999px;
                  background:rgba(181,100,10,.09);color:#b5640a;display:inline-block;margin-right:4px}
    .cp-badge-cat{font-family:'DM Mono',monospace;font-size:10px;font-weight:500;letter-spacing:.08em;
                  text-transform:uppercase;padding:3px 9px;border-radius:999px;
                  background:rgba(76,77,88,.07);color:rgba(76,77,88,.55);display:inline-block}
    .cp-badge-draft{font-family:'DM Mono',monospace;font-size:10px;font-weight:500;letter-spacing:.08em;
                    text-transform:uppercase;padding:3px 9px;border-radius:999px;
                    background:rgba(99,102,241,.1);color:#6366f1;display:inline-block;margin-right:4px}
    .cp-tools-tbl{width:100%;border-collapse:collapse;font-size:14px;margin-top:.5rem}
    .cp-tools-tbl th{font-family:'DM Mono',monospace;font-size:10px;font-weight:500;letter-spacing:.12em;
                     text-transform:uppercase;color:rgba(76,77,88,.55);text-align:left;
                     padding:10px 14px;border-bottom:1px solid rgba(76,77,88,.12);background:white}
    .cp-tools-tbl td{padding:12px 14px;border-bottom:1px solid rgba(76,77,88,.12);
                     vertical-align:top;background:white}
    .cp-tools-tbl tr:last-child td{border-bottom:none}
    .cp-tool-name{font-weight:500;font-size:14px;color:#2A2A2A}
    .cp-tool-sub{font-size:12px;color:rgba(76,77,88,.55);margin-top:2px}
    .cp-footer{background:#4C4D58;padding:20px 32px;border-radius:6px;display:flex;
               justify-content:space-between;align-items:center;margin-top:2rem}
    .cp-footer-l{font-family:'DM Mono',monospace;font-size:11px;color:rgba(255,255,255,.45)}
    .cp-footer-r{font-size:12px;color:rgba(255,255,255,.35)}
    .cp-dot{color:#02B793}
    @media(max-width:768px){
      .cp-header{grid-template-columns:1fr}.cp-meta{text-align:left}
      .cp-stat-strip{grid-template-columns:repeat(2,1fr)}.cp-exec-grid{grid-template-columns:1fr}
    }
    </style>""", unsafe_allow_html=True)

    # ── Header ────────────────────────────────────────────────────────────────
    _cp_h_left, _cp_h_right = st.columns([6, 1])
    with _cp_h_left:
        st.markdown(f"""<div class="cp-header">
          <div>
            <div class="cp-org">NBS D&amp;A &middot; Techco.lab &middot; Team Lead</div>
            <div class="cp-h1">Claude Pro — Initiatives<br>&amp; Developments</div>
          </div>
          <div class="cp-meta">
            <strong>Kelvin Okuda</strong><br>
            Team Lead · D&amp;A Projects &amp; Governance<br>
            Period: 11/05/2026 &rarr; present<br>
            Updated: {date.today().strftime('%d/%m/%Y')}
          </div>
        </div>""", unsafe_allow_html=True)
    with _cp_h_right:
        st.markdown('<div style="height:2.4rem"></div>', unsafe_allow_html=True)
        if st.button("🔄 Refresh", type="primary", key="cp_update_btn_top", use_container_width=True,
                     help="Check for new commits and sessions since last update"):
            from agent.daily_report import _update_claude_pro_report
            with st.spinner("Checking..."):
                ok = _update_claude_pro_report()
            if ok:
                st.rerun()
            else:
                st.toast("Already up to date.", icon="✅")

    # ── Data freshness indicator ──────────────────────────────────────────────
    if _cp_data_updated:
        try:
            _upd_date = date.fromisoformat(_cp_data_updated[:10])
            _upd_age  = (date.today() - _upd_date).days
        except ValueError:
            _upd_age = 0
        if _upd_age > 2:
            st.markdown(
                f'<div style="margin-bottom:.75rem;padding:.45rem .75rem;border-radius:5px;'
                f'border-left:3px solid #EF4444;background:rgba(239,68,68,.07)">'
                f'<span style="font-size:.75rem;color:#EF4444;font-weight:600">DATA STALE</span>'
                f'<span style="font-size:.75rem;color:#EF4444"> — last updated {_upd_age}d ago '
                f'({_cp_data_updated[:10]}). Run the daily agent or click Refresh.</span></div>',
                unsafe_allow_html=True,
            )
        else:
            _upd_clr = "#475569" if dark_mode else "rgba(76,77,88,.4)"
            st.markdown(
                f'<p style="font-size:11px;font-family:\'DM Mono\',monospace;color:{_upd_clr};'
                f'margin-bottom:.5rem">Data last updated: {_cp_data_updated} · '
                f'auto-refreshed daily at 08:00 by the agent</p>',
                unsafe_allow_html=True,
            )

    # ── Overview stats ────────────────────────────────────────────────────────
    st.markdown('<div class="cp-sect-lbl">Overview</div>', unsafe_allow_html=True)
    _cp_total_init = len(_CP_ACTIVE) + len(_CP_COMPLETED)
    _cp_pct        = int(_cp_total_init and (len(_CP_COMPLETED) / _cp_total_init * 100))
    _cp_bar_clr    = "#02B793" if not dark_mode else "#0AD4A8"
    _cp_bar_bg     = "rgba(2,183,147,.12)" if not dark_mode else "rgba(10,212,168,.08)"

    st.markdown(f"""<div class="cp-stat-strip">
      <div class="cp-stat-box"><div class="cp-stat-num">{_cp_total_init}</div><div class="cp-stat-lbl">Total initiatives</div></div>
      <div class="cp-stat-box">
        <div class="cp-stat-num">{len(_CP_COMPLETED)}</div>
        <div class="cp-stat-lbl">Completed</div>
        <div style="margin-top:8px;height:4px;border-radius:2px;background:{_cp_bar_bg};overflow:hidden">
          <div style="height:100%;width:{_cp_pct}%;background:{_cp_bar_clr};border-radius:2px;transition:width .4s ease"></div>
        </div>
        <div style="font-size:10px;color:rgba(76,77,88,.4);margin-top:3px;font-family:'DM Mono',monospace">{_cp_pct}% done</div>
      </div>
      <div class="cp-stat-box"><div class="cp-stat-num">{len(_CP_ACTIVE)}</div><div class="cp-stat-lbl">In progress</div></div>
      <div class="cp-stat-box"><div class="cp-stat-num">{_cp_days}d</div><div class="cp-stat-lbl">Since start</div></div>
    </div>""", unsafe_allow_html=True)

    # ── Executive summary ─────────────────────────────────────────────────────
    if _CP_EXEC:
        _exec_lead    = (_CP_EXEC.get("lead", "")
                         .replace("{days}", str(_cp_days))
                         .replace("{total}", str(_cp_total_init)))
        _exec_bullets = "".join(f"<li>{b}</li>" for b in _CP_EXEC.get("bullets", []))
        st.markdown(f"""<div class="cp-exec">
          <div class="cp-exec-lbl">For the manager — what is being done with Claude Pro</div>
          <p class="cp-exec-lead">{_exec_lead}</p>
          <ul class="cp-exec-grid">{_exec_bullets}</ul>
        </div>""", unsafe_allow_html=True)

    # ── Active initiatives ────────────────────────────────────────────────────
    st.markdown('<div class="cp-sect-lbl">Initiatives</div>', unsafe_allow_html=True)
    st.subheader("Projects & Developments")
    st.caption("Claude Pro applied to management, governance and D&A team development.")

    _cp_body_clr = "#94A3B8" if dark_mode else "rgba(76,77,88,.7)"
    for _init in _CP_ACTIVE:
        _is_draft  = _init.get("status") == "draft"
        _init_num  = _init.get("number", "??")
        _bl        = "".join(f"<li>{b}</li>" for b in _init.get("bullets", []))
        _exp_lbl   = (f"**{_init_num}** · {_init['title']}"
                      if _init_num != "??" else f"🔍 {_init['title']} *(draft)*")
        with st.expander(_exp_lbl, expanded=not _is_draft):
            if _is_draft:
                _proj_path = _init.get("project_path", "")
                st.markdown(
                    f'<span class="cp-badge-draft">Draft</span>'
                    f'<span class="cp-badge-cat">{_init["category"]}</span>',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f'<p style="font-size:13px;color:{_cp_body_clr};margin:.6rem 0">'
                    f'Auto-discovered from Claude Code sessions in <code>{_proj_path}</code>.<br>'
                    f'Narrative will be auto-generated in the next agent run (Phase 2).</p>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<span class="cp-badge-prog">In progress</span>'
                    f'<span class="cp-badge-cat">{_init["category"]}</span>',
                    unsafe_allow_html=True,
                )
                st.markdown(f"""<div class="cp-boss">
                  <div class="cp-boss-lbl">In summary</div>
                  <p class="cp-boss-p">{_init['boss']}</p>
                  <p class="cp-boss-adv"><strong>Key advance:</strong> {_init['advance']}</p>
                </div>
                <p style="font-size:13.5px;color:{_cp_body_clr};margin:.4rem 0 .3rem">{_init['body']}</p>
                <ul class="cp-body-ul">{_bl}</ul>""", unsafe_allow_html=True)

    # ── Completed toggle ──────────────────────────────────────────────────────
    if "cp_show_completed" not in st.session_state:
        st.session_state["cp_show_completed"] = False
    _ct_n   = len(_CP_COMPLETED)
    _ct_lbl = (f"▴ Completed ({_ct_n}) — hide" if st.session_state["cp_show_completed"]
               else f"▾ Completed ({_ct_n}) — show")
    if st.button(_ct_lbl, key="cp_toggle_completed", use_container_width=True):
        st.session_state["cp_show_completed"] = not st.session_state["cp_show_completed"]
        st.rerun()

    if st.session_state["cp_show_completed"]:
        for _init in _CP_COMPLETED:
            _bl = "".join(f"<li>{b}</li>" for b in _init["bullets"])
            with st.expander(f"**{_init['number']}** · {_init['title']}", expanded=False):
                st.markdown(
                    f'<span class="cp-badge-done">Done</span>'
                    f'<span class="cp-badge-cat">{_init["category"]}</span>',
                    unsafe_allow_html=True,
                )
                st.markdown(f"""<div class="cp-boss">
                  <div class="cp-boss-lbl">In summary</div>
                  <p class="cp-boss-p">{_init['boss']}</p>
                  <p class="cp-boss-adv"><strong>Key advance:</strong> {_init['advance']}</p>
                </div>
                <p style="font-size:13.5px;color:{_cp_body_clr};margin:.4rem 0 .3rem">{_init['body']}</p>
                <ul class="cp-body-ul">{_bl}</ul>""", unsafe_allow_html=True)

    # ── Tools & Integrations ──────────────────────────────────────────────────
    st.markdown('<div class="cp-sect-lbl">Configured Stack</div>', unsafe_allow_html=True)
    st.subheader("Tools & Integrations")
    st.caption("Active Claude Pro tooling ecosystem in the work environment.")

    _tool_rows = ""
    for _tn, _ts, _ta, _tst in _CP_TOOLS:
        _tbadge = ("cp-badge-done" if _tst == "Active"
                   else "cp-badge-cfg" if _tst == "Configured"
                   else "cp-badge-done")
        _tool_rows += (
            f"<tr><td><div class='cp-tool-name'>{_tn}</div>"
            f"<div class='cp-tool-sub'>{_ts}</div></td>"
            f"<td style='font-size:13px;color:{_cp_body_clr}'>{_ta}</td>"
            f"<td><span class='{_tbadge}'>{_tst}</span></td></tr>"
        )
    st.markdown(f"""<table class="cp-tools-tbl">
      <thead><tr><th>Tool</th><th>Application</th><th>Status</th></tr></thead>
      <tbody>{_tool_rows}</tbody>
    </table>""", unsafe_allow_html=True)

    st.markdown('<div style="height:1rem"></div>', unsafe_allow_html=True)
