"""views/team.py — Team page (direct reports: 1:1 tracker, OKR/PDI, agenda gen)."""

import re
from datetime import date, timedelta

import streamlit as st

from backlog.cache import get_store, rebuild_index
from components.ui import stat_grid
from config import TEAM_DIR

_CADENCE_DAYS = 28
_MEMBERS = [
    {"name": "Ana Leite",     "folder": "Ana-Leite"},
    {"name": "Daniel Lima",   "folder": "Daniel-Lima"},
    {"name": "Lucas Shizuno", "folder": "Lucas-Shizuno"},
    {"name": "Pedro Hennig",  "folder": "Pedro-Hennig"},
    {"name": "Pedro Klein",   "folder": "Pedro-Klein"},
]


def _parse_1on1(path):
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    parts = re.split(r"^## (\d{4}-\d{2}-\d{2})\b", text, flags=re.MULTILINE)
    sessions = []
    for i in range(1, len(parts) - 1, 2):
        s_date, content = parts[i], parts[i + 1]
        topics, actions, in_t, in_a = [], [], False, False
        for line in content.splitlines():
            s = line.strip()
            if re.match(r"\*\*(T[oó]picos?|Topics?):?\*\*", s):
                in_t, in_a = True, False; continue
            if re.match(r"\*\*(Action [Ii]tems?|Ac[oõ]es?):?\*\*", s):
                in_t, in_a = False, True; continue
            if s.startswith("**") or s.startswith("---"):
                in_t = in_a = False
            if in_t and s.startswith("- "):
                topics.append(s[2:])
            if in_a and re.match(r"- \[[ x]\]", s):
                actions.append({"text": s[6:].strip(), "done": s[3] == "x"})
        sessions.append({"date": s_date, "topics": topics, "actions": actions})
    return sessions


def _all_dates(folder, sessions):
    dates = set()
    for s in sessions:
        try:
            dates.add(date.fromisoformat(s["date"]))
        except ValueError:
            pass
    sd = folder / "1on1"
    if sd.exists():
        for f in sd.glob("*.md"):
            if f.name.startswith("_"):
                continue
            try:
                dates.add(date.fromisoformat(f.stem[:10]))
            except ValueError:
                pass
    return sorted(dates, reverse=True)


def _parse_okr(path):
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    krs, cur_kr = [], None
    for line in text.splitlines():
        m = re.match(r"###\s+KR:\s+(.+)", line)
        if m:
            cur_kr = m.group(1).strip()
        elif cur_kr:
            ms = re.search(r"\*\*Status:\*\*\s*(.+)", line)
            if ms:
                krs.append((cur_kr, ms.group(1).strip()))
                cur_kr = None
    return krs


def _parse_pdi(path):
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    objs, cur_name, cur_dl, cur_prog = [], None, None, None
    for line in text.splitlines():
        m = re.match(r"###\s+(.+)", line)
        if m:
            if cur_name:
                objs.append((cur_name, cur_dl, cur_prog))
            cur_name = m.group(1).strip()
            cur_dl, cur_prog = None, None
        elif cur_name:
            md = re.search(r"\*\*Deadline:\*\*\s*(.+)", line)
            mp = re.search(r"\*\*Progress:\*\*\s*(\d+)%", line)
            if md:
                cur_dl = md.group(1).strip()
            if mp:
                cur_prog = int(mp.group(1))
    if cur_name:
        objs.append((cur_name, cur_dl, cur_prog))
    return objs


def _parse_role(path):
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"\*\*Role:\*\*\s*(.+)", text)
    return m.group(1).strip() if m else ""


def render() -> None:
    st.markdown('<h1 style="margin-bottom:0.4rem">Team</h1>', unsafe_allow_html=True)
    st.caption("Direct reports — 1:1 tracker, OKR / PDI status, and agenda prep.")

    if not TEAM_DIR.exists():
        st.info("Team folder not found. Check TEAM_DIR in config.py.")
        return

    _member_names = [m["name"] for m in _MEMBERS]
    _selected = st.selectbox(
        "Team member",
        [""] + _member_names,
        format_func=lambda x: "Select a team member…" if x == "" else x,
        key="team_selected_member",
    )
    if not _selected:
        st.caption("Select a team member above to view their details.")
        return

    for _tm in [m for m in _MEMBERS if m["name"] == _selected]:
        _folder = TEAM_DIR / _tm["folder"]
        _sess   = _parse_1on1(_folder / "1on1.md")
        _dates  = _all_dates(_folder, _sess)
        _last   = _dates[0] if _dates else None
        _count  = len(_dates)
        _next   = (_last + timedelta(days=_CADENCE_DAYS)) if _last else None
        _days   = (_next - date.today()).days if _next else None
        _role   = _parse_role(_folder / "Overview.md")
        _krs    = _parse_okr(_folder / "OKR.md")
        _pdi    = _parse_pdi(_folder / "PDI.md")

        with st.expander(
            f"**{_tm['name']}**" + (f" — {_role}" if _role else ""),
            expanded=True,
        ):
            _last_str = _last.strftime("%d/%m/%Y") if _last else "—"
            _next_str = _next.strftime("%d/%m/%Y") if _next else "—"
            _next_c   = "#111827"
            if _days is not None:
                _next_c = "#EF4444" if _days <= 0 else ("#F59E0B" if _days <= 7 else "#111827")
            _pdi_s = f"{len(_pdi)} active" if _pdi else "—"

            st.markdown(
                stat_grid([
                    {"label": "Last 1:1", "value": _last_str},
                    {"label": "Total sessions", "value": _count},
                    {"label": "Next 1:1 (4-week)", "value": _next_str, "color": _next_c},
                    {"label": "PDI", "value": _pdi_s},
                ], columns=4),
                unsafe_allow_html=True,
            )

            if _days is not None and _days <= 7:
                _ac = "#EF4444" if _days <= 0 else "#F59E0B"
                _al = "Overdue" if _days <= 0 else "Due soon"
                _am = (
                    f"Structured 1:1 was due {abs(_days)}d ago ({_next_str}). Schedule now."
                    if _days <= 0
                    else f"Structured 1:1 due in {_days}d ({_next_str}). Plan the agenda."
                )
                st.markdown(
                    f'<div style="margin:.4rem 0;padding:.5rem .75rem;border-radius:6px;'
                    f'border-left:3px solid {_ac};background:rgba(245,158,11,.07)">'
                    f'<span style="font-size:.7rem;color:{_ac};font-weight:700;'
                    f'text-transform:uppercase;letter-spacing:.04em">{_al}</span>'
                    f'<br><span style="font-size:.82rem">{_am}</span></div>',
                    unsafe_allow_html=True,
                )

            if _sess:
                _lat = _sess[0]
                st.caption(f"Last session: {_lat['date']}")
                if _lat["topics"]:
                    st.markdown("**Topics:**")
                    for _t in _lat["topics"][:5]:
                        st.markdown(f"  - {_t}")
                _open_ai = [a for a in _lat["actions"] if not a["done"]]
                if _open_ai:
                    st.markdown("**Open action items:**")
                    for _ai_idx, _a in enumerate(_open_ai[:6]):
                        _ai_col, _ai_btn_col = st.columns([10, 1], vertical_alignment="center")
                        _ai_col.markdown(f"  - ☐ {_a['text']}")
                        _btn_key = f"ai_to_bl_{_tm['folder']}_{_ai_idx}"
                        if _ai_btn_col.button("➕", key=_btn_key, help="Add to backlog"):
                            _new = get_store().create(
                                title=_a["text"],
                                description=f"Action item from 1:1 with {_tm['name']} on {_lat['date']}.",
                                origin=f"team/{_tm['folder']}/1on1",
                            )
                            rebuild_index()
                            st.toast(f"Added to backlog: {_new.id}", icon="✅")
            else:
                st.caption("No 1:1 sessions recorded.")

            if _pdi:
                with st.expander("PDI objectives", expanded=False):
                    for _pn, _pd, _pp in _pdi:
                        _prog = f"{_pp}%" if _pp is not None else "—"
                        st.markdown(f"- **{_pn}** — progress: {_prog} · deadline: {_pd or '—'}")

            if _krs:
                with st.expander("OKR", expanded=False):
                    for _kr_name, _kr_status in _krs:
                        st.markdown(f"- **{_kr_name}** — {_kr_status}")

            # Agenda is pre-generated by the daily agent (Team/{folder}/next-agenda.md);
            # the tab just displays it. "Regenerate" recomputes on demand via Ollama.
            from team_agenda import read_agenda, write_agenda
            _ag = read_agenda(_tm["folder"])
            if _ag:
                _gen_date, _ag_body = _ag
                st.markdown(f"**Suggested agenda**  ·  _generated {_gen_date}_")
                st.markdown(_ag_body)
            else:
                st.caption("No agenda generated yet — the daily agent creates it, or regenerate now.")
            if st.button("🔄 Regenerate agenda", key=f"tm_btn_{_tm['folder']}"):
                with st.spinner("Generating agenda via Ollama…"):
                    try:
                        write_agenda(_tm["folder"], _tm["name"])
                        st.rerun()
                    except Exception as _e:
                        st.error(f"Ollama error: {_e}")
