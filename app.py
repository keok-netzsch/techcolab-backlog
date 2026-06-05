"""
Personal Toolkit · Techco.lab — Streamlit UI
Run with: streamlit run app.py
"""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))


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
/* Prevent expander content from flashing/disappearing on hover.
   Streamlit CSS is injected into the browser <head> and persists across SPA navigation.
   React re-renders on hover state change can briefly unmount content — this locks it. */
details[data-testid="stExpander"][open] > div[data-testid="stExpanderDetails"] {
    opacity: 1 !important; visibility: visible !important; display: block !important; will-change: transform; }
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


if page == "Backlog":
    from views.backlog import render as _render_backlog
    _render_backlog()

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
