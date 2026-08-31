"""views/pendencias.py — Pending decisions page (the single "waiting on Kelvin" list).

The vault holds the record (Pendencias.md, generated); THIS page is where he
looks and acts — his stated model (2026-08-31): "vault apenas como camada de
registro, não como camada de interação". Resolving here writes through
agent/pending.py, which regenerates the vault view — the record stays in sync
without him ever opening it.
"""

from datetime import date

import streamlit as st

from agent import pending

_TYPE_LABEL = {
    "decisao": "Decide",
    "graduacao": "Graduate",
    "verificacao": "Verify",
}
_TYPE_COLOR = {
    "decisao": "#8a5a00",
    "graduacao": "#007167",
    "verificacao": "#6B7280",
}


def _age_days(iso: str) -> int:
    try:
        return (date.today() - date.fromisoformat(iso)).days
    except (ValueError, TypeError):
        return 0


def _age_color(days: int) -> str:
    # An old pendência has to be visually annoying — it is exactly the item the
    # old model (buried in some ADR) let disappear.
    if days < 7:
        return "#059669"
    if days <= 14:
        return "#b26a00"
    return "#EF4444"


def render() -> None:
    # Same convention as dashboard.py / claude_pro.py: theme comes via query param.
    dark = st.query_params.get("dark", "1") == "1"
    card_bg = "#1E2640" if dark else "#F9FAFB"
    card_border = "rgba(255,255,255,0.09)" if dark else "#E5E7EB"
    ink = "#E8EBEE" if dark else "#111827"
    muted = "#94A3B8" if dark else "#6B7280"
    faint = "#64748B" if dark else "#9CA3AF"

    st.markdown(
        '<h1 style="background:linear-gradient(90deg,#007167,#8AC6BD);'
        "-webkit-background-clip:text;-webkit-text-fill-color:transparent;"
        'letter-spacing:-0.02em">Pending on you</h1>',
        unsafe_allow_html=True,
    )

    data = pending._load()
    open_items = [i for i in data["itens"] if not i.get("resolvida_em")]
    resolved = sorted(
        [i for i in data["itens"] if i.get("resolvida_em")],
        key=lambda i: i["resolvida_em"],
        reverse=True,
    )

    st.caption(
        f"{len(open_items)} open · {len(resolved)} resolved · "
        "record mirrored to Pendencias.md in the vault (generated — no need to open it)"
    )

    if not open_items:
        st.markdown(
            f'<div style="color:{muted};font-size:1.05rem;padding:1.5rem 0">'
            "Nothing waiting on you.</div>",
            unsafe_allow_html=True,
        )
    for item in sorted(open_items, key=lambda i: i["criada_em"]):
        days = _age_days(item["criada_em"])
        acolor = _age_color(days)
        tcolor = _TYPE_COLOR.get(item["tipo"], "#6B7280")
        tlabel = _TYPE_LABEL.get(item["tipo"], item["tipo"])
        origem = (
            f'<div style="color:{faint};font-size:.75rem;margin-top:6px">{item["origem"]}</div>'
            if item.get("origem")
            else ""
        )
        left, right = st.columns([11, 2], vertical_alignment="center")
        with left:
            st.markdown(
                f'<div style="background:{card_bg};border:1px solid {card_border};'
                f"border-left:4px solid {acolor};border-radius:8px;"
                f'padding:12px 14px">'
                f'<span style="background:{tcolor};color:#fff;font-size:.65rem;'
                f"font-weight:600;letter-spacing:.05em;padding:2px 8px;"
                f'border-radius:4px;text-transform:uppercase">{tlabel}</span> '
                f'<span style="color:{muted};font-size:.75rem;font-family:monospace">'
                f'{item["id"]}</span> '
                f'<span style="color:{acolor};font-size:.75rem;font-weight:600;'
                f'float:right">{days}d</span>'
                f'<div style="color:{ink};font-size:.9rem;margin-top:8px">'
                f'{item["texto"]}</div>{origem}</div>',
                unsafe_allow_html=True,
            )
        with right:
            if st.button("Resolve", key=f"res-{item['id']}", use_container_width=True):
                st.session_state["resolving"] = item["id"]
        if st.session_state.get("resolving") == item["id"]:
            with st.form(key=f"form-{item['id']}", border=False):
                how = st.text_input(
                    "Resolution (optional)", key=f"how-{item['id']}",
                    placeholder="e.g. approved in conversation / not needed anymore",
                )
                a, b, _sp = st.columns([2, 2, 8])
                if a.form_submit_button("Confirm", type="primary"):
                    pending.main(["resolve", item["id"], "--como", how.strip()])
                    st.session_state.pop("resolving", None)
                    st.rerun()
                if b.form_submit_button("Cancel"):
                    st.session_state.pop("resolving", None)
                    st.rerun()

    if resolved:
        with st.expander(f"Resolved history ({len(resolved)})"):
            for item in resolved:
                how = f" → **{item['resolucao']}**" if item.get("resolucao") else ""
                st.markdown(
                    f"`{item['resolvida_em']}` · "
                    f"{_TYPE_LABEL.get(item['tipo'], item['tipo'])} · "
                    f"~~{item['texto']}~~{how}"
                )
