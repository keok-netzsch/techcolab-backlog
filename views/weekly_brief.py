"""views/weekly_brief.py — Weekly Brief page (meeting prep for leadership)."""

import re
from datetime import date, timedelta
from pathlib import Path

import streamlit as st

from backlog.cache import load_ideas
from components.ui import STATUS_LABEL
from config import TEAM_DIR, VAULT_ROOT

_TEAM = [
    {"name": "Ana Leite",      "folder": "Ana-Leite"},
    {"name": "Daniel Lima",    "folder": "Daniel-Lima"},
    {"name": "Lucas Shizuno",  "folder": "Lucas-Shizuno"},
    {"name": "Pedro Hennig",   "folder": "Pedro-Hennig"},
    {"name": "Pedro Klein",    "folder": "Pedro-Klein"},
]


def _parse_1on1(path: Path):
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    parts = re.split(r"^## (\d{4}-\d{2}-\d{2})\b", text, flags=re.MULTILINE)
    if len(parts) < 3:
        return None
    session_date, content = parts[1], parts[2]
    topics, actions, in_topics, in_actions = [], [], False, False
    for line in content.splitlines():
        s = line.strip()
        if re.match(r"\*\*(T[oó]picos?|Topics?):?\*\*", s):
            in_topics, in_actions = True, False; continue
        if re.match(r"\*\*(Action [Ii]tems?|Ac[oõ]es?):?\*\*", s):
            in_topics, in_actions = False, True; continue
        if s.startswith("**") or s.startswith("---"):
            in_topics = in_actions = False
        if in_topics and s.startswith("- "):
            topics.append(s[2:])
        if in_actions and re.match(r"- \[[ x]\]", s):
            actions.append({"text": s[6:].strip(), "done": s[3] == "x"})
    return {"date": session_date, "topics": topics[:6], "actions": actions}


def _read_logs(log_dir: Path, start: date, end: date):
    entries, cur = [], start
    while cur <= end:
        lp = log_dir / f"diario-{cur.isoformat()}.md"
        if lp.exists():
            for line in lp.read_text(encoding="utf-8", errors="replace").splitlines():
                m = re.match(r"^- (\d{2}:\d{2}) `([\w-]+)` \[(.+?)\] (.+?)(?:\s—\s(.+))?$", line)
                if m:
                    entries.append({"date": cur, "time": m.group(1), "action": m.group(2),
                                    "idea_id": m.group(3), "title": m.group(4).strip(),
                                    "detail": (m.group(5) or "").strip()})
        cur += timedelta(days=1)
    return entries


def render() -> None:
    dark_mode = st.query_params.get("dark", "1") == "1"
    _LOG_DIR = VAULT_ROOT / "Log"

    st.markdown('<h1 style="margin-bottom:0.4rem">Weekly Brief</h1>', unsafe_allow_html=True)
    st.caption("Meeting prep panel for Alberto Reuters and Stefan Lautenschlager.")

    # ── Dark-mode aware inline table styles ───────────────────────────────────
    if dark_mode:
        _WB_TH = ("padding:7px 12px;text-align:left;font-weight:500;font-size:12px;"
                  "color:#64748B;border-bottom:1px solid #2D3748;white-space:nowrap")
        _WB_TD = ("padding:7px 12px;font-size:13px;color:#CBD5E0;"
                  "border-bottom:1px solid rgba(45,55,72,0.5);vertical-align:top")
        _WB_ID = _WB_TD + ";white-space:nowrap;font-family:monospace;font-size:12px;color:#02B793"
    else:
        _WB_TH = ("padding:7px 12px;text-align:left;font-weight:500;font-size:12px;"
                  "color:rgba(76,77,88,0.55);border-bottom:1px solid rgba(76,77,88,0.18);white-space:nowrap")
        _WB_TD = "padding:7px 12px;font-size:13px;border-bottom:1px solid rgba(76,77,88,0.07);vertical-align:top"
        _WB_ID = _WB_TD + ";white-space:nowrap;font-family:monospace;font-size:12px;color:#02B793"

    # ── Controls ──────────────────────────────────────────────────────────────
    _ctrl1, _ctrl2 = st.columns([1, 3])
    with _ctrl1:
        _period = st.slider("Period (days)", 3, 30, 7, key="wb_period")
    _start = date.today() - timedelta(days=_period)
    with _ctrl2:
        st.markdown("<br>", unsafe_allow_html=True)
        _c1, _c2, _c3, _c4 = st.columns(4)
        _show_devs  = _c1.checkbox("🚀 Devs",  value=True, key="wb_devs")
        _show_wip   = _c2.checkbox("🔄 WIP",   value=True, key="wb_wip")
        _show_team  = _c3.checkbox("👥 Team",  value=True, key="wb_team")
        _show_calls = _c4.checkbox("📞 Calls", value=True, key="wb_calls")

    st.caption(f"Period: **{_start.strftime('%d/%m/%Y')}** → **{date.today().strftime('%d/%m/%Y')}**")
    st.divider()

    _ideas  = load_ideas()
    _today  = date.today()
    _export = [
        f"# Weekly Brief — {_today.strftime('%d/%m/%Y')}",
        f"Period: {_start.strftime('%d/%m/%Y')} → {_today.strftime('%d/%m/%Y')}",
        "",
    ]

    # ── Section 1: Developments ───────────────────────────────────────────────
    if _show_devs:
        st.subheader("Developments")
        _logs = _read_logs(_LOG_DIR, _start, _today)
        _seen, _devs = set(), []
        for e in _logs:
            key = (e["idea_id"], e["detail"])
            if ("status:" in e["detail"] or e["action"] == "CRIADA") and key not in _seen:
                _seen.add(key); _devs.append(e)

        _export.append("## Developments")
        if not _devs:
            st.info("No developments recorded in this period.")
            _export.append("_No developments recorded._")
        else:
            _rows = ""
            for e in _devs:
                _tipo    = "Created" if e["action"] == "CRIADA" else "Status"
                _mudanca = e["detail"].replace("status:", "").replace("->", "→").strip() if e["detail"] else "—"
                _rows += (
                    f'<tr><td style="{_WB_ID}">{e["idea_id"]}</td>'
                    f'<td style="{_WB_TD}">{e["title"]}</td>'
                    f'<td style="{_WB_TD}">{_tipo}</td>'
                    f'<td style="{_WB_TD}">{_mudanca}</td></tr>'
                )
                _export.append(f"| {e['idea_id']} | {e['title']} | {_tipo} | {_mudanca} |")
            st.markdown(
                f'<table style="width:100%;border-collapse:collapse">'
                f'<thead><tr>'
                f'<th style="{_WB_TH}">ID</th>'
                f'<th style="{_WB_TH}">Title</th>'
                f'<th style="{_WB_TH}">Tipo</th>'
                f'<th style="{_WB_TH}">Change</th>'
                f'</tr></thead><tbody>{_rows}</tbody></table>',
                unsafe_allow_html=True,
            )
        _export.append(""); st.divider()

    # ── Section 2: In progress ────────────────────────────────────────────────
    if _show_wip:
        st.subheader("In progress")
        _active    = [i for i in _ideas if i.status in ("em desenvolvimento", "em validação", "aguardando desenvolvimento")]
        _wip_todos = [(i, t) for i in _ideas for t in i.todos if t.get("in_progress") and not t.get("done")]
        _upcoming  = [i for i in _ideas
                      if i.due_date and _today <= i.due_date <= _today + timedelta(days=7)
                      and i.status not in ("concluído", "descartado")]

        _export.append("## In progress")
        if not _active and not _wip_todos and not _upcoming:
            st.info("No items currently in progress.")
            _export.append("_No items in progress._")
        else:
            if _active:
                st.caption("Active ideas")
                _rows2 = ""
                for i in _active:
                    _rows2 += (
                        f'<tr><td style="{_WB_ID}">{i.id}</td>'
                        f'<td style="{_WB_TD}">{i.title.replace("**","").strip()}</td>'
                        f'<td style="{_WB_TD}">{STATUS_LABEL.get(i.status, i.status)}</td></tr>'
                    )
                    _export.append(f"| {i.id} | {i.title} | {STATUS_LABEL.get(i.status, i.status)} |")
                st.markdown(
                    f'<table style="width:100%;border-collapse:collapse;margin-bottom:12px">'
                    f'<thead><tr>'
                    f'<th style="{_WB_TH}">ID</th>'
                    f'<th style="{_WB_TH}">Title</th>'
                    f'<th style="{_WB_TH}">Status</th>'
                    f'</tr></thead><tbody>{_rows2}</tbody></table>',
                    unsafe_allow_html=True,
                )
            if _wip_todos:
                st.caption("In-progress to-dos")
                _rows3 = ""
                for i, t in _wip_todos:
                    _due_str = t["due_date"] if t.get("due_date") else "—"
                    _rows3 += (
                        f'<tr><td style="{_WB_TD}">{t["text"]}</td>'
                        f'<td style="{_WB_ID}">{i.id}</td>'
                        f'<td style="{_WB_TD}">{_due_str}</td></tr>'
                    )
                    _export.append(f"| {t['text']} | {i.id} | {_due_str} |")
                st.markdown(
                    f'<table style="width:100%;border-collapse:collapse;margin-bottom:12px">'
                    f'<thead><tr>'
                    f'<th style="{_WB_TH}">To-do</th>'
                    f'<th style="{_WB_TH}">Ideia</th>'
                    f'<th style="{_WB_TH}">Due date</th>'
                    f'</tr></thead><tbody>{_rows3}</tbody></table>',
                    unsafe_allow_html=True,
                )
            if _upcoming:
                st.caption("Due in 7 days")
                _rows4 = ""
                for i in _upcoming:
                    _dl    = (i.due_date - _today).days
                    _color = "#EF4444" if _dl <= 2 else "#F59E0B"
                    _rows4 += (
                        f'<tr><td style="{_WB_ID}">{i.id}</td>'
                        f'<td style="{_WB_TD}">{i.title.replace("**","").strip()}</td>'
                        f'<td style="{_WB_TD};color:{_color};font-weight:500">{i.due_date.strftime("%d/%m")} ({_dl}d)</td></tr>'
                    )
                    _export.append(f"| {i.id} | {i.title} | vence {i.due_date.strftime('%d/%m')} |")
                st.markdown(
                    f'<table style="width:100%;border-collapse:collapse;margin-bottom:12px">'
                    f'<thead><tr>'
                    f'<th style="{_WB_TH}">ID</th>'
                    f'<th style="{_WB_TH}">Title</th>'
                    f'<th style="{_WB_TH}">Due</th>'
                    f'</tr></thead><tbody>{_rows4}</tbody></table>',
                    unsafe_allow_html=True,
                )
        _export.append(""); st.divider()

    # ── Section 3: Team status ────────────────────────────────────────────────
    if _show_team:
        st.subheader("Team status")
        st.caption("Snapshot only — go to Team for details.")
        _export.append("## 👥 Team")
        _team_rows = ""
        for _m in _TEAM:
            _folder = TEAM_DIR / _m["folder"]
            _role = ""
            _ov = _folder / "Overview.md"
            if _ov.exists():
                _rm = re.search(r"\*\*Role:\*\*\s*(.+)", _ov.read_text(encoding="utf-8", errors="replace"))
                if _rm:
                    _role = _rm.group(1).strip()
            _latest = _parse_1on1(_folder / "1on1.md")
            if _latest:
                _open_count = sum(1 for a in _latest["actions"] if not a["done"])
                _open_str   = f'<span style="color:#EF4444;font-weight:500">{_open_count} open</span>' if _open_count else '<span style="color:#059669">✓ clear</span>'
                _team_rows += (
                    f'<tr><td style="{_WB_TD};font-weight:500">{_m["name"]}</td>'
                    f'<td style="{_WB_TD};color:rgba(76,77,88,.55)">{_role}</td>'
                    f'<td style="{_WB_TD}">{_latest["date"]}</td>'
                    f'<td style="{_WB_TD}">{_open_str}</td></tr>'
                )
                _export.append(f"| {_m['name']} | {_role} | last 1:1: {_latest['date']} | {_open_count} open actions |")
            else:
                _team_rows += (
                    f'<tr><td style="{_WB_TD};font-weight:500">{_m["name"]}</td>'
                    f'<td style="{_WB_TD};color:rgba(76,77,88,.55)">{_role}</td>'
                    f'<td style="{_WB_TD};color:rgba(76,77,88,.35)">—</td>'
                    f'<td style="{_WB_TD};color:rgba(76,77,88,.35)">—</td></tr>'
                )
                _export.append(f"| {_m['name']} | {_role} | — | — |")
        st.markdown(
            f'<table style="width:100%;border-collapse:collapse">'
            f'<thead><tr>'
            f'<th style="{_WB_TH}">Name</th>'
            f'<th style="{_WB_TH}">Role</th>'
            f'<th style="{_WB_TH}">Last 1:1</th>'
            f'<th style="{_WB_TH}">Open actions</th>'
            f'</tr></thead><tbody>{_team_rows}</tbody></table>',
            unsafe_allow_html=True,
        )
        _export.append(""); st.divider()

    # ── Section 4: Calls ──────────────────────────────────────────────────────
    if _show_calls:
        st.subheader("Calls this week")
        _export.append("## 📞 Calls")
        _calls = []
        for _m in _TEAM:
            _call_dir = TEAM_DIR / _m["folder"] / "1on1"
            if _call_dir.exists():
                for _cf in sorted(_call_dir.glob("*.md")):
                    if _cf.name.startswith("_"):
                        continue
                    try:
                        _nd = date.fromisoformat(_cf.stem[:10])
                        if _nd >= _start:
                            _calls.append({"member": _m["name"], "date": _nd, "path": _cf})
                    except ValueError:
                        pass
        if not _calls:
            st.info("No calls recorded in this period.")
            _export.append("_No calls recorded in this period._")
        else:
            import html as _html
        import streamlit.components.v1 as _components
        _call_bg  = "#1A1D2E" if dark_mode else "#F8FAFC"
        _call_clr = "#CBD5E0" if dark_mode else "#374151"
        for _c in sorted(_calls, key=lambda x: x["date"], reverse=True):
                _ck = f"wb_call_{_c['member']}_{_c['date'].isoformat()}"
                if _ck not in st.session_state:
                    st.session_state[_ck] = False
                # Arrow LEFT of name
                _tcol, _hcol = st.columns([0.5, 11], vertical_alignment="center")
                if _tcol.button("▲" if st.session_state[_ck] else "▼",
                                key=f"wb_ct_{_c['member']}_{_c['date'].isoformat()}"):
                    st.session_state[_ck] = not st.session_state[_ck]
                    st.rerun()
                _hcol.markdown(f"📞 **{_c['member']}** — {_c['date'].strftime('%d/%m/%Y')}")
                if st.session_state[_ck]:
                    _body = re.sub(r"^---.*?---\n", "",
                                   _c["path"].read_text(encoding="utf-8", errors="replace"),
                                   flags=re.DOTALL).strip()
                    _body_safe = _html.escape(_body[:3000])
                    _n_lines   = min(_body[:3000].count("\n") + 4, 60)
                    _h_px      = _n_lines * 19 + 28
                    # iframe fully isolated from Streamlit React tree — hover cannot affect it
                    _components.html(
                        f'<!DOCTYPE html><html><head><meta charset="utf-8"><style>'
                        f'html,body{{margin:0;padding:12px 16px;background:{_call_bg};color:{_call_clr};'
                        f'font-family:"DM Mono",monospace;font-size:12px;line-height:1.6;'
                        f'white-space:pre-wrap;word-wrap:break-word;overflow-x:hidden}}'
                        f'</style></head><body>{_body_safe}</body></html>',
                        height=_h_px,
                        scrolling=False,
                    )
                _export.append(f"- Call com {_c['member']} em {_c['date'].strftime('%d/%m/%Y')}")
        _export.append(""); st.divider()

    # ── Export ────────────────────────────────────────────────────────────────
    st.subheader("Export summary")
    _export_md = "\n".join(_export)
    _dl_col, _ = st.columns([1, 3])
    with _dl_col:
        st.download_button("⬇️ Download .md", data=_export_md,
                           file_name=f"weekly-brief-{_today.isoformat()}.md",
                           mime="text/markdown", type="primary")
    with st.expander("Exported summary preview"):
        st.text_area(
            label="preview",
            value=_export_md,
            height=420,
            disabled=True,
            label_visibility="collapsed",
        )
