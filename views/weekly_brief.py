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

            def _call_to_html(raw: str, bg: str, is_dark: bool) -> tuple[str, int]:
                """Parse BLOCO-structured call note and return (html, height_px)."""
                accent  = "#02B793"
                fg_main = "#E2E8F0" if is_dark else "#1F2937"
                fg_sub  = "#94A3B8" if is_dark else "#6B7280"
                fg_done = "#059669"
                bdr     = "#2D3748" if is_dark else "#E5E7EB"
                sec_bg  = "rgba(2,183,147,0.07)" if is_dark else "rgba(2,183,147,0.04)"

                # Strip YAML frontmatter
                body = re.sub(r"^---.*?---\n?", "", raw, flags=re.DOTALL).strip()
                # Split on ### BLOCO markers
                sections = re.split(r"###\s+BLOCO\s+(\w+)[^\n]*\n?", body)

                def _md_lines(text: str) -> str:
                    """Convert minimal markdown to HTML lines."""
                    out, in_ul = [], False
                    for ln in text.splitlines():
                        ln = ln.rstrip()
                        # Strip code-fence markers
                        if re.match(r"^~~~", ln):
                            continue
                        # Headings
                        if ln.startswith("## "):
                            if in_ul: out.append("</ul>"); in_ul = False
                            out.append(f'<h3 style="margin:10px 0 4px;font-size:13px;color:{fg_main}">'
                                       f'{_html.escape(ln[3:])}</h3>')
                            continue
                        if ln.startswith("### "):
                            if in_ul: out.append("</ul>"); in_ul = False
                            out.append(f'<h4 style="margin:8px 0 3px;font-size:12px;color:{fg_sub};'
                                       f'text-transform:uppercase;letter-spacing:.06em">'
                                       f'{_html.escape(ln[4:])}</h4>')
                            continue
                        # Action items
                        m_ai = re.match(r"- \[( |x)\] (.+)", ln)
                        if m_ai:
                            if not in_ul: out.append('<ul style="margin:2px 0;padding-left:18px">'); in_ul = True
                            done = m_ai.group(1) == "x"
                            icon = f'<span style="color:{fg_done}">✅</span>' if done else '⬜'
                            txt  = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>",
                                          _html.escape(m_ai.group(2)))
                            style = f'color:{fg_sub};text-decoration:line-through' if done else f'color:{fg_main}'
                            out.append(f'<li style="list-style:none;margin:2px 0;{style}">'
                                       f'{icon} {txt}</li>')
                            continue
                        # Bullets
                        m_ul = re.match(r"- (.+)", ln)
                        if m_ul:
                            if not in_ul: out.append('<ul style="margin:2px 0;padding-left:18px">'); in_ul = True
                            txt = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>",
                                         _html.escape(m_ul.group(1)))
                            out.append(f'<li style="color:{fg_main};margin:2px 0">{txt}</li>')
                            continue
                        # Blank line
                        if not ln.strip():
                            if in_ul: out.append("</ul>"); in_ul = False
                            out.append('<div style="height:6px"></div>')
                            continue
                        # Regular paragraph
                        if in_ul: out.append("</ul>"); in_ul = False
                        txt = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>",
                                     _html.escape(ln))
                        out.append(f'<p style="margin:3px 0;color:{fg_main}">{txt}</p>')
                    if in_ul:
                        out.append("</ul>")
                    return "\n".join(out)

                html_parts = []
                # No BLOCO structure — render as plain markdown
                if len(sections) <= 1:
                    html_parts.append(_md_lines(body))
                else:
                    # sections = ["pre-text", "SectionName", "content", ...]
                    for i in range(1, len(sections) - 1, 2):
                        sec_name = sections[i].strip()
                        sec_body = sections[i + 1].strip() if i + 1 < len(sections) else ""
                        html_parts.append(
                            f'<div style="margin-bottom:14px;padding:10px 14px;'
                            f'background:{sec_bg};border-left:3px solid {accent};border-radius:0 6px 6px 0">'
                            f'<div style="font-family:\'DM Mono\',monospace;font-size:10px;font-weight:600;'
                            f'letter-spacing:.14em;text-transform:uppercase;color:{accent};margin-bottom:8px">'
                            f'{_html.escape(sec_name)}</div>'
                            f'{_md_lines(sec_body)}'
                            f'</div>'
                        )

                content_html = "\n".join(html_parts)
                char_count   = len(re.sub(r"<[^>]+>", "", content_html))
                est_lines    = max(content_html.count("<li") + content_html.count("<p") +
                                   content_html.count("<h3") + content_html.count("<h4") +
                                   content_html.count("height:6px") + 4, 6)
                h_px = min(est_lines * 22 + 40, 520)

                full_html = (
                    f'<!DOCTYPE html><html><head><meta charset="utf-8"><style>'
                    f'*{{box-sizing:border-box}}html,body{{margin:0;padding:14px 16px;'
                    f'background:{bg};font-family:"Inter",sans-serif;font-size:13px;'
                    f'line-height:1.55;overflow-x:hidden}}'
                    f'strong{{color:{fg_main}}}'
                    f'</style></head><body>{content_html}</body></html>'
                )
                return full_html, h_px

            _call_bg = "#1A1D2E" if dark_mode else "#F9FAFB"
            for _c in sorted(_calls, key=lambda x: x["date"], reverse=True):
                _ck = f"wb_call_{_c['member']}_{_c['date'].isoformat()}"
                if _ck not in st.session_state:
                    st.session_state[_ck] = False
                _tcol, _hcol = st.columns([0.5, 11], vertical_alignment="center")
                if _tcol.button("▲" if st.session_state[_ck] else "▼",
                                key=f"wb_ct_{_c['member']}_{_c['date'].isoformat()}"):
                    st.session_state[_ck] = not st.session_state[_ck]
                    st.rerun()
                _hcol.markdown(f"📞 **{_c['member']}** — {_c['date'].strftime('%d/%m/%Y')}")
                if st.session_state[_ck]:
                    _raw  = _c["path"].read_text(encoding="utf-8", errors="replace")
                    _fhtml, _fh = _call_to_html(_raw[:4000], _call_bg, dark_mode)
                    _components.html(_fhtml, height=_fh, scrolling=False)
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
