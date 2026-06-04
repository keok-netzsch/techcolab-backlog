"""views/todo_list.py — To-Do List page (consolidated to-dos across all backlog ideas)."""

from datetime import date, timedelta
from itertools import groupby

import streamlit as st

from backlog.cache import get_store, load_ideas
from backlog.daily_log import log_entry
from components.ui import PRIORITY_LABEL, PRIORITY_NUM, STATUS_COLOR, pbadge, sdot


def _render_legend() -> None:
    col_p, col_s = st.columns([1, 2])
    from components.ui import STATUS_HEX, STATUS_LABEL
    with col_p:
        p3 = pbadge("3", "#1e293b")
        p2 = pbadge("2", "#64748b")
        p1 = pbadge("1", "#94a3b8")
        st.markdown(
            f"**Priority**  \n"
            f"{p3} High  \n"
            f"{p2} Medium  \n"
            f"{p1} Low",
            unsafe_allow_html=True,
        )
    with col_s:
        rows = " &nbsp;·&nbsp; ".join(
            f'{sdot(s, 9)} {STATUS_LABEL.get(s, s)}'
            for s in STATUS_HEX
        )
        st.markdown(f"**Status**  \n{rows}", unsafe_allow_html=True)


def render() -> None:
    dark_mode = st.query_params.get("dark", "1") == "1"

    st.markdown('<h1 style="margin-bottom:0.4rem">To-Do List</h1>', unsafe_allow_html=True)
    st.caption("All action items consolidated in one place. Check them off throughout the day.")
    with st.expander("📖 Legend", expanded=False):
        _render_legend()

    ideas = load_ideas()

    all_todos = []
    for idea in ideas:
        for idx, todo in enumerate(idea.todos):
            all_todos.append({
                "idea_id":    idea.id,
                "idea_title": idea.title,
                "priority":   idea.priority,
                "area":       idea.area or "—",
                "status":     idea.status,
                "is_bug":     todo.get("is_bug", False),
                "todo_idx":   idx,
                "text":       todo["text"],
                "done":       todo["done"],
                "in_progress": todo.get("in_progress", False),
                "due_date":   todo.get("due_date"),
                "completed_at": todo.get("completed_at"),
            })

    if not all_todos:
        st.info("No to-dos found. Add to-dos to ideas in the Backlog.")
        return

    col_a, col_b, col_c, col_d, _ = st.columns([1.5, 2.2, 1.6, 1.1, 1.6], vertical_alignment="bottom", gap="small")
    with col_a:
        areas = sorted(set(t["area"] for t in all_todos if t["area"] != "—"))
        filter_area = st.selectbox("Area", ["All"] + areas)
    with col_b:
        group_by = st.radio("Group by", ["Priority", "Idea", "Area", "Date"], index=3, horizontal=True)
    with col_c:
        show_filter = st.radio("Show", ["Pending", "Done", "All"], horizontal=True)
    with col_d:
        filter_bugs = st.checkbox("🐛 Bugs", value=False, key="tdl_bugs_only")

    filtered_todos = all_todos
    if show_filter == "Pending":
        filtered_todos = [t for t in filtered_todos if not t["done"]]
    elif show_filter == "Done":
        filtered_todos = [t for t in filtered_todos if t["done"]]
    if filter_area != "All":
        filtered_todos = [t for t in filtered_todos if t["area"] == filter_area]
    if filter_bugs:
        filtered_todos = [t for t in filtered_todos if t.get("is_bug")]

    prio_order = {"alta": 0, "média": 1, "baixa": 2}
    filtered_todos.sort(key=lambda t: (prio_order.get(t["priority"], 9), t["idea_id"]))

    pending_count    = sum(1 for t in filtered_todos if not t["done"])
    in_progress_count = sum(1 for t in filtered_todos if not t["done"] and t.get("in_progress"))
    done_count       = sum(1 for t in filtered_todos if t["done"])
    ip_badge = f" · **{in_progress_count} 🔄 in progress**" if in_progress_count else ""
    st.markdown(f"**{pending_count} pending**{ip_badge} · {done_count} done out of {len(filtered_todos)} shown")

    _tdl_num_bg  = "#1E293B" if dark_mode else "#F3F4F6"
    _tdl_num_clr = "#94A3B8" if dark_mode else "#6B7280"
    st.markdown(
        "<style>"
        f"div.tdl-num button {{"
        f" background:{_tdl_num_bg}!important; border:none!important; box-shadow:none!important;"
        " border-radius:4px!important; font-size:0.73rem!important; font-weight:700!important;"
        f" color:{_tdl_num_clr}!important; padding:1px 2px!important;"
        " min-height:22px!important; width:100%!important; }"
        "div.tdl-num button:hover {"
        " background:rgba(2,183,147,0.12)!important; color:#02B793!important; }"
        "div.tdl-sel div[data-testid='stSelectbox'] > div > div {"
        " min-height:26px!important; padding:1px 6px!important; font-size:0.82rem!important; }"
        "</style>",
        unsafe_allow_html=True,
    )

    _GROUP_DATA_ORDER = {"🔴 Overdue": 0, "📅 This week": 1, "📆 This month": 2, "🗓️ Upcoming": 3, "📭 No due date": 4}

    def _due_group(t) -> str:
        raw = t.get("due_date")
        if not raw:
            return "📭 No due date"
        try:
            due    = date.fromisoformat(raw)
            _today = date.today()
            week_end = _today + timedelta(days=(6 - _today.weekday()))
            if t.get("done"):
                completed_raw = t.get("completed_at")
                ref = date.fromisoformat(completed_raw) if completed_raw else due
                if ref > due:
                    return "🔴 Overdue"
                if due <= week_end:
                    return "📅 This week"
                elif due.month == _today.month and due.year == _today.year:
                    return "📆 This month"
                else:
                    return "🗓️ Upcoming"
            else:
                if due < _today:
                    return "🔴 Overdue"
                elif due <= week_end:
                    return "📅 This week"
                elif due.month == _today.month and due.year == _today.year:
                    return "📆 This month"
                else:
                    return "🗓️ Upcoming"
        except (ValueError, TypeError):
            return "📭 No due date"

    def get_group_key(t):
        if group_by == "Priority":
            return f"{PRIORITY_LABEL.get(t['priority'], t['priority'].title())}"
        elif group_by == "Idea":
            return f"💡 {t['idea_id']} — {t['idea_title']}"
        elif group_by == "Date":
            return _due_group(t)
        else:
            return f"🏷️ {t['area']}"

    if group_by == "Date":
        filtered_todos.sort(key=lambda t: (_GROUP_DATA_ORDER.get(_due_group(t), 9), t["idea_id"]))
    elif group_by == "Priority":
        filtered_todos.sort(key=lambda t: (prio_order.get(t["priority"], 9), t["idea_id"]))
    else:
        filtered_todos.sort(key=get_group_key)

    store = get_store()
    today = date.today()
    _idea_by_id = {i.id: i for i in ideas}  # lookup table — avoids per-row disk reads in the loop

    # In "Pending" filter, always include this-week done items (show as strikethrough)
    if show_filter == "Pending":
        this_week_done = [
            t for t in all_todos
            if t["done"] and _due_group(t) == "📅 This week"
            and (filter_area == "All" or t["area"] == filter_area)
            and (not filter_bugs or t.get("is_bug"))
        ]
        existing_keys = {(t["idea_id"], t["todo_idx"]) for t in filtered_todos}
        for t in this_week_done:
            if (t["idea_id"], t["todo_idx"]) not in existing_keys:
                filtered_todos.append(t)
        if group_by == "Date":
            filtered_todos.sort(key=lambda t: (_GROUP_DATA_ORDER.get(_due_group(t), 9), t["idea_id"]))
        elif group_by == "Priority":
            filtered_todos.sort(key=lambda t: (prio_order.get(t["priority"], 9), t["idea_id"]))
        else:
            filtered_todos.sort(key=get_group_key)

    # ── Sort state ─────────────────────────────────────────────────────────────
    for _k, _dv in [("tdl_sort_col", None), ("tdl_sort_dir", 1)]:
        if _k not in st.session_state:
            st.session_state[_k] = _dv
    _sc = st.session_state.get("tdl_sort_col")
    _sd = st.session_state.get("tdl_sort_dir", 1)

    _TDL_COLS = [0.06, 0.05, 0.04, 0.09, 0.62, 0.14]

    def _hdrbtn(label, col_name, widget_col):
        arr = (" ↑" if _sd == 1 else " ↓") if _sc == col_name else ""
        if widget_col.button(f"{label}{arr}", key=f"tdl_hdr_{col_name}", use_container_width=True):
            if _sc == col_name:
                st.session_state["tdl_sort_dir"] = -_sd
            else:
                st.session_state["tdl_sort_col"] = col_name
                st.session_state["tdl_sort_dir"] = 1
            st.rerun()

    _h1, _h2, _h3, _h4, _h5, _h6 = st.columns(_TDL_COLS)
    _hdrbtn("#", "id", _h1)
    _hdrbtn("Prio", "priority", _h2)
    _h3.caption("")
    _hdrbtn("Estado", "state", _h4)
    _hdrbtn("To-Do · Backlog item", "text", _h5)
    _hdrbtn("Prazo", "due_date", _h6)

    _STATE_OPTS = ["⬜", "🔄", "✅"]
    _STATE_IDX  = {"open": 0, "in_progress": 1, "done": 2}
    st.markdown(
        "<style>div[data-testid='stVerticalBlockBorderWrapper']"
        "{ height:calc(100vh - 360px)!important; }</style>",
        unsafe_allow_html=True,
    )
    with st.container(height=600):
        for group_label, group_items in groupby(filtered_todos, key=get_group_key):
            items = list(group_items)
            _todo_state_order = {"open": 0, "in_progress": 1, "done": 2}
            def _todo_state(t):
                return "done" if t["done"] else ("in_progress" if t.get("in_progress") else "open")
            if _sc == "id":
                items.sort(key=lambda t: t["idea_id"], reverse=(_sd == -1))
            elif _sc == "priority":
                items.sort(key=lambda t: prio_order.get(t["priority"], 9), reverse=(_sd == -1))
            elif _sc == "state":
                items.sort(key=lambda t: _todo_state_order.get(_todo_state(t), 0), reverse=(_sd == -1))
            elif _sc == "text":
                items.sort(key=lambda t: t["text"].lower(), reverse=(_sd == -1))
            elif _sc == "due_date":
                items.sort(key=lambda t: t.get("due_date") or "9999-12-31", reverse=(_sd == -1))

            st.markdown(
                f'<div style="font-size:0.78rem;font-weight:600;color:#6B7280;'
                f'padding:10px 0 2px 0;border-top:1px solid rgba(0,0,0,0.07);'
                f'margin-top:2px">{group_label}</div>',
                unsafe_allow_html=True,
            )

            for item in items:
                idea = _idea_by_id.get(item["idea_id"])  # reuse cached ideas, no per-row disk read
                if not idea:
                    continue

                c_id, c_prio, c_status, c_chk, c_text, c_info = st.columns(_TDL_COLS, vertical_alignment="center")

                short = str(int(item["idea_id"].replace("idea-", "")))
                with c_id:
                    st.markdown('<div class="tdl-num">', unsafe_allow_html=True)
                    if st.button(short, key=f"nav_{item['idea_id']}_{item['todo_idx']}",
                                 use_container_width=True):
                        st.session_state[f"exp_{item['idea_id']}"] = True
                        st.query_params["page"] = "Backlog"
                    st.markdown('</div>', unsafe_allow_html=True)

                c_prio.markdown(PRIORITY_NUM.get(item["priority"], "⚪"), unsafe_allow_html=True)
                c_status.markdown(STATUS_COLOR.get(item["status"], sdot("backlog")), unsafe_allow_html=True)

                cur_state = "done" if item["done"] else ("in_progress" if item.get("in_progress") else "open")
                with c_chk:
                    st.markdown('<div class="tdl-sel">', unsafe_allow_html=True)
                    sel = st.selectbox(
                        "", _STATE_OPTS,
                        index=_STATE_IDX[cur_state],
                        key=f"tdl_state_{item['idea_id']}_{item['todo_idx']}",
                        label_visibility="collapsed",
                    )
                    st.markdown('</div>', unsafe_allow_html=True)
                new_state   = ["open", "in_progress", "done"][_STATE_OPTS.index(sel)]
                state_clicked = new_state != cur_state

                with c_text:
                    if item["done"]:
                        text_html = f"<s>{item['text']}</s>"
                    elif item.get("in_progress"):
                        text_html = f"<em>{item['text']}</em>"
                    else:
                        text_html = item["text"]
                    _bug_bg  = "rgba(220,38,38,0.18)" if dark_mode else "#FEE2E2"
                    _bug_clr = "#F87171"              if dark_mode else "#B91C1C"
                    bug_badge = (
                        f' <span style="background:{_bug_bg};color:{_bug_clr};font-size:9px;font-weight:700;'
                        f'letter-spacing:.06em;padding:2px 5px;border-radius:3px;vertical-align:middle">BUG</span>'
                        if item.get("is_bug") else ""
                    )
                    _ref_code_bg  = "#1E293B" if dark_mode else "#F3F4F6"
                    _ref_code_clr = "#64748B" if dark_mode else "#6B7280"
                    _ref_txt_clr  = "#64748B" if dark_mode else "#9CA3AF"
                    idea_ref = (
                        f'<div style="font-size:0.72rem;color:{_ref_txt_clr};margin-top:1px">'
                        f'<code style="font-size:0.68rem;background:{_ref_code_bg};padding:0 3px;'
                        f'border-radius:2px;color:{_ref_code_clr}">{item["idea_id"]}</code>'
                        f'&nbsp;{item["idea_title"][:52]}</div>'
                    )
                    st.markdown(
                        f'<div style="font-size:0.87rem;line-height:1.35">{text_html}{bug_badge}{idea_ref}</div>',
                        unsafe_allow_html=True,
                    )

                with c_info:
                    due_str = ""
                    if item.get("due_date"):
                        try:
                            due = date.fromisoformat(item["due_date"])
                            if item["done"]:
                                completed_raw = item.get("completed_at")
                                ref = date.fromisoformat(completed_raw) if completed_raw else due
                                due_str = f"🔴 {due.strftime('%d/%m')}" if ref > due else f"✅ {due.strftime('%d/%m')}"
                            else:
                                if due < today:
                                    due_str = f"🔴 {due.strftime('%d/%m')}"
                                elif due == today:
                                    due_str = "🟡 hoje"
                                else:
                                    due_str = f"📅 {due.strftime('%d/%m')}"
                        except (ValueError, TypeError):
                            pass
                    st.caption(due_str)

                if state_clicked:
                    todo_entry = idea.todos[item["todo_idx"]]
                    todo_entry["done"]         = new_state == "done"
                    todo_entry["in_progress"]  = new_state == "in_progress"
                    todo_entry["completed_at"] = today.isoformat() if new_state == "done" else None
                    store.save(idea)
                    if new_state == "done":
                        log_entry("todo_concluido", idea, item["text"])
                    st.rerun()
