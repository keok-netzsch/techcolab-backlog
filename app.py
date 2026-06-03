"""
Personal Toolkit · Techco.lab — Streamlit UI
Run with: streamlit run app.py
"""

import json
import sys
from datetime import date
from pathlib import Path

import requests
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from backlog.daily_log import log_entry
from backlog.schema import VALID_AREAS, VALID_EFFORTS, VALID_IMPACTS, VALID_PRIORITIES, VALID_STATUSES
from backlog.store import BacklogStore
from config import (
    BACKLOG_ARCHIVE_DIR,
    BACKLOG_DIR,
    EXTRACTION_MODEL,
    OLLAMA_BASE_URL,
    VAULT_ROOT,
)

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Personal Toolkit · Techco.lab",
    page_icon="🤖",
    layout="wide",
)

# ── Dark mode (default ON; pass ?dark=0 to switch to light) ───────────────────
_dark_mode = st.query_params.get("dark", "1") == "1"

# ── Brand identity (logo + CSS loaded from assets/) ─────────────────────────────
_ASSETS_DIR = Path(__file__).parent / "assets"
_LOGO_GREEN = (_ASSETS_DIR / "logo.svg").read_text(encoding="utf-8")
_BRAND_CSS = "<style>\n" + (_ASSETS_DIR / "brand.css").read_text(encoding="utf-8") + "\n</style>"

_DARK_CSS = """
<style>
/* ── Dark mode ─────────────────────────────────────────────────────────────── */
html, body { background-color: #0E1117 !important; color: #E2E8F0 !important; }
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
[data-testid="stMainBlockContainer"] { background-color: #0E1117 !important; }

/* Column containers */
[data-testid="stColumn"] { background-color: #0E1117; }

/* Custom stat cards */
.cc-sc { background: #1A1D2E !important; border-color: #2D3748 !important; }
.cc-sl { color: #94A3B8 !important; }
.cc-sv { color: #E2E8F0 !important; }

/* Text */
.stMarkdown p, .stMarkdown span, .stMarkdown li { color: #E2E8F0 !important; }
[data-testid="stCaption"] p { color: #94A3B8 !important; }
h2, h3, h4 { color: #E2E8F0 !important; }

/* Inputs */
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea {
    background: #1A1D2E !important;
    border-color: #2D3748 !important;
    color: #E2E8F0 !important;
}
/* Disabled inputs (read-only paths) */
[data-testid="stTextInput"] input:disabled {
    background: #161B2E !important;
    border-color: #2D3748 !important;
    color: #64748B !important;
    -webkit-text-fill-color: #64748B !important;
    opacity: 1 !important;
}
/* Disabled text area used as read-only preview — keep full legibility */
[data-testid="stTextArea"] textarea:disabled {
    background: #161B2E !important;
    border-color: #2D3748 !important;
    color: #CBD5E0 !important;
    -webkit-text-fill-color: #CBD5E0 !important;
    opacity: 1 !important;
    font-family: monospace !important;
    font-size: 0.82rem !important;
    line-height: 1.6 !important;
    resize: none !important;
}
/* Input / selectbox labels */
[data-testid="stTextInput"] label p,
[data-testid="stTextArea"] label p,
[data-testid="stSelectbox"] label p,
[data-testid="stMultiSelect"] label p,
[data-testid="stDateInput"] label p,
[data-testid="stNumberInput"] label p,
[data-testid="stSlider"] label p { color: #64748B !important; }
[data-testid="stSelectbox"] > div > div,
[data-testid="stMultiSelect"] > div > div {
    background: #1A1D2E !important;
    border-color: #2D3748 !important;
    color: #E2E8F0 !important;
}
[data-testid="stDateInput"] input {
    background: #1A1D2E !important;
    border-color: #2D3748 !important;
    color: #E2E8F0 !important;
}

/* General secondary buttons — Streamlit 1.49 selector */
button[data-testid="stBaseButton-secondary"] {
    background: #1A1D2E !important;
    border-color: #2D3748 !important;
    color: #E2E8F0 !important;
    text-align: left !important;
    justify-content: flex-start !important;
}
button[data-testid="stBaseButton-secondary"]:hover {
    background: #1E2640 !important;
    border-color: #02B793 !important;
}

/* Row buttons inside columns — transparent, borderless */
[data-testid="stColumn"] button[data-testid="stBaseButton-secondary"] {
    background: transparent !important;
    border: none !important;
    color: #CBD5E0 !important;
}
[data-testid="stColumn"] button[data-testid="stBaseButton-secondary"]:hover {
    background: rgba(2,183,147,0.1) !important;
    color: #0AD4A8 !important;
    border: none !important;
}

/* Sidebar footer icon buttons */
.sidebar-footer button {
    color: rgba(200,210,220,0.45) !important;
    border-color: rgba(200,210,220,0.12) !important;
}

/* Dividers */
hr { border-color: #2D3748 !important; }

/* Expanders */
[data-testid="stExpander"] { background: #1A1D2E !important; border-color: #2D3748 !important; }
[data-testid="stExpander"] summary { color: #E2E8F0 !important; background: #1A1D2E !important; }
[data-testid="stExpander"] summary:hover { background: #1E2640 !important; }
[data-testid="stExpanderDetails"] { background: #1A1D2E !important; padding-bottom: 0.75rem !important; }
/* stVerticalBlock inside expanders must be transparent so parent bg (#1A1D2E) shows */
[data-testid="stExpanderDetails"] [data-testid="stVerticalBlock"],
[data-testid="stExpanderDetails"] [data-testid="stVerticalBlock"] > div { background: transparent !important; }
/* Ensure last markdown element has breathing room */
[data-testid="stExpanderDetails"] [data-testid="stMarkdownContainer"]:last-child { margin-bottom: 0.5rem !important; }
.cp-body-ul { margin-bottom: 0.5rem !important; }

/* Alerts / Notifications */
[data-testid="stNotification"] { background: #1A1D2E !important; border-color: #2D3748 !important; }

/* Labels on checkboxes/radios */
[data-testid="stCheckbox"] label p,
[data-testid="stRadio"] label p { color: #E2E8F0 !important; }

/* Radio button circle (unselected = dark bg, selected = accent) */
[data-testid="stRadio"] [role="radio"] {
    background: #1A1D2E !important;
    border-color: #4B5563 !important;
}
[data-testid="stRadio"] [role="radio"][aria-checked="true"] {
    background: #02B793 !important;
    border-color: #02B793 !important;
}

/* Progress bar track */
[data-testid="stProgressBar"] > div {
    background: #1E293B !important;
    border-radius: 999px !important;
}

/* Inline code badges */
code { background: #2D3748 !important; color: #E2E8F0 !important; }

/* ── Claude Pro page dark overrides ─────────────────────────────────────── */
.cp-stat-box   { background: #1A1D2E !important; border-color: #2D3748 !important; }
.cp-stat-lbl   { color: #94A3B8 !important; }
.cp-sect-lbl   { color: #64748B !important; }
.cp-sect-lbl::after { background: #2D3748 !important; }
.cp-exec       { background: rgba(2,183,147,0.06) !important; border-color: rgba(2,183,147,0.2) !important; }
.cp-exec-lead  { color: #E2E8F0 !important; }
.cp-exec-grid li       { color: #CBD5E0 !important; }
.cp-exec-grid li strong{ color: #E2E8F0 !important; }
.cp-boss       { background: rgba(2,183,147,0.06) !important; }
.cp-boss-p     { color: #CBD5E0 !important; }
.cp-boss-adv   { color: #94A3B8 !important; }
.cp-body-ul li { color: #94A3B8 !important; }
.cp-body-ul li::before { background: #475569 !important; }
.cp-badge-cat  { background: rgba(148,163,184,0.1) !important; color: #94A3B8 !important; }
.cp-badge-prog { background: rgba(245,158,11,0.1) !important; color: #F59E0B !important; }
.cp-badge-done { background: rgba(2,183,147,0.1) !important; }
.cp-tl-date    { color: #64748B !important; }
.cp-tl-title   { color: #E2E8F0 !important; }
.cp-tl-detail  { color: #94A3B8 !important; }
.cp-tl-wrap::before { background: #2D3748 !important; }
.cp-tl-item::before { border-color: #0E1117 !important; }
.cp-tools-tbl th { background: #161B2E !important; border-color: #2D3748 !important; color: #64748B !important; }
.cp-tools-tbl td { background: #1A1D2E !important; border-color: #2D3748 !important; }
.cp-tool-name  { color: #E2E8F0 !important; }
.cp-tool-sub   { color: #94A3B8 !important; }

/* Calendar: all overrides are handled inside _cal_css (dark-mode aware Python) */

/* Scrollbars */
::-webkit-scrollbar { background: #161B2E; width: 6px; }
::-webkit-scrollbar-thumb { background: #2D3748; border-radius: 4px; }

/* ── Markdown tables (exclude calendar — .cal-td/.cal-th handled by _cal_css) */
[data-testid="stMarkdownContainer"] table:not(.cal-tbl) { background: #1A1D2E !important; width: 100% !important; }
[data-testid="stMarkdownContainer"] th:not(.cal-th) {
    background: #161B2E !important; color: #64748B !important;
    border: 1px solid #2D3748 !important; padding: 8px 12px !important;
}
[data-testid="stMarkdownContainer"] td:not(.cal-td) {
    background: #1A1D2E !important; color: #CBD5E0 !important;
    border: 1px solid #2D3748 !important; padding: 8px 12px !important;
}
[data-testid="stMarkdownContainer"] tr:hover td:not(.cal-td) { background: #1E2640 !important; }
[data-testid="stMarkdownContainer"] blockquote {
    border-left: 4px solid #2D3748 !important;
    background: rgba(45,55,72,0.25) !important; color: #94A3B8 !important;
    padding: 6px 12px !important; border-radius: 0 4px 4px 0 !important;
}

/* ── Code blocks (markdown fences + st.code) ─────────────────────────────── */
[data-testid="stMarkdownContainer"] pre {
    background: #161B2E !important; border: 1px solid #2D3748 !important;
    border-radius: 6px !important;
}
[data-testid="stMarkdownContainer"] pre code {
    background: transparent !important; color: #E2E8F0 !important;
}
[data-testid="stCode"] > div,
[data-testid="stCode"] pre { background: #161B2E !important; border: 1px solid #2D3748 !important; }
[data-testid="stCode"] code { color: #E2E8F0 !important; background: transparent !important; }

/* ── st.json() ───────────────────────────────────────────────────────────── */
[data-testid="stJson"],
.stJson,
[data-testid="stJson"] > div,
[data-testid="stJson"] > div > div { background: #161B2E !important; border: 1px solid #2D3748 !important; border-radius: 6px !important; }
[data-testid="stJson"] span,
[data-testid="stJson"] p,
[data-testid="stJson"] div { color: #CBD5E0 !important; background: transparent !important; }
/* Streamlit JSON tree (uses jsonFormatted class) */
.jsonFormatted,
.jsonFormatted > div { background: #161B2E !important; color: #CBD5E0 !important; }

/* ── st.info / st.warning banners ────────────────────────────────────────── */
[data-testid="stNotification"] { background: #1A1D2E !important; border-color: #2D3748 !important; color: #CBD5E0 !important; }
[data-testid="stNotification"] a { color: #02B793 !important; }
</style>
"""

st.markdown(_BRAND_CSS, unsafe_allow_html=True)
if _dark_mode:
    st.markdown(_DARK_CSS, unsafe_allow_html=True)
# Favicon: base64-encoded SVG (raw angle brackets in data URIs break the HTML parser)
_FAVICON_B64 = "PHN2ZyB4bWxucz0naHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmcnIHZpZXdCb3g9JzAgMCAzMiAzMic+PHJlY3Qgd2lkdGg9JzMyJyBoZWlnaHQ9JzMyJyByeD0nNicgZmlsbD0nIzAyQjc5MycvPjx0ZXh0IHg9JzE2JyB5PScyMicgdGV4dC1hbmNob3I9J21pZGRsZScgZm9udC1mYW1pbHk9J0ludGVyLHNhbnMtc2VyaWYnIGZvbnQtc2l6ZT0nMTQnIGZvbnQtd2VpZ2h0PSc3MDAnIGZpbGw9J3doaXRlJz50YzwvdGV4dD48L3N2Zz4="
st.markdown(
    f'<link rel="shortcut icon" href="data:image/svg+xml;base64,{_FAVICON_B64}" type="image/svg+xml">',
    unsafe_allow_html=True,
)

# ── Top navigation (pure HTML — full height control) ───────────────────────
_PAGES_MAIN = ["Dashboard", "Backlog", "To-Do List", "Team", "Claude Pro", "Weekly Brief", "English Coach"]
_ALL_PAGES  = _PAGES_MAIN + ["FAQ", "Tutorial", "Documentation", "Settings"]

_qpage = st.query_params.get("page", "Dashboard")
if _qpage not in _ALL_PAGES:
    _qpage = "Dashboard"
page = _qpage

_LOGO_NAV = _LOGO_GREEN.replace('width="140" height="44"', 'width="88" height="27"')

_nav_text_color    = "#94A3B8" if _dark_mode else "#4C4D58"
_nav_active_color  = "#02B793" if _dark_mode else "#007167"
_nav_active_bg     = "#1E2640"  if _dark_mode else "rgba(2,183,147,0.14)"
_nav_bg            = "#161B2E" if _dark_mode else "#FFFFFF"
_nav_border        = "rgba(255,255,255,0.07)" if _dark_mode else "rgba(0,0,0,0.09)"

_BTN_BASE = (
    "display:inline-flex;align-items:center;padding:3px 10px;border-radius:6px;"
    "font-size:0.79rem;font-family:Inter,sans-serif;white-space:nowrap;"
    "cursor:pointer;border:none;outline:none;background:transparent;"
)

def _navlink(label: str, key: str) -> str:
    _a = key == page
    _s = (
        f"background:{_nav_active_bg};color:{_nav_active_color};font-weight:600;"
        if _a else
        f"color:{_nav_text_color};"
    )
    _dk = f'<input type="hidden" name="dark" value="{"1" if _dark_mode else "0"}">'
    return (
        f'<form method="get" action="" style="display:inline-block;margin:0;padding:0">'
        f'<input type="hidden" name="page" value="{key}">'
        f'{_dk}'
        f'<button type="submit" style="{_BTN_BASE}{_s}">{label}</button></form>'
    )

def _dark_toggle() -> str:
    _next        = "0" if _dark_mode else "1"
    _track_bg    = "#02B793"  if _dark_mode else "#D1D5DB"
    _thumb_left  = "19px"     if _dark_mode else "2px"
    _icon        = "☀️"       if _dark_mode else "🌙"
    return (
        f'<form method="get" action="" style="display:inline-flex;align-items:center;'
        f'margin:0 6px;padding:0;vertical-align:middle">'
        f'<input type="hidden" name="page" value="{page}">'
        f'<input type="hidden" name="dark" value="{_next}">'
        f'<button type="submit" title="Toggle dark mode" style="'
        f'position:relative;width:38px;height:20px;border-radius:10px;border:none;'
        f'outline:none;cursor:pointer;padding:0;background:{_track_bg};'
        f'transition:background .2s;flex-shrink:0;">'
        f'<span style="position:absolute;top:2px;left:{_thumb_left};'
        f'width:16px;height:16px;border-radius:50%;background:#fff;'
        f'display:inline-flex;align-items:center;justify-content:center;'
        f'font-size:9px;line-height:1;transition:left .15s;">{_icon}</span>'
        f'</button></form>'
    )

_nav_items  = "".join(_navlink(p, p) for p in _PAGES_MAIN)
_nav_extras = (
    _navlink("❓", "FAQ") +
    _navlink("📖", "Tutorial") +
    _navlink("📚", "Documentation") +
    _navlink("⚙️", "Settings") +
    _dark_toggle() +
    _navlink("🔄", page)
)

st.markdown(
    f'<nav style="display:flex;align-items:center;padding:5px 16px;background:{_nav_bg};'
    f'border-bottom:1px solid {_nav_border};gap:2px;margin-bottom:0.9rem">'
    f'<div style="line-height:0;margin-right:14px;flex-shrink:0">{_LOGO_NAV}</div>'
    f'{_nav_items}'
    f'<div style="flex:1"></div>'
    f'{_nav_extras}'
    f'</nav>',
    unsafe_allow_html=True,
)

PRIORITY_ICON = {"alta": "⭐⭐⭐", "média": "⭐⭐", "baixa": "⭐"}

def _pbadge(n: str, bg: str, fg: str = "#fff") -> str:
    return (
        f'<span style="display:inline-flex;align-items:center;justify-content:center;'
        f'width:1.25rem;height:1.25rem;border-radius:50%;background:{bg};color:{fg};'
        f'font-weight:800;font-size:0.65rem;font-family:Georgia,serif;vertical-align:middle">{n}</span>'
    )

PRIORITY_NUM = {
    "alta":  _pbadge("3", "#1e293b"),
    "média": _pbadge("2", "#64748b"),
    "baixa": _pbadge("1", "#94a3b8"),
}
STATUS_HEX = {
    "backlog":                    "#9CA3AF",
    "em análise":                 "#8B5CF6",
    "análise - aprovado":         "#02B793",
    "análise - rejeitado":        "#EF4444",
    "aguardando desenvolvimento": "#F59E0B",
    "em desenvolvimento":         "#F97316",
    "em validação":               "#3B82F6",
    "concluído":                  "#059669",
    "descartado":                 "#6B7280",
}

def _sdot(status: str, size: int = 10) -> str:
    color = STATUS_HEX.get(status, "#9CA3AF")
    return (
        f'<span style="display:inline-block;width:{size}px;height:{size}px;'
        f'border-radius:50%;background:{color};vertical-align:middle"></span>'
    )

STATUS_COLOR = {k: _sdot(k) for k in STATUS_HEX}
STATUS_LABEL = {
    "backlog": "Backlog",
    "em análise": "Under review",
    "análise - aprovado": "Approved",
    "análise - rejeitado": "Rejected",
    "aguardando desenvolvimento": "Waiting",
    "em desenvolvimento": "In development",
    "em validação": "In validation",
    "concluído": "Done",
    "descartado": "Discarded",
}
PRIORITY_LABEL = {"alta": "High", "média": "Medium", "baixa": "Low"}
IMPACT_LABEL = {"alta": "High", "média": "Medium", "baixa": "Low"}
EFFORT_LABEL = {"alto": "High", "médio": "Medium", "baixo": "Low"}
AREA_LABEL = {
    "produto": "Product",
    "dados & IA": "Data & AI",
    "automação": "Automation",
    "gestão": "Management",
    "governança": "Governance",
    "infraestrutura": "Infrastructure",
    "comunicação": "Communication",
    "business": "Business",
}

def _area_chip(area: str | None) -> str:
    """Compact muted chip for the backlog area column."""
    if not area:
        return '<span style="color:#9CA3AF;font-size:0.78rem">—</span>'
    label = AREA_LABEL.get(area, area.title())
    return (
        f'<span style="display:inline-block;font-size:0.72rem;font-weight:600;'
        f'color:#64748B;background:rgba(100,116,139,0.12);padding:2px 8px;'
        f'border-radius:10px;white-space:nowrap">{label}</span>'
    )

# ── Store ─────────────────────────────────────────────────────────────────────
def get_store() -> BacklogStore:
    return BacklogStore(Path(BACKLOG_DIR))

def _backlog_mtime() -> float:
    """Latest modification time across backlog files — used as a cache key.
    Changes whenever any idea-NNN.md is added, removed, or edited."""
    try:
        return max((f.stat().st_mtime for f in Path(BACKLOG_DIR).glob("*.md")), default=0.0)
    except OSError:
        return 0.0

@st.cache_data(show_spinner=False)
def _load_ideas_cached(cache_key: float):
    # cache_key (the backlog dir mtime) is hashed by Streamlit; when it changes
    # the list is recomputed, so edits/saves are reflected without stale reads.
    return get_store().load_all()

def load_ideas():
    return _load_ideas_cached(_backlog_mtime())

def _rebuild_index(store: BacklogStore) -> None:
    from backlog.index import generate_index
    from config import BACKLOG_INDEX
    generate_index(store.load_all(), Path(BACKLOG_INDEX))


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1 — BACKLOG
# ══════════════════════════════════════════════════════════════════════════════
def _render_legend():
    col_p, col_s = st.columns([1, 2])
    with col_p:
        p3 = _pbadge("3", "#1e293b")
        p2 = _pbadge("2", "#64748b")
        p1 = _pbadge("1", "#94a3b8")
        st.markdown(
            f"**Priority**  \n"
            f"{p3} High  \n"
            f"{p2} Medium  \n"
            f"{p1} Low",
            unsafe_allow_html=True,
        )
    with col_s:
        rows = " &nbsp;·&nbsp; ".join(
            f'{_sdot(s, 9)} {STATUS_LABEL.get(s, s)}'
            for s in STATUS_HEX
        )
        st.markdown(f"**Status**  \n{rows}", unsafe_allow_html=True)

def _similar_ideas(title: str, ideas: list, threshold: float = 0.45) -> list:
    from difflib import SequenceMatcher
    t = title.lower().strip()
    if not t:
        return []
    matches = []
    for idea in ideas:
        ratio = SequenceMatcher(None, t, idea.title.lower()).ratio()
        if ratio >= threshold:
            matches.append((idea, ratio))
    return sorted(matches, key=lambda x: -x[1])


if page == "Backlog":
    st.markdown(
        '<h1 style="margin-bottom:0.4rem">Idea Backlog</h1>',
        unsafe_allow_html=True,
    )

    # ── Flash messages ──────────────────────────────────────────────────────────
    if "backlog_flash" in st.session_state:
        kind, msg = st.session_state.pop("backlog_flash")
        if kind == "success":
            st.success(msg)
        else:
            st.error(msg)

    # ── Toolbar: 3 botões lado a lado, painel abre abaixo ──────────────────────
    st.markdown(
        "<style>div[data-testid='stButton'] > button { white-space: nowrap !important; }</style>",
        unsafe_allow_html=True,
    )
    if "backlog_panel" not in st.session_state:
        st.session_state["backlog_panel"] = None

    def _toggle_panel(name: str):
        st.session_state["backlog_panel"] = None if st.session_state["backlog_panel"] == name else name

    _panel = st.session_state["backlog_panel"]
    _tb1, _tb2, _tb3, _ = st.columns([2.5, 2, 2, 3.5])

    with _tb1:
        _active = _panel == "legenda"
        if st.button(
            "📖 Legend" + (" ▲" if _active else " ▼"),
            key="tb_legenda",
            type="primary" if _active else "secondary",
        ):
            _toggle_panel("legenda"); st.rerun()

    with _tb2:
        _active = _panel == "nova"
        if st.button(
            "➕ New" + (" ▲" if _active else " ▼"),
            key="tb_nova",
            type="primary" if _active else "secondary",
        ):
            _toggle_panel("nova"); st.rerun()

    with _tb3:
        _active = _panel == "bulk"
        if st.button(
            "⚡ Bulk" + (" ▲" if _active else " ▼"),
            key="tb_bulk",
            type="primary" if _active else "secondary",
        ):
            _toggle_panel("bulk"); st.rerun()

    # ── Conteúdo do painel ──────────────────────────────────────────────────────
    if st.session_state["backlog_panel"] == "legenda":
        with st.container(border=True):
            _render_legend()

    elif st.session_state["backlog_panel"] == "nova":
        with st.container(border=True):
            ni_title = st.text_input("Title *", placeholder="Short name for the idea", key="ni_title")

            if ni_title.strip():
                similares = _similar_ideas(ni_title, load_ideas())
                if similares:
                    st.warning(
                        "**Possible duplicate** — ideas with a similar title already exist:  \n"
                        + "  \n".join(f"• `{i.id}` — {i.title} *(similarity: {r:.0%})*" for i, r in similares[:3])
                    )
            ni_col1, ni_col2 = st.columns(2)
            with ni_col1:
                ni_area = st.selectbox("Area", [""] + VALID_AREAS, index=0, key="ni_area",
                                       format_func=lambda x: AREA_LABEL.get(x, x) if x else "— select —")
                ni_priority = st.selectbox("Priority", VALID_PRIORITIES, index=1, key="ni_priority",
                                           format_func=lambda x: PRIORITY_LABEL.get(x, x))
            with ni_col2:
                ni_impact = st.selectbox("Impact", [""] + VALID_IMPACTS, index=0, key="ni_impact",
                                         format_func=lambda x: IMPACT_LABEL.get(x, x) if x else "")
                ni_effort = st.selectbox("Effort", [""] + VALID_EFFORTS, index=0, key="ni_effort",
                                         format_func=lambda x: EFFORT_LABEL.get(x, x) if x else "")
            ni_desc = st.text_area("Description", height=80, placeholder="Context, motivation, details...", key="ni_desc")

            btn_col1, btn_col2, _ = st.columns([2, 2, 3])
            with btn_col1:
                if st.button("✨ Suggest to-dos", disabled=not ni_title.strip(), help="Uses the local model to suggest next steps"):
                    from ingestion.extractor import build_client, suggest_todos
                    with st.spinner("Generating suggestions..."):
                        try:
                            suggestions = suggest_todos(ni_title.strip(), ni_desc.strip(), build_client())
                            st.session_state["ni_suggested_todos"] = suggestions
                        except Exception as e:
                            st.error(f"Error connecting to Ollama: {e}")
            with btn_col2:
                if st.button("✨ Suggest priority", disabled=not ni_title.strip(), help="Suggests priority based on title and description"):
                    from ingestion.extractor import build_client
                    with st.spinner("Analysing..."):
                        try:
                            client = build_client()
                            prompt = (
                                f"Title: {ni_title.strip()}\nDescription: {ni_desc.strip() or '(no description)'}\n\n"
                                "What is the priority of this idea? Respond ONLY with one of: alta, média, baixa."
                            )
                            resp = client.chat.completions.create(
                                model=EXTRACTION_MODEL, max_tokens=10,
                                messages=[
                                    {"role": "system", "content": "Você é um assistente de gestão de produto."},
                                    {"role": "user", "content": prompt},
                                ],
                            )
                            suggested_prio = resp.choices[0].message.content.strip().lower()
                            if suggested_prio in VALID_PRIORITIES:
                                st.session_state["ni_priority"] = suggested_prio
                                st.session_state["ni_suggested_prio"] = suggested_prio
                            else:
                                st.warning(f"Unexpected response: {suggested_prio}")
                        except Exception as e:
                            st.error(f"Error: {e}")

            if "ni_suggested_prio" in st.session_state:
                prio = st.session_state.pop("ni_suggested_prio")
                st.info(f"Suggested priority: {PRIORITY_ICON.get(prio, '⚪')} **{PRIORITY_LABEL.get(prio, prio)}**")

            suggested = st.session_state.get("ni_suggested_todos", [])
            ni_todos: list[dict] = []
            if suggested:
                st.markdown("**Suggested to-dos** — uncheck any you don't want to include:")
                for i, txt in enumerate(suggested):
                    if st.checkbox(txt, value=True, key=f"ni_sug_{i}"):
                        ni_todos.append({"text": txt, "done": False, "due_date": None})

            # ── Manual to-dos during creation ─────────────────────────────────────
            if "ni_staged_todos" not in st.session_state:
                st.session_state["ni_staged_todos"] = []
            _ni_ctr_key = "ni_todo_ctr"
            if _ni_ctr_key not in st.session_state:
                st.session_state[_ni_ctr_key] = 0
            _ni_ctr = st.session_state[_ni_ctr_key]

            # Show already-staged to-dos
            for _nsi, _nstgd in enumerate(st.session_state["ni_staged_todos"]):
                _nsc1, _nsc2, _nsc3 = st.columns([0.5, 9, 0.5])
                _nsc1.markdown('<span style="color:#02B793;font-size:0.85rem">➕</span>', unsafe_allow_html=True)
                _staged_badges = ""
                if _nstgd.get("is_bug"):
                    _staged_badges += ' <span style="background:rgba(220,38,38,0.18);color:#F87171;font-size:9px;font-weight:700;padding:1px 4px;border-radius:3px">BUG</span>'
                if _nstgd.get("due_date"):
                    _staged_badges += f' <span style="font-size:0.75rem;color:#64748B">📅 {_nstgd["due_date"]}</span>'
                _nsc2.markdown(f'<span style="font-size:0.85rem">{_nstgd["text"]}</span>{_staged_badges}', unsafe_allow_html=True)
                if _nsc3.button("✕", key=f"rm_ni_staged_{_nsi}", help="Remove"):
                    st.session_state["ni_staged_todos"].pop(_nsi)
                    st.rerun()

            # Input row — text + due date + bug flag + add button
            _ni_c_txt, _ni_c_date, _ni_c_bug, _ni_c_btn = st.columns([6, 2.5, 1, 1])
            with _ni_c_txt:
                ni_new_todo = st.text_input(
                    "To-dos", placeholder="Add a to-do and press ➕...",
                    key=f"ni_new_todo_{_ni_ctr}",
                )
            with _ni_c_date:
                ni_todo_due = st.date_input(
                    "Due date", value=None, key=f"ni_todo_due_{_ni_ctr}",
                    format="DD/MM/YYYY",
                )
            with _ni_c_bug:
                st.caption("Bug")
                ni_todo_bug = st.checkbox("🐛", value=False, key=f"ni_todo_bug_{_ni_ctr}",
                                          help="Mark this to-do as a bug",
                                          label_visibility="collapsed")
            with _ni_c_btn:
                st.markdown('<div style="margin-top:28px">', unsafe_allow_html=True)
                if st.button("➕ Add", key="ni_add_todo_btn",
                             disabled=not ni_new_todo.strip(),
                             use_container_width=True):
                    _due_str = ni_todo_due.isoformat() if ni_todo_due else None
                    st.session_state["ni_staged_todos"].append(
                        {"text": ni_new_todo.strip(), "done": False,
                         "due_date": _due_str, "is_bug": ni_todo_bug}
                    )
                    st.session_state[_ni_ctr_key] += 1
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

            # Bottom row — agent flag + submit button on same line
            _ni_bot_chk, _ni_bot_btn = st.columns([3, 2])
            with _ni_bot_chk:
                ni_agente = st.checkbox(
                    "Agent authorized", value=False, key="ni_agente",
                    help="Allow the daily agent to automatically work on this item",
                )
            _ni_submit = _ni_bot_btn.button(
                "Add to backlog", type="primary", disabled=not ni_title.strip()
            )

            if _ni_submit:
                store = get_store()
                all_ni_todos = ni_todos + st.session_state.get("ni_staged_todos", [])
                idea = store.create(
                    title=ni_title.strip(),
                    description=ni_desc.strip() or None,
                    area=ni_area.strip() or None,
                    priority=ni_priority,
                    impacto=ni_impact or None,
                    esforco=ni_effort or None,
                    origin="entrada direta",
                    todos=all_ni_todos,
                    agente_autorizado=ni_agente,
                )
                log_entry("criada", idea)
                _rebuild_index(store)
                st.session_state["backlog_flash"] = ("success", f"✅ {idea.id} added to backlog.")
                st.session_state["backlog_panel"] = None
                for k in ["ni_title", "ni_area", "ni_desc", "ni_priority", "ni_impact", "ni_effort",
                          "ni_suggested_todos", "ni_staged_todos", "ni_agente"]:
                    st.session_state.pop(k, None)
                st.session_state[_ni_ctr_key] = 0
                st.rerun()

    elif st.session_state["backlog_panel"] == "bulk":
        with st.container(border=True):
            st.caption("ℹ️ Select ideas, choose the new status and click **Apply**. Useful for moving several ideas at once, e.g. at the end of a sprint.")
            _bulk_ideas = load_ideas()
            bulk_ids = st.multiselect(
                "Ideas",
                options=[i.id for i in _bulk_ideas],
                format_func=lambda x: next((f"{x} — {i.title[:50]}" for i in _bulk_ideas if i.id == x), x),
                placeholder="Select ideas...",
                key="bulk_ids",
            )
            bulk_status = st.selectbox("New status", VALID_STATUSES, key="bulk_status",
                                       format_func=lambda x: STATUS_LABEL.get(x, x))
            if st.button("Apply", type="primary", disabled=not bulk_ids, key="bulk_apply"):
                store_bulk = get_store()
                for bid in bulk_ids:
                    bidea = store_bulk.load_by_id(bid)
                    if bidea:
                        old = bidea.status
                        bidea.status = bulk_status
                        store_bulk.save(bidea)
                        log_entry("alterada", bidea, f"status: {old} -> {bulk_status} (em massa)")
                _rebuild_index(store_bulk)
                st.session_state["backlog_flash"] = ("success", f"Status of {len(bulk_ids)} item(s) updated to '{STATUS_LABEL.get(bulk_status, bulk_status)}'.")
                st.rerun()

    st.markdown('<div style="margin-top:0.5rem"></div>', unsafe_allow_html=True)

    ideas = load_ideas()
    today = date.today()

    # ── Alerta de vencidos ──────────────────────────────────────────────────────
    overdue = [i for i in ideas if i.due_date and i.due_date < today and i.status not in ("concluído", "descartado")]
    if overdue:
        st.warning(f"🔴 {len(overdue)} item(s) past due: {', '.join(i.id for i in overdue)}")

    _CLOSED = {"concluído", "descartado"}

    # ── Filtros ──────────────────────────────────────────────────────────────────
    # Reset must run before the widgets are instantiated this rerun.
    if st.session_state.pop("_clear_backlog_filters", False):
        for _fk in ("flt_priority", "flt_status", "flt_area", "flt_text"):
            st.session_state.pop(_fk, None)

    _area_options = sorted({i.area for i in ideas if i.area})
    col_f1, col_f2, col_f3, col_f4, col_f5 = st.columns([1.2, 1.6, 1.6, 2.8, 0.8],
                                                         vertical_alignment="bottom")
    with col_f1:
        filter_priority = st.multiselect("Priority", VALID_PRIORITIES, placeholder="All",
                                         format_func=lambda x: PRIORITY_LABEL.get(x, x),
                                         key="flt_priority")
    with col_f2:
        filter_status = st.multiselect("Status", VALID_STATUSES, placeholder="All statuses",
                                       format_func=lambda x: STATUS_LABEL.get(x, x),
                                       key="flt_status")
    with col_f3:
        filter_area = st.multiselect("Area", _area_options, placeholder="All areas",
                                     format_func=lambda x: AREA_LABEL.get(x, x.title()),
                                     key="flt_area")
    with col_f4:
        filter_text = st.text_input("Search", placeholder="Title, description, notes, to-dos or area...",
                                    key="flt_text")
    with col_f5:
        _filters_active = bool(filter_priority or filter_status or filter_area or filter_text)
        if st.button("Clear", help="Reset all filters", use_container_width=True,
                     disabled=not _filters_active):
            st.session_state["_clear_backlog_filters"] = True
            st.rerun()

    # ── View toggle + Show closed na mesma linha ─────────────────────────────────
    col_v1, col_v2 = st.columns([1.4, 6.6], vertical_alignment="bottom")
    with col_v1:
        view_mode = st.radio("View", ["List", "Kanban"], horizontal=True, key="view_mode",
                             label_visibility="collapsed")
    with col_v2:
        show_closed = st.checkbox("Show closed (Done · Discarded)", value=False)

    filtered = ideas if show_closed else [i for i in ideas if i.status not in _CLOSED]
    if filter_status:
        filtered = [i for i in filtered if i.status in filter_status]
    if filter_priority:
        filtered = [i for i in filtered if i.priority in filter_priority]
    if filter_area:
        filtered = [i for i in filtered if i.area in filter_area]
    if filter_text:
        q = filter_text.lower()
        def _idea_matches(i):
            haystack = [
                i.title, i.description or "", i.notes or "",
                i.area or "", AREA_LABEL.get(i.area, ""),
            ]
            haystack += [t.get("text", "") for t in i.todos]
            return any(q in (h or "").lower() for h in haystack)
        filtered = [i for i in filtered if _idea_matches(i)]

    priority_order = {"alta": 0, "média": 1, "baixa": 2}
    filtered.sort(key=lambda i: (priority_order.get(i.priority, 9), i.created_at))

    if not filtered:
        st.info("No ideas found with the current filters.")
    else:
        store = get_store()

        # ── KANBAN ──────────────────────────────────────────────────────────────
        if view_mode == "Kanban":
            with st.container(height=600):
                kanban_statuses = [
                    "backlog", "em análise", "em desenvolvimento", "em validação", "concluído", "descartado"
                ]
                visible = [s for s in kanban_statuses if any(i.status == s for i in filtered)]
                cols = st.columns(len(visible)) if visible else []
                for col, status in zip(cols, visible, strict=True):
                    icon = STATUS_COLOR.get(status, _sdot("backlog"))
                    group = [i for i in filtered if i.status == status]
                    col.markdown(f"{icon} **{STATUS_LABEL.get(status, status.title())}** `{len(group)}`", unsafe_allow_html=True)
                    col.divider()
                    for idea in group:
                        picon = PRIORITY_ICON.get(idea.priority, "⚪")
                        card_col, edit_col = col.columns([5, 1])
                        _ktitle = idea.title.replace("**", "").strip()
                        card_col.markdown(
                            f"{picon} `{idea.id}`  \n**{_ktitle[:45]}**"
                            + (f"  \n📅 {idea.due_date.strftime('%d/%m/%y')}" if idea.due_date else "")
                            + (f"  \n{_area_chip(idea.area)}" if idea.area else ""),
                            unsafe_allow_html=True,
                        )
                        if edit_col.button("✏️", key=f"kb_edit_{idea.id}", help="Edit"):
                            st.session_state[f"exp_{idea.id}"] = True
                            st.session_state["view_mode"] = "List"
                            st.session_state["return_to_kanban"] = idea.id
                            st.rerun()
                        col.markdown("---")

        # ── LIST ────────────────────────────────────────────────────────────────
        else:
            st.caption(f"{len(filtered)} item(s)")

            # Column headers
            _h1, _h2, _h3, _h4, _h5 = st.columns([0.06, 0.09, 0.07, 0.63, 0.15])
            _h1.caption("ID")
            _h2.caption("Prio")
            _h3.caption("Status")
            _h4.caption("Backlog item")
            _h5.caption("Area")
            st.divider()

            with st.container(height=600):
                for idea in filtered:
                    prio_icon = PRIORITY_NUM.get(idea.priority, "⚪")
                    status_icon = STATUS_COLOR.get(idea.status, _sdot("backlog"))
                    todos_done = sum(1 for t in idea.todos if t["done"])
                    todos_total = len(idea.todos)
                    bug_count = sum(1 for t in idea.todos if t.get("is_bug") and not t.get("done"))
                    due_flag = "  📅" if idea.due_date and idea.due_date < today else ""
                    badge = f"  `{todos_done}/{todos_total}`" if todos_total else ""
                    bug_badge = f"  🐛`{bug_count}`" if bug_count else ""
                    short_id = idea.id.replace("idea-", "")
                    _clean_title = idea.title.replace("**", "").strip()

                    exp_key = f"exp_{idea.id}"
                    if exp_key not in st.session_state:
                        st.session_state[exp_key] = False

                    c1, c2, c3, c4, c5 = st.columns([0.06, 0.09, 0.07, 0.63, 0.15], vertical_alignment="center")
                    c1.markdown(f"**{short_id}**")
                    c2.markdown(prio_icon, unsafe_allow_html=True)
                    c3.markdown(status_icon, unsafe_allow_html=True)
                    if c4.button(
                        f"{_clean_title}{badge}{bug_badge}{due_flag}",
                        key=f"row_btn_{idea.id}",
                        use_container_width=True,
                    ):
                        new_exp = not st.session_state[exp_key]
                        st.session_state[exp_key] = new_exp
                        if not new_exp and st.session_state.get("return_to_kanban") == idea.id:
                            st.session_state["view_mode"] = "Kanban"
                            st.session_state.pop("return_to_kanban", None)
                    c5.markdown(_area_chip(idea.area), unsafe_allow_html=True)

                    if st.session_state[exp_key]:
                        with st.container(border=True):
                            new_title = st.text_input("Title", value=idea.title, key=f"title_{idea.id}")

                            col_config, col_text = st.columns([2, 3])

                            with col_config:
                                new_status = st.selectbox(
                                    "Status", VALID_STATUSES,
                                    index=VALID_STATUSES.index(idea.status) if idea.status in VALID_STATUSES else 0,
                                    key=f"status_{idea.id}",
                                    format_func=lambda x: STATUS_LABEL.get(x, x),
                                )
                                new_priority = st.selectbox(
                                    "Priority", VALID_PRIORITIES,
                                    index=VALID_PRIORITIES.index(idea.priority) if idea.priority in VALID_PRIORITIES else 0,
                                    key=f"priority_{idea.id}",
                                    format_func=lambda x: PRIORITY_LABEL.get(x, x),
                                )
                                _area_opts = [""] + VALID_AREAS
                                _area_cur = idea.area or ""
                                if _area_cur and _area_cur not in _area_opts:
                                    _area_opts = [""] + [_area_cur] + VALID_AREAS
                                new_area = st.selectbox("Area", _area_opts,
                                                        index=_area_opts.index(_area_cur) if _area_cur in _area_opts else 0,
                                                        key=f"area_{idea.id}",
                                                        format_func=lambda x: AREA_LABEL.get(x, x) if x else "— select —")
                                new_due = st.date_input(
                                    "Due date",
                                    value=idea.due_date,
                                    key=f"due_date_{idea.id}",
                                    format="DD/MM/YYYY",
                                )
                                imp_opts = [""] + VALID_IMPACTS
                                eff_opts = [""] + VALID_EFFORTS
                                new_impacto = st.selectbox(
                                    "Impact", imp_opts,
                                    index=imp_opts.index(idea.impacto) if idea.impacto in imp_opts else 0,
                                    key=f"impacto_{idea.id}",
                                    format_func=lambda x: IMPACT_LABEL.get(x, x) if x else "",
                                )
                                new_esforco = st.selectbox(
                                    "Effort", eff_opts,
                                    index=eff_opts.index(idea.esforco) if idea.esforco in eff_opts else 0,
                                    key=f"esforco_{idea.id}",
                                    format_func=lambda x: EFFORT_LABEL.get(x, x) if x else "",
                                )
                                st.caption(
                                    f"Origin: `{idea.origin or '—'}`  \n"
                                    f"Created: {idea.created_at}  \n"
                                    f"Updated: {idea.updated_at}"
                                )

                            with col_text:
                                new_desc = st.text_area(
                                    "Description", value=idea.description or "",
                                    height=110, key=f"desc_{idea.id}",
                                )
                                new_notes = st.text_area(
                                    "Notes", value=idea.notes or "",
                                    height=90,
                                    placeholder="Observations, links, context...",
                                    key=f"notes_{idea.id}",
                                )

                            re_col, tips_col, hist_col, tr_col = st.columns([2, 2, 2, 2])
                            with tr_col:
                                if st.button("🌐 Translate", key=f"translate_{idea.id}",
                                             help="Translate title, description and to-dos between PT ↔ EN using Ollama"):
                                    _active_idx = [
                                        idx for idx, _ in enumerate(idea.todos)
                                        if idx not in st.session_state.get(f"deleted_todo_idx_{idea.id}", set())
                                    ]
                                    _todo_texts = [
                                        st.session_state.get(f"bl_txt_{idea.id}_{idx}", idea.todos[idx]["text"])
                                        for idx in _active_idx
                                    ]
                                    _payload_in = {
                                        "title": st.session_state.get(f"title_{idea.id}", idea.title),
                                        "description": st.session_state.get(f"desc_{idea.id}", idea.description or ""),
                                        "todos": _todo_texts,
                                    }
                                    _tr_prompt = (
                                        "Translate the following backlog item between Portuguese and English. "
                                        "If the title is in Portuguese, translate everything to English. "
                                        "If the title is in English, translate everything to Portuguese. "
                                        "Keep technical terms, IDs, proper nouns, and acronyms unchanged. "
                                        "Return ONLY valid JSON with the exact same structure as the input:\n"
                                        + json.dumps(_payload_in, ensure_ascii=False)
                                    )
                                    with st.spinner("Translating..."):
                                        try:
                                            # OLLAMA_BASE_URL may end in /v1 or /api — extract host:port only
                                            _ollama_host = OLLAMA_BASE_URL.split("/v1")[0].split("/api")[0]
                                            _tr_r = requests.post(
                                                f"{_ollama_host}/api/generate",
                                                json={"model": "llama3.2:3b", "prompt": _tr_prompt,
                                                      "stream": False, "format": "json"},
                                                timeout=60,
                                            )
                                            _tr_r.raise_for_status()
                                            _tr_data = json.loads(_tr_r.json()["response"])
                                            st.session_state[f"title_{idea.id}"] = _tr_data.get("title", idea.title)
                                            st.session_state[f"desc_{idea.id}"] = _tr_data.get("description", "")
                                            for _i, _orig_idx in enumerate(_active_idx):
                                                _translated_todos = _tr_data.get("todos", [])
                                                if _i < len(_translated_todos):
                                                    st.session_state[f"bl_txt_{idea.id}_{_orig_idx}"] = _translated_todos[_i]
                                            st.rerun()
                                        except Exception as _te:
                                            st.error(f"Translation failed: {_te}")
                            with re_col:
                                if st.button("✨ Suggest to-dos", key=f"regen_{idea.id}", help="Suggests next steps based on title and description"):
                                    from ingestion.extractor import build_client, suggest_todos
                                    with st.spinner("Generating..."):
                                        try:
                                            sugs = suggest_todos(new_title or idea.title, new_desc or idea.description or "", build_client())
                                            st.session_state[f"regen_sugs_{idea.id}"] = sugs
                                        except Exception as e:
                                            st.error(f"Ollama unavailable: {e}")

                            tips_key = f"claude_tips_{idea.id}"
                            current_tips = st.session_state.get(tips_key, idea.claude_tips)
                            with tips_col:
                                tips_label = "🤖 Regenerate tips" if current_tips else "🤖 Claude tips"
                                if st.button(tips_label, key=f"tips_btn_{idea.id}",
                                             help="Generates tips on how to use Claude to develop this item"):
                                    from ingestion.extractor import build_client, suggest_claude_tips
                                    with st.spinner("Generating tips..."):
                                        try:
                                            tips_list = suggest_claude_tips(
                                                new_title or idea.title,
                                                new_desc or idea.description or "",
                                                build_client(),
                                            )
                                            if tips_list:
                                                tips_md = "\n".join(f"- {t}" for t in tips_list)
                                                st.session_state[tips_key] = tips_md
                                                idea.claude_tips = tips_md
                                                fresh = store.load_by_id(idea.id)
                                                if fresh:
                                                    fresh.claude_tips = tips_md
                                                    store.save(fresh)
                                                st.rerun()
                                            else:
                                                st.warning("No tips generated. Add a description to the item.")
                                        except Exception as e:
                                            st.error(f"Ollama indisponível: {e}")

                            regen_sugs = st.session_state.get(f"regen_sugs_{idea.id}", [])
                            if regen_sugs:
                                st.markdown("**Suggested to-dos** — check the ones you want to add:")
                                for si, stxt in enumerate(regen_sugs):
                                    if st.checkbox(stxt, value=False, key=f"regen_chk_{idea.id}_{si}"):
                                        if not any(t["text"] == stxt for t in idea.todos):
                                            idea.todos.append({"text": stxt, "done": False, "due_date": None})

                            with hist_col:
                                if st.button("🕓 View history", key=f"hist_{idea.id}"):
                                    st.session_state[f"show_hist_{idea.id}"] = not st.session_state.get(f"show_hist_{idea.id}", False)

                            if st.session_state.get(f"show_hist_{idea.id}"):
                                log_dir = Path(VAULT_ROOT) / "Log"
                                hist_lines = []
                                for lf in sorted(log_dir.glob("diario-*.md")):
                                    for line in lf.read_text(encoding="utf-8").splitlines():
                                        if idea.id in line and line.strip().startswith("-"):
                                            hist_lines.append(f"`{lf.stem[7:]}` {line.strip()}")
                                if hist_lines:
                                    st.markdown("**History:**")
                                    for hl in hist_lines[-20:]:
                                        st.markdown(hl)
                                else:
                                    st.caption("No events recorded yet.")

                            st.markdown(
                                "<style>"
                                ".todo-row-del + div[data-testid='stButton'] > button {"
                                " padding:0 4px!important; min-height:24px!important;"
                                " background:transparent!important; border:none!important;"
                                " box-shadow:none!important; color:#bbb!important; font-size:0.85rem!important;"
                                " margin-top:8px!important; width:100%!important; }"
                                ".todo-row-del + div[data-testid='stButton'] > button:hover {"
                                " color:#fff!important; background:rgba(185,28,28,0.85)!important;"
                                " border-radius:4px!important; }"
                                "</style>",
                                unsafe_allow_html=True,
                            )
                            _TODO_STATE_OPTS = ["⬜", "🔄", "✅"]
                            h_state, h_txt, h_date, h_auto, h_bug, h_del = st.columns([1.5, 6.5, 1.5, 0.4, 0.4, 0.4])
                            h_state.caption("State")
                            h_txt.caption("To-dos")
                            h_date.caption("📅 Prazo")
                            h_auto.caption("🤖")
                            h_bug.caption("🐛")
                            updated_todos = []
                            deleted_idx_key = f"deleted_todo_idx_{idea.id}"
                            if deleted_idx_key not in st.session_state:
                                st.session_state[deleted_idx_key] = set()

                            for idx, todo in enumerate(idea.todos):
                                if idx in st.session_state[deleted_idx_key]:
                                    continue
                                c_state, c_txt, c_date, c_auto, c_bug, c_del = st.columns([1.5, 5.2, 2, 0.5, 0.5, 0.5], vertical_alignment="center")
                                with c_state:
                                    if todo.get("done"):
                                        cur_idx = 2
                                    elif todo.get("in_progress"):
                                        cur_idx = 1
                                    else:
                                        cur_idx = 0
                                    state_sel = st.selectbox(
                                        "", _TODO_STATE_OPTS, index=cur_idx,
                                        key=f"bl_state_{idea.id}_{idx}",
                                        label_visibility="collapsed",
                                    )
                                    done = state_sel == "✅"
                                    in_progress = state_sel == "🔄"
                                with c_txt:
                                    text = st.text_input(
                                        "", value=todo["text"],
                                        key=f"bl_txt_{idea.id}_{idx}",
                                        label_visibility="collapsed",
                                    )
                                with c_date:
                                    existing_due = None
                                    if todo.get("due_date"):
                                        try:
                                            existing_due = date.fromisoformat(todo["due_date"])
                                        except (ValueError, TypeError):
                                            pass
                                    todo_due = st.date_input(
                                        "", value=existing_due,
                                        key=f"bl_due_{idea.id}_{idx}",
                                        format="DD/MM/YYYY",
                                        label_visibility="collapsed",
                                    )
                                with c_auto:
                                    auto = st.checkbox(
                                        "", value=todo.get("agente_autorizado", False),
                                        key=f"bl_auto_{idea.id}_{idx}",
                                    )
                                with c_bug:
                                    is_bug_todo = st.checkbox(
                                        "", value=todo.get("is_bug", False),
                                        key=f"bl_bug_{idea.id}_{idx}",
                                    )
                                with c_del:
                                    st.markdown('<div class="todo-row-del">', unsafe_allow_html=True)
                                    if st.button("×", key=f"del_todo_{idea.id}_{idx}", use_container_width=True):
                                        st.session_state[deleted_idx_key].add(idx)
                                        st.rerun()
                                    st.markdown('</div>', unsafe_allow_html=True)
                                completed_at = todo.get("completed_at")
                                if done and not completed_at:
                                    completed_at = date.today().isoformat()
                                elif not done:
                                    completed_at = None
                                updated_todos.append({
                                    "text": text,
                                    "done": done,
                                    "in_progress": in_progress,
                                    "due_date": str(todo_due) if todo_due else None,
                                    "completed_at": completed_at,
                                    "agente_autorizado": auto,
                                    "is_bug": is_bug_todo,
                                })

                            staged_key = f"staged_todos_{idea.id}"
                            if staged_key not in st.session_state:
                                st.session_state[staged_key] = []

                            for _si, _stgd in enumerate(st.session_state[staged_key]):
                                _sc1, _sc2, _sc3, _sc4 = st.columns([0.4, 8, 0.4, 0.4])
                                _sc1.markdown("➕")
                                _sc2.caption(("🤖 " if _stgd.get("agente_autorizado") else "") + _stgd["text"])
                                if _sc3.button("✕", key=f"rm_staged_{idea.id}_{_si}", help="Remove"):
                                    st.session_state[staged_key].pop(_si)
                                    st.rerun()

                            # New todo row — counter-based key ensures widget resets after each add
                            _new_ctr_key = f"bl_new_ctr_{idea.id}"
                            if _new_ctr_key not in st.session_state:
                                st.session_state[_new_ctr_key] = 0
                            _ctr = st.session_state[_new_ctr_key]

                            _nc0, _nc_txt, _nc_date, _nc_auto, _nc_bug, _nc_add = st.columns([0.7, 6, 2, 0.5, 0.5, 0.5], vertical_alignment="center")
                            with _nc0:
                                st.markdown('<div style="padding-top:8px;color:#ccc;text-align:center;font-size:0.9rem">+</div>', unsafe_allow_html=True)
                            with _nc_txt:
                                new_todo_text = st.text_input(
                                    "", placeholder="New to-do...",
                                    key=f"bl_new_txt_{idea.id}_{_ctr}",
                                    label_visibility="collapsed",
                                )
                            with _nc_date:
                                new_todo_due = st.date_input(
                                    "", value=None,
                                    key=f"bl_new_due_{idea.id}_{_ctr}",
                                    format="DD/MM/YYYY",
                                    label_visibility="collapsed",
                                )
                            with _nc_auto:
                                new_todo_auto = st.checkbox(
                                    "", value=False,
                                    key=f"bl_new_auto_{idea.id}_{_ctr}",
                                )
                            with _nc_bug:
                                new_todo_bug = st.checkbox(
                                    "", value=False,
                                    key=f"bl_new_bug_{idea.id}_{_ctr}",
                                )
                            with _nc_add:
                                st.markdown('<div class="todo-row-del">', unsafe_allow_html=True)
                                if st.button("➕", key=f"add_todo_btn_{idea.id}",
                                             disabled=not new_todo_text.strip(),
                                             use_container_width=True):
                                    st.session_state[staged_key].append({
                                        "text": new_todo_text.strip(),
                                        "done": False,
                                        "due_date": str(new_todo_due) if new_todo_due else None,
                                        "agente_autorizado": new_todo_auto,
                                        "is_bug": new_todo_bug,
                                    })
                                    st.session_state[_new_ctr_key] += 1  # new key → widget resets cleanly
                                    st.rerun()
                                st.markdown('</div>', unsafe_allow_html=True)

                            for _stgd in st.session_state.get(staged_key, []):
                                updated_todos.append(_stgd)
                            if new_todo_text.strip():
                                updated_todos.append({
                                    "text": new_todo_text.strip(),
                                    "done": False,
                                    "due_date": str(new_todo_due) if new_todo_due else None,
                                    "agente_autorizado": new_todo_auto,
                                    "is_bug": new_todo_bug,
                                })

                            if current_tips:
                                st.markdown(
                                    '<div style="margin-top:6px;margin-bottom:2px">'
                                    '<span style="font-size:0.82em;font-weight:600;color:#02B793">🤖 Dicas com Claude</span>'
                                    '</div>',
                                    unsafe_allow_html=True,
                                )
                                st.info(current_tips)

                            st.markdown(
                                "<style>"
                                # base: red border + red text
                                # anchor: stVerticalBlock with direct stElementContainer child containing marker,
                                # then its last stLayoutWrapper child > stHorizontalBlock > col 2
                                "div[data-testid='stVerticalBlock']"
                                ":has(>div[data-testid='stElementContainer'] .save-del-marker)"
                                ">div[data-testid='stLayoutWrapper']:last-child"
                                ">div[data-testid='stHorizontalBlock']"
                                ">div[data-testid='stColumn']:nth-child(2)"
                                " button[data-testid='stBaseButton-secondary']"
                                "{border:1px solid rgba(220,38,38,0.55)!important;"
                                " color:#FCA5A5!important;background:transparent!important;}"
                                # hover: red fill
                                "div[data-testid='stVerticalBlock']"
                                ":has(>div[data-testid='stElementContainer'] .save-del-marker)"
                                ">div[data-testid='stLayoutWrapper']:last-child"
                                ">div[data-testid='stHorizontalBlock']"
                                ">div[data-testid='stColumn']:nth-child(2)"
                                " button[data-testid='stBaseButton-secondary']:hover"
                                "{background:rgba(220,38,38,0.85)!important;"
                                " color:#fff!important;border:1px solid #DC2626!important;}"
                                "</style>"
                                '<div class="save-del-marker"></div>',
                                unsafe_allow_html=True,
                            )
                            col_save, col_del, _ = st.columns([1, 1, 3], vertical_alignment="center")
                            with col_save:
                                if st.button("💾 Save", key=f"save_{idea.id}", type="primary"):
                                    old_status = idea.status
                                    # Auto-revert: if todos increased (new added or unchecked)
                                    # and idea was in a final/closed status, bump back to In development
                                    _old_open = sum(1 for t in idea.todos if not t.get("done"))
                                    _new_open = sum(1 for t in updated_todos if not t.get("done"))
                                    _auto_reverted = False
                                    if (new_status in ("concluído", "em validação")
                                            and new_status == old_status
                                            and _new_open > _old_open):
                                        new_status = "em desenvolvimento"
                                        _auto_reverted = True
                                    idea.title = new_title.strip() or idea.title
                                    idea.status = new_status
                                    idea.priority = new_priority
                                    idea.area = new_area or None
                                    idea.due_date = new_due if new_due else None
                                    idea.impacto = new_impacto or None
                                    idea.esforco = new_esforco or None
                                    idea.description = new_desc
                                    idea.notes = new_notes
                                    idea.todos = updated_todos
                                    idea.claude_tips = st.session_state.get(tips_key) or idea.claude_tips
                                    store.save(idea)
                                    st.session_state.pop(f"deleted_todo_idx_{idea.id}", None)
                                    _rebuild_index(store)
                                    if new_status == "concluído":
                                        log_entry("concluida", idea)
                                    elif old_status != new_status:
                                        log_entry("alterada", idea, f"status: {old_status} -> {new_status}")
                                    else:
                                        log_entry("alterada", idea)
                                    st.session_state.pop(f"bl_new_txt_{idea.id}", None)
                                    st.session_state.pop(f"bl_new_due_{idea.id}", None)
                                    st.session_state.pop(f"staged_todos_{idea.id}", None)
                                    st.session_state[exp_key] = False
                                    if st.session_state.get("return_to_kanban") == idea.id:
                                        st.session_state["view_mode"] = "Kanban"
                                        st.session_state.pop("return_to_kanban", None)
                                    if _auto_reverted:
                                        st.session_state["backlog_flash"] = ("warning", f"{idea.id} saved — status reverted to In Development (open to-dos added).")
                                    else:
                                        st.session_state["backlog_flash"] = ("success", f"{idea.id} saved.")
                                    st.rerun()
                            with col_del:
                                if st.button("🗑️ Delete", key=f"del_{idea.id}"):
                                    st.session_state[f"confirm_del_{idea.id}"] = True
                                    st.rerun()

                            if st.session_state.get(f"confirm_del_{idea.id}"):
                                st.warning(f"Confirm deletion of **{idea.id} — {idea.title}**?")
                                c_yes, c_no, _ = st.columns([1, 1, 4])
                                with c_yes:
                                    if st.button("✅ Yes, delete", key=f"yes_del_{idea.id}"):
                                        archive = Path(BACKLOG_ARCHIVE_DIR)
                                        archive.mkdir(parents=True, exist_ok=True)
                                        src = store.dir / f"{idea.id}.md"
                                        src.rename(archive / f"{idea.id}.md")
                                        _rebuild_index(store)
                                        st.session_state.pop(f"confirm_del_{idea.id}", None)
                                        st.session_state["backlog_flash"] = ("success", f"{idea.id} moved to deleted.")
                                        st.rerun()
                                with c_no:
                                    if st.button("❌ Cancel", key=f"no_del_{idea.id}"):
                                        st.session_state.pop(f"confirm_del_{idea.id}", None)
                                        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2 — TO-DO LIST
# ══════════════════════════════════════════════════════════════════════════════
elif page == "To-Do List":
    from views.todo_list import render as _render_todo_list
    _render_todo_list()

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3 — DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Dashboard":
    from views.dashboard import render as _render_dashboard
    _render_dashboard()

# PAGE 5 — WEEKLY BRIEF
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Weekly Brief":
    from views.weekly_brief import render as _render_weekly_brief
    _render_weekly_brief()

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 4 — TUTORIAL
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Tutorial":
    from views.tutorial import render as _render_tutorial
    _render_tutorial()

# PAGE 5 — DOCUMENTAÇÃO
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Documentation":
    from views.documentation import render as _render_documentation
    _render_documentation()

# ══════════════════════════════════════════════════════════════════════════════
# PAGE — TEAM
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Team":
    from views.team import render as _render_team
    _render_team()

elif page == "Claude Pro":
    from views.claude_pro import render as _render_claude_pro
    _render_claude_pro()

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 7 — ENGLISH COACH
# ══════════════════════════════════════════════════════════════════════════════
elif page == "English Coach":
    from views.english_coach import render as _render_english_coach
    _render_english_coach()

# PAGE 8 — FAQ
# ══════════════════════════════════════════════════════════════════════════════
elif page == "FAQ":
    from views.faq import render as _render_faq
    _render_faq()

elif page == "Settings":
    from views.settings import render as _render_settings
    _render_settings()
