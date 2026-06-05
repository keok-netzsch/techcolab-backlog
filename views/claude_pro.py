"""views/claude_pro.py — Claude Pro page (live backlog view + configured stack)."""

import json
from datetime import date
from pathlib import Path

import streamlit as st

from backlog.cache import load_ideas
from components.ui import STATUS_LABEL, pbadge, sdot
from config import CLAUDE_PRO_START_DATE

_REPORTS_DIR = Path(__file__).parent.parent / "reports"
_DATA_JSON   = _REPORTS_DIR / "claude-pro-data.json"

_STATUS_ACTIVE    = {"em desenvolvimento", "em validação", "aguardando desenvolvimento", "em análise", "análise - aprovado"}
_STATUS_COMPLETED = {"concluído"}
_STATUS_PAUSED    = {"arquivado", "descartado"}

_PRIO_ORDER = {"alta": 0, "média": 1, "baixa": 2}


def render() -> None:
    dark_mode = st.query_params.get("dark", "1") == "1"

    # ── Static config (exec summary + tools only) ─────────────────────────────
    _exec_bullets: list[str] = []
    _cp_tools: list[tuple] = []
    if _DATA_JSON.exists():
        try:
            _raw = json.loads(_DATA_JSON.read_text(encoding="utf-8"))
            _exec_bullets = _raw.get("exec_summary", {}).get("bullets", [])
            _cp_tools = [tuple(t) for t in _raw.get("tools", [])]
        except Exception:
            pass

    # ── Live backlog data ─────────────────────────────────────────────────────
    ideas = load_ideas()
    active    = sorted([i for i in ideas if i.status in _STATUS_ACTIVE],
                       key=lambda i: (_PRIO_ORDER.get(i.priority, 9), i.id))
    completed = [i for i in ideas if i.status in _STATUS_COMPLETED]
    bugs_open = [i for i in ideas if i.is_bug and i.status not in _STATUS_COMPLETED | _STATUS_PAUSED]

    wip_todos = [
        (i, t) for i in ideas for t in i.todos
        if t.get("in_progress") and not t.get("done")
    ]
    overdue_todos = [
        (i, t) for i in ideas for t in i.todos
        if not t.get("done") and t.get("due_date")
        and date.fromisoformat(t["due_date"]) < date.today()
    ]

    _cp_start = date.fromisoformat(CLAUDE_PRO_START_DATE)
    _cp_days  = (date.today() - _cp_start).days
    _total    = len(active) + len(completed)
    _pct      = int(_total and len(completed) / _total * 100)

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
    .cp-stat-strip{display:grid;grid-template-columns:repeat(5,1fr);gap:2px;margin-bottom:1.5rem}
    .cp-stat-box{background:white;border:1px solid rgba(76,77,88,.12);padding:20px 24px;border-radius:4px}
    .cp-stat-num{font-size:36px;font-weight:700;letter-spacing:-.03em;line-height:1;margin-bottom:4px;
                 background:linear-gradient(135deg,#007167,#8AC6BD);
                 -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
    .cp-stat-num-warn{font-size:36px;font-weight:700;letter-spacing:-.03em;line-height:1;margin-bottom:4px;
                      color:#EF4444}
    .cp-stat-lbl{font-size:13px;color:rgba(76,77,88,.55)}
    .cp-sect-lbl{font-family:'DM Mono',monospace;font-size:10px;font-weight:500;letter-spacing:.18em;
                 text-transform:uppercase;color:rgba(76,77,88,.55);margin:1.5rem 0 .4rem;
                 display:flex;align-items:center;gap:12px}
    .cp-sect-lbl::after{content:'';flex:1;height:1px;background:rgba(76,77,88,.12)}
    .cp-tools-tbl{width:100%;border-collapse:collapse;font-size:14px;margin-top:.5rem}
    .cp-tools-tbl th{font-family:'DM Mono',monospace;font-size:10px;font-weight:500;letter-spacing:.12em;
                     text-transform:uppercase;color:rgba(76,77,88,.55);text-align:left;
                     padding:10px 14px;border-bottom:1px solid rgba(76,77,88,.12);background:white}
    .cp-tools-tbl td{padding:12px 14px;border-bottom:1px solid rgba(76,77,88,.12);
                     vertical-align:top;background:white}
    .cp-tools-tbl tr:last-child td{border-bottom:none}
    .cp-tool-name{font-weight:500;font-size:14px;color:#2A2A2A}
    .cp-tool-sub{font-size:12px;color:rgba(76,77,88,.55);margin-top:2px}
    .cp-badge-prog{font-family:'DM Mono',monospace;font-size:10px;font-weight:500;letter-spacing:.08em;
                   text-transform:uppercase;padding:3px 9px;border-radius:999px;
                   background:#fdf0e0;color:#b5640a;display:inline-block;margin-right:4px}
    .cp-badge-done{font-family:'DM Mono',monospace;font-size:10px;font-weight:500;letter-spacing:.08em;
                   text-transform:uppercase;padding:3px 9px;border-radius:999px;
                   background:rgba(2,183,147,.09);color:#007167;display:inline-block;margin-right:4px}
    .cp-badge-cfg{font-family:'DM Mono',monospace;font-size:10px;font-weight:500;letter-spacing:.08em;
                  text-transform:uppercase;padding:3px 9px;border-radius:999px;
                  background:rgba(181,100,10,.09);color:#b5640a;display:inline-block;margin-right:4px}
    .cp-todo-row{padding:6px 0;border-bottom:1px solid rgba(76,77,88,.07);font-size:13px}
    .cp-todo-row:last-child{border-bottom:none}
    .cp-id{font-family:monospace;font-size:11px;color:#02B793;background:rgba(2,183,147,.08);
           padding:1px 5px;border-radius:3px;margin-right:6px}
    @media(max-width:768px){
      .cp-header{grid-template-columns:1fr}.cp-meta{text-align:left}
      .cp-stat-strip{grid-template-columns:repeat(2,1fr)}
    }
    </style>""", unsafe_allow_html=True)

    _body_clr = "#94A3B8" if dark_mode else "rgba(76,77,88,.7)"
    _td       = f"padding:7px 12px;font-size:13px;color:{_body_clr};border-bottom:1px solid rgba(76,77,88,.08);vertical-align:top"
    _td_id    = _td + ";white-space:nowrap;font-family:monospace;font-size:12px;color:#02B793"
    _th       = ("padding:7px 12px;text-align:left;font-weight:500;font-size:11px;"
                 "color:rgba(76,77,88,.5);border-bottom:1px solid rgba(76,77,88,.15);white-space:nowrap;"
                 "font-family:'DM Mono',monospace;letter-spacing:.06em;text-transform:uppercase")

    # ── Header ────────────────────────────────────────────────────────────────
    _cp_h_left, _cp_h_right = st.columns([6, 1])
    with _cp_h_left:
        st.markdown(f"""<div class="cp-header">
          <div>
            <div class="cp-org">NBS D&amp;A &middot; Techco.lab &middot; Team Lead</div>
            <div class="cp-h1">Claude Pro — Work Dashboard</div>
          </div>
          <div class="cp-meta">
            <strong>Kelvin Okuda</strong><br>
            Team Lead · D&amp;A Projects &amp; Governance<br>
            Since: {CLAUDE_PRO_START_DATE} &rarr; present ({_cp_days}d)<br>
            Live data from backlog · {date.today().strftime('%d/%m/%Y')}
          </div>
        </div>""", unsafe_allow_html=True)
    with _cp_h_right:
        st.markdown('<div style="height:2.4rem"></div>', unsafe_allow_html=True)
        if st.button("🔄 Refresh", type="primary", key="cp_update_btn_top", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    # ── Overview stats ────────────────────────────────────────────────────────
    _bar_clr = "#02B793" if not dark_mode else "#0AD4A8"
    _bar_bg  = "rgba(2,183,147,.12)" if not dark_mode else "rgba(10,212,168,.08)"
    _bug_num_cls = "cp-stat-num-warn" if bugs_open else "cp-stat-num"
    _ov_num_cls  = "cp-stat-num-warn" if overdue_todos else "cp-stat-num"

    st.markdown(f"""<div class="cp-stat-strip">
      <div class="cp-stat-box">
        <div class="cp-stat-num">{len(active)}</div>
        <div class="cp-stat-lbl">Active ideas</div>
      </div>
      <div class="cp-stat-box">
        <div class="cp-stat-num">{len(completed)}</div>
        <div class="cp-stat-lbl">Completed</div>
        <div style="margin-top:8px;height:4px;border-radius:2px;background:{_bar_bg};overflow:hidden">
          <div style="height:100%;width:{_pct}%;background:{_bar_clr};border-radius:2px"></div>
        </div>
        <div style="font-size:10px;color:rgba(76,77,88,.4);margin-top:3px;font-family:'DM Mono',monospace">{_pct}% done</div>
      </div>
      <div class="cp-stat-box">
        <div class="cp-stat-num">{len(wip_todos)}</div>
        <div class="cp-stat-lbl">In-progress to-dos</div>
      </div>
      <div class="cp-stat-box">
        <div class="{_ov_num_cls}">{len(overdue_todos)}</div>
        <div class="cp-stat-lbl">Overdue to-dos</div>
      </div>
      <div class="cp-stat-box">
        <div class="{_bug_num_cls}">{len(bugs_open)}</div>
        <div class="cp-stat-lbl">Open bugs</div>
      </div>
    </div>""", unsafe_allow_html=True)

    # ── Executive summary (static — edit claude-pro-data.json to update) ──────
    if _exec_bullets:
        _bl = "".join(f"<li>{b}</li>" for b in _exec_bullets)
        st.markdown(f"""<div style="background:rgba(2,183,147,.05);border:1px solid rgba(2,183,147,.35);
          border-left:4px solid #02B793;border-radius:6px;padding:20px 24px;margin-bottom:1.5rem">
          <div style="font-family:'DM Mono',monospace;font-size:10px;font-weight:500;letter-spacing:.14em;
               text-transform:uppercase;color:#02B793;margin-bottom:10px">What Claude Pro is used for</div>
          <ul style="display:grid;grid-template-columns:1fr 1fr;gap:4px 24px;list-style:none;padding:0;margin:0">
            {_bl}
          </ul>
        </div>""", unsafe_allow_html=True)

    # ── Active ideas ──────────────────────────────────────────────────────────
    st.markdown('<div class="cp-sect-lbl">Active ideas</div>', unsafe_allow_html=True)

    if not active:
        st.info("No active ideas found in the backlog.")
    else:
        _rows = ""
        for i in active:
            _status_lbl = STATUS_LABEL.get(i.status, i.status)
            _area       = i.area or "—"
            _prio_badge = pbadge({"alta": "3", "média": "2", "baixa": "1"}.get(i.priority, "·"), "#888")
            _bug_tag    = (' <span style="background:#FEE2E2;color:#B91C1C;font-size:9px;font-weight:700;'
                           'letter-spacing:.06em;padding:1px 5px;border-radius:3px">BUG</span>'
                           if i.is_bug else "")
            _open_todos = sum(1 for t in i.todos if not t.get("done"))
            _todo_str   = f'<span style="font-size:11px;color:rgba(76,77,88,.45)">{_open_todos} to-do{"s" if _open_todos != 1 else ""}</span>' if i.todos else ""
            _rows += (
                f'<tr>'
                f'<td style="{_td_id}">{i.id}</td>'
                f'<td style="{_td}">{i.title.replace("**","").strip()}{_bug_tag}&nbsp;{_todo_str}</td>'
                f'<td style="{_td}">{_area}</td>'
                f'<td style="{_td}">{_status_lbl}</td>'
                f'</tr>'
            )
        st.markdown(
            f'<table style="width:100%;border-collapse:collapse">'
            f'<thead><tr>'
            f'<th style="{_th}">ID</th>'
            f'<th style="{_th}">Title</th>'
            f'<th style="{_th}">Area</th>'
            f'<th style="{_th}">Status</th>'
            f'</tr></thead><tbody>{_rows}</tbody></table>',
            unsafe_allow_html=True,
        )

    # ── In-progress to-dos ────────────────────────────────────────────────────
    if wip_todos:
        st.markdown('<div class="cp-sect-lbl">In-progress to-dos</div>', unsafe_allow_html=True)
        _rows2 = ""
        for i, t in wip_todos:
            _due = t.get("due_date") or "—"
            _rows2 += (
                f'<tr>'
                f'<td style="{_td}">{t["text"]}</td>'
                f'<td style="{_td_id}">{i.id}</td>'
                f'<td style="{_td}">{_due}</td>'
                f'</tr>'
            )
        st.markdown(
            f'<table style="width:100%;border-collapse:collapse;margin-bottom:1rem">'
            f'<thead><tr>'
            f'<th style="{_th}">To-do</th>'
            f'<th style="{_th}">Idea</th>'
            f'<th style="{_th}">Due</th>'
            f'</tr></thead><tbody>{_rows2}</tbody></table>',
            unsafe_allow_html=True,
        )

    # ── Overdue to-dos ────────────────────────────────────────────────────────
    if overdue_todos:
        st.markdown(
            '<div class="cp-sect-lbl" style="color:#EF4444">Overdue to-dos</div>',
            unsafe_allow_html=True,
        )
        _rows3 = ""
        for i, t in overdue_todos:
            _rows3 += (
                f'<tr>'
                f'<td style="{_td}">{t["text"]}</td>'
                f'<td style="{_td_id}">{i.id}</td>'
                f'<td style="{_td};color:#EF4444;font-weight:500">{t["due_date"]}</td>'
                f'</tr>'
            )
        st.markdown(
            f'<table style="width:100%;border-collapse:collapse;margin-bottom:1rem">'
            f'<thead><tr>'
            f'<th style="{_th}">To-do</th>'
            f'<th style="{_th}">Idea</th>'
            f'<th style="{_th}">Due date</th>'
            f'</tr></thead><tbody>{_rows3}</tbody></table>',
            unsafe_allow_html=True,
        )

    # ── Completed (collapsible) ───────────────────────────────────────────────
    if completed:
        with st.expander(f"Completed ({len(completed)})", expanded=False):
            _rows4 = ""
            for i in completed:
                _area = i.area or "—"
                _upd  = i.updated_at.strftime("%d/%m/%Y") if i.updated_at else "—"
                _rows4 += (
                    f'<tr>'
                    f'<td style="{_td_id}">{i.id}</td>'
                    f'<td style="{_td}">{i.title.replace("**","").strip()}</td>'
                    f'<td style="{_td}">{_area}</td>'
                    f'<td style="{_td}">{_upd}</td>'
                    f'</tr>'
                )
            st.markdown(
                f'<table style="width:100%;border-collapse:collapse">'
                f'<thead><tr>'
                f'<th style="{_th}">ID</th>'
                f'<th style="{_th}">Title</th>'
                f'<th style="{_th}">Area</th>'
                f'<th style="{_th}">Completed</th>'
                f'</tr></thead><tbody>{_rows4}</tbody></table>',
                unsafe_allow_html=True,
            )

    # ── Tools & Integrations ──────────────────────────────────────────────────
    if _cp_tools:
        st.markdown('<div class="cp-sect-lbl">Configured Stack</div>', unsafe_allow_html=True)
        st.caption("Active Claude Pro tooling ecosystem.")
        _tool_rows = ""
        for _tn, _ts, _ta, _tst in _cp_tools:
            _tbadge = ("cp-badge-done" if _tst == "Active" else "cp-badge-cfg")
            _tool_rows += (
                f"<tr><td><div class='cp-tool-name'>{_tn}</div>"
                f"<div class='cp-tool-sub'>{_ts}</div></td>"
                f"<td style='font-size:13px;color:{_body_clr}'>{_ta}</td>"
                f"<td><span class='{_tbadge}'>{_tst}</span></td></tr>"
            )
        st.markdown(f"""<table class="cp-tools-tbl">
          <thead><tr><th>Tool</th><th>Application</th><th>Status</th></tr></thead>
          <tbody>{_tool_rows}</tbody>
        </table>""", unsafe_allow_html=True)

    st.markdown('<div style="height:1rem"></div>', unsafe_allow_html=True)
