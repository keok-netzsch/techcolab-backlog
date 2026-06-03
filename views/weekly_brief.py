"""views/weekly_brief.py — Weekly Brief page (meeting prep for leadership)."""

import re
from datetime import date, timedelta
from pathlib import Path

import streamlit as st

from backlog.cache import load_ideas
from components.ui import STATUS_LABEL
from config import EC_DIR, TEAM_DIR, VAULT_ROOT

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
                st.caption("Ideas in development")
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
        _export.append("## 👥 Team")
        for _m in _TEAM:
            _folder = TEAM_DIR / _m["folder"]
            with st.expander(f"**{_m['name']}**", expanded=True):
                _role = ""
                _ov = _folder / "Overview.md"
                if _ov.exists():
                    _rm = re.search(r"\*\*Role:\*\*\s*(.+)", _ov.read_text(encoding="utf-8", errors="replace"))
                    if _rm:
                        _role = _rm.group(1).strip()

                _latest = _parse_1on1(_folder / "1on1.md")
                if _latest:
                    st.caption(f"{_role + ' — ' if _role else ''}last 1-on-1: {_latest['date']}")
                    if _latest["topics"]:
                        st.markdown("**Topics:**")
                        for _t in _latest["topics"]:
                            st.markdown(f"  - {_t}")
                    _open = [a for a in _latest["actions"] if not a["done"]]
                    if _open:
                        st.markdown("**Open action items:**")
                        for _a in _open:
                            st.markdown(f"  - ☐ {_a['text']}")
                    _export += [f"### {_m['name']}", f"Último 1-on-1: {_latest['date']}"]
                    _export += [f"- {t}" for t in _latest["topics"]]
                    if _open:
                        _export.append("Action items:")
                        _export += [f"  - [ ] {a['text']}" for a in _open]
                    _export.append("")
                else:
                    st.caption(f"{_role + ' — ' if _role else ''}no 1-on-1 recorded")
                    _export.append(f"### {_m['name']} — no 1-on-1"); _export.append("")
        st.divider()

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
            for _c in sorted(_calls, key=lambda x: x["date"], reverse=True):
                with st.expander(f"📞 {_c['member']} — {_c['date'].strftime('%d/%m/%Y')}"):
                    _body = re.sub(r"^---.*?---\n", "",
                                   _c["path"].read_text(encoding="utf-8", errors="replace"),
                                   flags=re.DOTALL).strip()
                    st.markdown(_body[:2500] + ("…" if len(_body) > 2500 else ""))
                _export.append(f"- Call com {_c['member']} em {_c['date'].strftime('%d/%m/%Y')}")
        _export.append(""); st.divider()

    # ── Section 5: English Coach snapshot ────────────────────────────────────
    st.subheader("English Coach")
    _EC_PROGRESS_WB = EC_DIR / "progress.md"
    _EC_REPORTS_WB  = VAULT_ROOT / "agent-reports"

    _ec_weekly_files  = sorted(_EC_REPORTS_WB.glob("english-coach-*.md"), reverse=True) if _EC_REPORTS_WB.exists() else []
    _ec_latest_report = _ec_weekly_files[0] if _ec_weekly_files else None

    _ec_prog_rows_wb = []
    if _EC_PROGRESS_WB.exists():
        for _ln in _EC_PROGRESS_WB.read_text(encoding="utf-8").splitlines():
            _em = re.match(
                r"\|\s*(\d{4}-\d{2}-\d{2})[^|]*\|\s*([\d.]+)/10\s*\|\s*(\w+)\s*\|([^|]+)\|([^|]*)\|",
                _ln,
            )
            if _em:
                try:
                    _ed = date.fromisoformat(_em.group(1))
                except ValueError:
                    continue
                _ec_prog_rows_wb.append({"date": _ed, "overall": float(_em.group(2)), "level": _em.group(3).strip()})

    _ec_period_sessions = [r for r in _ec_prog_rows_wb if r["date"] >= _start]

    if not _ec_prog_rows_wb:
        st.info("No English Coach sessions recorded yet.", icon="🎙️")
        _export.append("## English Coach\n_No sessions recorded yet._\n")
    else:
        _ec_latest_score = _ec_prog_rows_wb[-1]["overall"]
        _ec_latest_level = _ec_prog_rows_wb[-1]["level"]
        _ec_avg_all      = sum(r["overall"] for r in _ec_prog_rows_wb) / len(_ec_prog_rows_wb)
        _ec_period_avg   = (sum(r["overall"] for r in _ec_period_sessions) / len(_ec_period_sessions)
                            if _ec_period_sessions else None)

        _bg  = "#1A1D2E" if dark_mode else "#F9FAFB"
        _brd = "#2D3748" if dark_mode else "#E5E7EB"
        _lbl = "#64748B" if dark_mode else "#6B7280"
        _val = "#E2E8F0" if dark_mode else "#111827"
        _acc = "#02B793"

        _ec_cards = (
            f'<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin:.5rem 0">'
            f'<div style="background:{_bg};border:1px solid {_brd};border-radius:8px;padding:8px 12px">'
            f'<div style="font-size:.7rem;color:{_lbl};font-weight:500">Latest score</div>'
            f'<div style="font-size:1.2rem;font-weight:700;color:{_acc}">{_ec_latest_score:.1f}/10</div></div>'
            f'<div style="background:{_bg};border:1px solid {_brd};border-radius:8px;padding:8px 12px">'
            f'<div style="font-size:.7rem;color:{_lbl};font-weight:500">Level</div>'
            f'<div style="font-size:1.2rem;font-weight:700;color:{_val}">{_ec_latest_level}</div></div>'
            f'<div style="background:{_bg};border:1px solid {_brd};border-radius:8px;padding:8px 12px">'
            f'<div style="font-size:.7rem;color:{_lbl};font-weight:500">All-time avg</div>'
            f'<div style="font-size:1.2rem;font-weight:700;color:{_val}">{_ec_avg_all:.1f}/10</div></div>'
            f'<div style="background:{_bg};border:1px solid {_brd};border-radius:8px;padding:8px 12px">'
            f'<div style="font-size:.7rem;color:{_lbl};font-weight:500">Sessions (period)</div>'
            f'<div style="font-size:1.2rem;font-weight:700;color:{_val}">{len(_ec_period_sessions)}</div></div>'
            f'</div>'
        )
        st.markdown(_ec_cards, unsafe_allow_html=True)

        if _ec_latest_report:
            _ec_report_week = _ec_latest_report.stem.replace("english-coach-", "")
            with st.expander(f"Latest weekly report — {_ec_report_week}"):
                _ec_body = re.sub(r"^---.*?---\n", "",
                                  _ec_latest_report.read_text(encoding="utf-8", errors="replace"),
                                  flags=re.DOTALL).strip()
                st.markdown(_ec_body[:3000] + ("…" if len(_ec_body) > 3000 else ""))

        _export.append("## English Coach")
        _export.append(f"- Latest: {_ec_latest_score:.1f}/10 ({_ec_latest_level})")
        _export.append(f"- All-time avg: {_ec_avg_all:.1f}/10")
        if _ec_period_avg:
            _export.append(f"- Period avg ({_start.strftime('%d/%m/%Y')} → today): {_ec_period_avg:.1f}/10")
        if _ec_latest_report:
            _export.append(f"- Latest weekly report: {_ec_latest_report.name}")
        _export.append("")

    st.divider()

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
