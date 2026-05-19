"""
TechColab Backlog — Streamlit UI
Run with: streamlit run app.py
"""

import sys
from pathlib import Path
from datetime import date

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from config import BACKLOG_DIR, BACKLOG_ARCHIVE_DIR, VAULT_ROOT, EXTRACTION_MODEL, OLLAMA_BASE_URL
from backlog.store import BacklogStore
from backlog.schema import VALID_STATUSES, VALID_PRIORITIES, VALID_IMPACTS, VALID_EFFORTS, VALID_AREAS
from backlog.daily_log import log_entry

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="TechColab Backlog",
    page_icon="💡",
    layout="wide",
)

# ── Brand identity ─────────────────────────────────────────────────────────────
_LOGO_GREEN = """<svg width="140" height="44" viewBox="0 0 123 30" fill="none" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMinYMin meet">
  <path d="M0 14.6087V29.2173H2.61944H5.23889V28.1021V26.987H3.64444H2.05V14.6087V2.23038H3.64444H5.23889V1.11521V5.34058e-05H2.61944H0V14.6087Z" fill="#02B793"/>
  <path d="M117.761 1.11521V2.23038H119.356H120.95V14.6087V26.987H119.356H117.761V28.1021V29.2173H120.381H123V14.6087V5.34058e-05H120.381H117.761V1.11521Z" fill="#02B793"/>
  <path d="M42.2528 5.64268C42.1844 5.7765 42.1617 9.9249 42.1844 14.8316L42.2528 23.7529L43.0044 23.8198L43.7333 23.8867V18.9131C43.7333 12.289 43.9611 11.8207 47.2183 11.8207C49.0861 11.8207 49.9744 12.1998 50.3161 13.1812C50.4756 13.6272 50.5667 15.813 50.5667 18.8685V23.8644H51.3639H52.1611V18.5562C52.1611 13.828 52.1156 13.1812 51.7056 12.3336C51.0222 10.8393 50.2022 10.4825 47.5372 10.4825C45.305 10.4825 44.1433 10.7724 43.8928 11.4192C43.8244 11.5753 43.7561 10.2817 43.7561 8.51979L43.7333 5.35274H43.05C42.6628 5.35274 42.2983 5.48656 42.2528 5.64268Z" fill="#02B793"/>
  <path d="M84.0498 14.6084V23.8643H85.4165H86.7831V14.6084V5.35258H85.4165H84.0498V14.6084Z" fill="#02B793"/>
  <path d="M103.343 5.50886C103.252 5.57577 103.183 9.74647 103.183 14.7647V23.8867L107.488 23.8198C112.203 23.7529 112.408 23.686 113.524 22.214C113.98 21.6341 114.003 21.2995 114.003 17.1065C114.003 12.7574 113.98 12.579 113.479 11.8653C112.613 10.6832 111.771 10.371 109.402 10.371C107.602 10.371 107.238 10.4379 106.623 10.8839L105.917 11.3969V8.36367V5.35274H104.709C104.026 5.35274 103.411 5.41965 103.343 5.50886ZM110.882 13.2258C111.224 13.5603 111.269 14.0956 111.269 17.0396C111.269 21.5003 111.292 21.4557 108.217 21.3665L106.031 21.2995L105.962 18.1548C105.871 13.3373 106.281 12.6236 109.06 12.7797C110.017 12.8243 110.609 12.9804 110.882 13.2258Z" fill="#02B793"/>
  <path d="M10.9333 9.14412V10.4823H9.9083C8.92886 10.4823 8.8833 10.5046 8.8833 11.1514C8.8833 11.7982 8.92886 11.8205 9.88552 11.8205H10.9105L10.9789 16.6603C11.0472 20.9648 11.0927 21.6116 11.48 22.2361C12.1633 23.329 13.3477 23.8643 15.1472 23.8643H16.6505L16.5822 23.2398C16.5139 22.6822 16.4227 22.6376 15.17 22.5038C14.1677 22.3922 13.7122 22.2138 13.2339 21.7678L12.6416 21.1879L12.5733 16.5042L12.505 11.8428L14.3955 11.7759C16.2405 11.709 16.2861 11.6867 16.2861 11.1514C16.2861 10.6161 16.2177 10.5938 14.4639 10.4823L12.6416 10.3708L12.5733 9.07722L12.505 7.80593H11.7305H10.9333V9.14412Z" fill="#02B793"/>
  <path d="M20.4772 10.9953C19.065 11.9097 18.9055 12.5342 18.9055 17.1733C18.9055 21.8124 19.065 22.4369 20.4772 23.3513C21.2061 23.842 21.4794 23.8643 24.9644 23.8643H28.7V23.2175V22.5484L25.1694 22.4815C21.8666 22.4145 21.6161 22.3922 21.1377 21.9016C20.705 21.5001 20.6138 21.0987 20.5455 19.7382L20.4544 18.0654L24.6227 18.0208L28.8138 17.9539L28.8822 15.6121C28.9277 13.5379 28.8822 13.1587 28.4266 12.2666C27.6522 10.7723 26.8777 10.4823 23.78 10.4823C21.525 10.4823 21.1605 10.5492 20.4772 10.9953ZM26.0577 12.0435C26.9233 12.3558 27.3333 13.3594 27.3333 15.166V16.7272H23.9166H20.5V14.9207C20.5 13.2256 20.5455 13.0918 21.1605 12.4673C21.7983 11.8651 21.935 11.8205 23.6661 11.8205C24.6683 11.8205 25.7388 11.9097 26.0577 12.0435Z" fill="#02B793"/>
  <path d="M33.4832 10.9061C31.9343 11.709 31.7749 12.2666 31.7749 17.1733C31.7749 21.2994 31.7977 21.567 32.2988 22.3253C33.096 23.5966 33.916 23.8643 37.1049 23.8643H39.861V23.1952V22.5261H37.4693C33.4832 22.5261 33.2555 22.2361 33.2555 17.1733C33.2555 12.1105 33.4832 11.8205 37.4693 11.8205H39.861V11.1514V10.4823H37.0593C34.7816 10.4823 34.121 10.5492 33.4832 10.9061Z" fill="#02B793"/>
  <path d="M56.7166 10.9733C55.0539 12.0885 55.0083 12.2446 55.0083 17.1736C55.0083 21.2997 55.0311 21.6343 55.4866 22.2141C56.5572 23.6192 56.9216 23.7531 60.3839 23.82L63.5727 23.9092L63.5044 22.7048L63.4361 21.5227L61.0216 21.4558C57.6733 21.3666 57.7416 21.4558 57.7416 17.1736C57.7416 12.8914 57.6733 12.9806 61.0216 12.8914L63.4361 12.8245L63.5044 11.6424L63.5727 10.4826H60.5205C57.7189 10.4826 57.4 10.5272 56.7166 10.9733Z" fill="#02B793"/>
  <path d="M67.5134 10.7948C65.7368 11.5754 65.304 12.9582 65.4179 17.7088C65.4862 21.6341 65.6912 22.3032 67.0351 23.2846C67.6273 23.7083 67.9918 23.7529 70.839 23.7529C74.4606 23.7529 74.8934 23.5968 75.8045 21.8572C76.2601 20.9427 76.3056 20.5636 76.3056 17.1735C76.3056 13.7834 76.2601 13.4042 75.8045 12.4898C74.9162 10.7948 74.4379 10.594 71.1123 10.5271C69.0395 10.5048 68.0145 10.5717 67.5134 10.7948ZM73.0256 13.4042C73.4129 13.828 73.4584 14.2518 73.4584 17.1735C73.4584 21.3219 73.4129 21.4111 70.8845 21.4111C68.3106 21.4111 68.3334 21.4334 68.3334 17.2181C68.3334 12.9136 68.3334 12.9359 70.839 12.9359C72.3195 12.9359 72.6612 13.0028 73.0256 13.4042Z" fill="#02B793"/>
  <path d="M91.6578 10.7946C89.8812 11.5752 89.4484 12.958 89.5623 17.7086C89.6306 20.8087 89.6989 21.4109 90.0862 22.0577C90.9289 23.4405 91.5667 23.7528 94.0039 23.842C95.94 23.9089 96.2589 23.8643 96.8284 23.4405L97.4889 22.9498V23.4182C97.4889 23.842 97.6028 23.8866 98.9239 23.8197L100.336 23.7528V17.1733V10.5938L96.35 10.5492C93.4117 10.5046 92.1817 10.5715 91.6578 10.7946ZM97.4889 16.6157C97.4889 20.2511 97.4889 20.3181 96.9195 20.8533C96.4412 21.344 96.1678 21.4109 94.8695 21.4109C92.5462 21.4109 92.4778 21.2771 92.4778 17.1287C92.4778 12.8465 92.4095 12.9357 95.3706 12.9357H97.4889V16.6157Z" fill="#02B793"/>
  <path d="M78.5833 21.7455V23.8643H79.9499H81.3166V21.7455V19.6266H79.9499H78.5833V21.7455Z" fill="#02B793"/>
</svg>"""

_BRAND_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

/* ── Ocultar header padrão do Streamlit ─────────────────── */
[data-testid="stHeader"] { display: none !important; }
[data-testid="stToolbar"] { display: none !important; }

/* ── Global font ─────────────────────────────────────────── */
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
}

/* ── Primary buttons ──────────────────────────────────────── */
.stButton > button[kind="primary"] {
    background: linear-gradient(90deg, #02B793, #0AD4A8) !important;
    border: none !important;
    color: #ffffff !important;
    font-family: 'Inter', sans-serif !important;
}
.stButton > button[kind="primary"]:hover {
    background: linear-gradient(90deg, #007167, #02B793) !important;
}

/* ── Page title gradient ──────────────────────────────────── */
h1 {
    background: linear-gradient(135deg, #007167, #8AC6BD);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    font-weight: 700;
    letter-spacing: -0.02em;
    font-family: 'Inter', sans-serif !important;
}

/* ── Sidebar ─────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background-color: #FFFFFF;
    border-right: 1px solid rgba(76,77,88,0.08);
}

/* ── Sidebar nav buttons ─────────────────────────────────── */
[data-testid="stSidebar"] .stButton > button {
    text-align: left !important;
    justify-content: flex-start !important;
    border-radius: 8px !important;
    font-size: 0.9rem !important;
    font-weight: 500 !important;
    padding: 0.45rem 0.75rem !important;
    margin-bottom: 2px !important;
    border: none !important;
    width: 100% !important;
}
[data-testid="stSidebar"] .stButton > button[kind="secondary"] {
    background: transparent !important;
    color: #4A4A4A !important;
}
[data-testid="stSidebar"] .stButton > button[kind="secondary"]:hover {
    background: rgba(2,183,147,0.08) !important;
    color: #007167 !important;
}
[data-testid="stSidebar"] .stButton > button[kind="primary"] {
    background: rgba(2,183,147,0.12) !important;
    color: #007167 !important;
    font-weight: 600 !important;
}

/* ── Footer icon buttons ─────────────────────────────────── */
.sidebar-footer .stButton > button {
    font-size: 1.2rem !important;
    text-align: center !important;
    justify-content: center !important;
    padding: 0.4rem !important;
    background: transparent !important;
    border: 1px solid rgba(76,77,88,0.12) !important;
    border-radius: 8px !important;
    color: rgba(76,77,88,0.5) !important;
}
.sidebar-footer .stButton > button:hover {
    background: rgba(2,183,147,0.08) !important;
    border-color: #02B793 !important;
    color: #007167 !important;
}

/* ── Progress bars ────────────────────────────────────────── */
[data-testid="stProgressBar"] > div > div {
    background: linear-gradient(90deg, #02B793, #0AD4A8) !important;
}

/* ── Idea row buttons (title column) — left-aligned, borderless ── */
[data-testid="column"] .stButton > button[kind="tertiary"],
[data-testid="column"] .stButton > button[data-testid*="row_btn"] {
    text-align: left !important;
    justify-content: flex-start !important;
    background: transparent !important;
    border: none !important;
    color: #2A2A2A !important;
    padding: 0.15rem 0.4rem !important;
    font-size: 0.9rem !important;
    width: 100%;
}

/* Catch-all for idea row buttons that use secondary kind */
[data-testid="stHorizontalBlock"]:not([data-sidebar]) .stButton > button[kind="secondary"]:not([data-testid*="nav_"]) {
    text-align: left !important;
    justify-content: flex-start !important;
    background: transparent !important;
    border: none !important;
    color: #2A2A2A !important;
    font-size: 0.9rem !important;
}
[data-testid="stHorizontalBlock"]:not([data-sidebar]) .stButton > button[kind="secondary"]:not([data-testid*="nav_"]):hover {
    background: rgba(2,183,147,0.07) !important;
    color: #007167 !important;
}
</style>
"""

st.markdown(_BRAND_CSS, unsafe_allow_html=True)
# Favicon: base64-encoded SVG (raw angle brackets in data URIs break the HTML parser)
_FAVICON_B64 = "PHN2ZyB4bWxucz0naHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmcnIHZpZXdCb3g9JzAgMCAzMiAzMic+PHJlY3Qgd2lkdGg9JzMyJyBoZWlnaHQ9JzMyJyByeD0nNicgZmlsbD0nIzAyQjc5MycvPjx0ZXh0IHg9JzE2JyB5PScyMicgdGV4dC1hbmNob3I9J21pZGRsZScgZm9udC1mYW1pbHk9J0ludGVyLHNhbnMtc2VyaWYnIGZvbnQtc2l6ZT0nMTQnIGZvbnQtd2VpZ2h0PSc3MDAnIGZpbGw9J3doaXRlJz50YzwvdGV4dD48L3N2Zz4="
st.markdown(
    f'<link rel="shortcut icon" href="data:image/svg+xml;base64,{_FAVICON_B64}" type="image/svg+xml">',
    unsafe_allow_html=True,
)

# ── Sidebar: logo + navigation + reload ────────────────────────────────────────
_PAGES_MAIN  = ["📋 Backlog", "✅ To-Do List", "📊 Dashboard", "📈 Claude Pro"]
_PAGES_EXTRA = {"📖": "📖 Tutorial", "📚": "📚 Documentation"}

if "page" not in st.session_state:
    st.session_state["page"] = "📋 Backlog"

with st.sidebar:
    st.markdown(
        f'<div style="padding:1.2rem 0 0.8rem 0;display:flex;justify-content:center">{_LOGO_GREEN}</div>',
        unsafe_allow_html=True,
    )
    st.divider()

    for _p in _PAGES_MAIN:
        _active = st.session_state["page"] == _p
        if st.button(_p, key=f"nav_{_p}", use_container_width=True,
                     type="primary" if _active else "secondary"):
            st.session_state["page"] = _p
            st.rerun()

    st.divider()
    if st.button("🔄 Reload ideas", use_container_width=True, type="secondary"):
        st.rerun()

    st.markdown("<br>" * 3, unsafe_allow_html=True)
    st.divider()
    st.markdown(
        '<p style="font-size:0.72rem;color:rgba(76,77,88,0.45);margin:0 0 6px 2px">Resources</p>',
        unsafe_allow_html=True,
    )
    with st.container():
        st.markdown('<div class="sidebar-footer">', unsafe_allow_html=True)
        _fc1, _fc2 = st.columns(2)
        with _fc1:
            if st.button("📖", key="nav_tutorial", use_container_width=True,
                         help="Installation tutorial"):
                st.session_state["page"] = "📖 Tutorial"
                st.rerun()
            st.markdown(
                '<p style="text-align:center;font-size:0.68rem;color:rgba(76,77,88,0.5);margin:0">Tutorial</p>',
                unsafe_allow_html=True,
            )
        with _fc2:
            if st.button("📚", key="nav_docs", use_container_width=True,
                         help="Technical documentation"):
                st.session_state["page"] = "📚 Documentation"
                st.rerun()
            st.markdown(
                '<p style="text-align:center;font-size:0.68rem;color:rgba(76,77,88,0.5);margin:0">Docs</p>',
                unsafe_allow_html=True,
            )
        st.markdown('</div>', unsafe_allow_html=True)

page = st.session_state["page"]

PRIORITY_ICON = {"alta": "⭐⭐⭐", "média": "⭐⭐", "baixa": "⭐"}
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

# ── Store ─────────────────────────────────────────────────────────────────────
def get_store() -> BacklogStore:
    return BacklogStore(Path(BACKLOG_DIR))

def load_ideas():
    return get_store().load_all()

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
        st.markdown(
            "**Priority**  \n"
            "⭐⭐⭐ High  \n"
            "⭐⭐ Medium  \n"
            "⭐ Low"
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


if page == "📋 Backlog":
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
    if "backlog_panel" not in st.session_state:
        st.session_state["backlog_panel"] = None

    def _toggle_panel(name: str):
        st.session_state["backlog_panel"] = None if st.session_state["backlog_panel"] == name else name

    _panel = st.session_state["backlog_panel"]
    _tb1, _tb2, _tb3, _ = st.columns([1.3, 1.3, 1.8, 5.6])

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
            "➕ New idea" + (" ▲" if _active else " ▼"),
            key="tb_nova",
            type="primary" if _active else "secondary",
        ):
            _toggle_panel("nova"); st.rerun()

    with _tb3:
        _active = _panel == "bulk"
        if st.button(
            "⚡ Bulk status update" + (" ▲" if _active else " ▼"),
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
                                       format_func=lambda x: x if x else "— selecione —")
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
                    from ingestion.extractor import suggest_todos, build_client
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
                                f"Título: {ni_title.strip()}\nDescrição: {ni_desc.strip() or '(sem descrição)'}\n\n"
                                "Qual a prioridade desta ideia? Responda APENAS com uma das opções: alta, média, baixa."
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

            if st.button("Add to backlog", type="primary", disabled=not ni_title.strip()):
                store = get_store()
                idea = store.create(
                    title=ni_title.strip(),
                    description=ni_desc.strip() or None,
                    area=ni_area.strip() or None,
                    priority=ni_priority,
                    impacto=ni_impact or None,
                    esforco=ni_effort or None,
                    origin="entrada direta",
                    todos=ni_todos,
                )
                log_entry("criada", idea)
                _rebuild_index(store)
                st.session_state["backlog_flash"] = ("success", f"✅ {idea.id} added to backlog.")
                st.session_state["backlog_panel"] = None
                for k in ["ni_title", "ni_area", "ni_desc", "ni_priority", "ni_impact", "ni_effort", "ni_suggested_todos"]:
                    st.session_state.pop(k, None)
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

    # ── Filtros + toggle de view na mesma linha ─────────────────────────────────
    col_f1, col_f2, col_f3, col_f4 = st.columns([1.2, 1.8, 4, 1])
    with col_f1:
        filter_priority = st.multiselect("Priority", VALID_PRIORITIES, placeholder="All",
                                         format_func=lambda x: PRIORITY_LABEL.get(x, x))
    with col_f2:
        filter_status = st.multiselect("Status", VALID_STATUSES, placeholder="All statuses",
                                       format_func=lambda x: STATUS_LABEL.get(x, x))
    with col_f3:
        filter_text = st.text_input("Search", placeholder="Title, description or notes...")
    with col_f4:
        view_mode = st.radio("View", ["List", "Kanban"], horizontal=False, key="view_mode", label_visibility="hidden")

    show_closed = st.checkbox("Show closed (Done · Discarded)", value=False)

    filtered = ideas if show_closed else [i for i in ideas if i.status not in _CLOSED]
    if filter_status:
        filtered = [i for i in filtered if i.status in filter_status]
    if filter_priority:
        filtered = [i for i in filtered if i.priority in filter_priority]
    if filter_text:
        q = filter_text.lower()
        filtered = [
            i for i in filtered
            if q in i.title.lower()
            or q in (i.description or "").lower()
            or q in (i.notes or "").lower()
        ]

    priority_order = {"alta": 0, "média": 1, "baixa": 2}
    filtered.sort(key=lambda i: (priority_order.get(i.priority, 9), i.created_at))

    if not filtered:
        st.info("No ideas found with the current filters.")
    else:
        store = get_store()

        # ── KANBAN ──────────────────────────────────────────────────────────────
        if view_mode == "Kanban":
            kanban_statuses = [
                "backlog", "em análise", "em desenvolvimento", "em validação", "concluído", "descartado"
            ]
            visible = [s for s in kanban_statuses if any(i.status == s for i in filtered)]
            cols = st.columns(len(visible)) if visible else []
            for col, status in zip(cols, visible):
                icon = STATUS_COLOR.get(status, _sdot("backlog"))
                group = [i for i in filtered if i.status == status]
                col.markdown(f"{icon} **{STATUS_LABEL.get(status, status.title())}** `{len(group)}`", unsafe_allow_html=True)
                col.divider()
                for idea in group:
                    picon = PRIORITY_ICON.get(idea.priority, "⚪")
                    card_col, edit_col = col.columns([5, 1])
                    card_col.markdown(
                        f"{picon} `{idea.id}`  \n**{idea.title[:45]}**"
                        + (f"  \n📅 {idea.due_date.strftime('%d/%m/%y')}" if idea.due_date else "")
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
            _h1, _h2, _h3, _h4 = st.columns([0.06, 0.09, 0.05, 0.80])
            _h1.caption("ID")
            _h2.caption("Prio")
            _h3.caption("Status")
            _h4.caption("Backlog item")
            st.markdown('<hr style="margin:2px 0 6px 0;border-color:rgba(76,77,88,0.12)">', unsafe_allow_html=True)

            for idea in filtered:
                prio_icon = PRIORITY_ICON.get(idea.priority, "⚪")
                status_icon = STATUS_COLOR.get(idea.status, _sdot("backlog"))
                todos_done = sum(1 for t in idea.todos if t["done"])
                todos_total = len(idea.todos)
                due_flag = "  📅" if idea.due_date and idea.due_date < today else ""
                badge = f"  `{todos_done}/{todos_total}`" if todos_total else ""
                short_id = idea.id.replace("idea-", "")

                exp_key = f"exp_{idea.id}"
                if exp_key not in st.session_state:
                    st.session_state[exp_key] = False

                c1, c2, c3, c4 = st.columns([0.06, 0.09, 0.05, 0.80])
                c1.markdown(f"**{short_id}**")
                c2.markdown(prio_icon)
                c3.markdown(status_icon, unsafe_allow_html=True)
                if c4.button(
                    f"{idea.title}{badge}{due_flag}",
                    key=f"row_btn_{idea.id}",
                    use_container_width=True,
                ):
                    new_exp = not st.session_state[exp_key]
                    st.session_state[exp_key] = new_exp
                    if not new_exp and st.session_state.get("return_to_kanban") == idea.id:
                        st.session_state["view_mode"] = "Kanban"
                        st.session_state.pop("return_to_kanban", None)

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
                                                    format_func=lambda x: x if x else "— selecione —")
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

                        re_col, hist_col, _ = st.columns([2, 2, 3])
                        with re_col:
                            if st.button("✨ Regenerate to-dos", key=f"regen_{idea.id}", help="Suggests new to-dos based on current title and description"):
                                from ingestion.extractor import suggest_todos, build_client
                                with st.spinner("Generating..."):
                                    try:
                                        sugs = suggest_todos(new_title or idea.title, new_desc or idea.description or "", build_client())
                                        st.session_state[f"regen_sugs_{idea.id}"] = sugs
                                    except Exception as e:
                                        st.error(f"Ollama unavailable: {e}")

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
                            log_dir = Path(VAULT_ROOT) / "Backlog - to do - app" / "Log"
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

                        h_chk, h_txt, h_date = st.columns([1, 6, 2])
                        h_txt.markdown("**To-dos**")
                        h_date.caption("📅 Prazo")
                        updated_todos = []

                        for idx, todo in enumerate(idea.todos):
                            c_chk, c_txt, c_date = st.columns([1, 6, 2])
                            with c_chk:
                                done = st.checkbox(
                                    "", value=todo["done"],
                                    key=f"bl_chk_{idea.id}_{idx}",
                                )
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
                            updated_todos.append({
                                "text": text,
                                "done": done,
                                "due_date": str(todo_due) if todo_due else None,
                            })

                        staged_key = f"staged_todos_{idea.id}"
                        if staged_key not in st.session_state:
                            st.session_state[staged_key] = []

                        for _si, _stgd in enumerate(st.session_state[staged_key]):
                            _sc1, _sc2, _sc3 = st.columns([0.5, 7, 0.5])
                            _sc1.markdown("➕")
                            _sc2.caption(_stgd["text"])
                            if _sc3.button("✕", key=f"rm_staged_{idea.id}_{_si}", help="Remove"):
                                st.session_state[staged_key].pop(_si)
                                st.rerun()

                        c_new_txt, c_new_date, c_add = st.columns([5, 2, 1])
                        with c_new_txt:
                            new_todo_text = st.text_input(
                                "", placeholder="+ New to-do...",
                                key=f"bl_new_txt_{idea.id}",
                                label_visibility="collapsed",
                            )
                        with c_new_date:
                            new_todo_due = st.date_input(
                                "", value=None,
                                key=f"bl_new_due_{idea.id}",
                                format="DD/MM/YYYY",
                                label_visibility="collapsed",
                            )
                        with c_add:
                            if st.button("➕", key=f"add_todo_btn_{idea.id}",
                                         disabled=not new_todo_text.strip(),
                                         help="Stage this to-do (add another without saving)"):
                                st.session_state[staged_key].append({
                                    "text": new_todo_text.strip(),
                                    "done": False,
                                    "due_date": str(new_todo_due) if new_todo_due else None,
                                })
                                st.session_state.pop(f"bl_new_txt_{idea.id}", None)
                                st.session_state.pop(f"bl_new_due_{idea.id}", None)
                                st.rerun()

                        for _stgd in st.session_state.get(staged_key, []):
                            updated_todos.append(_stgd)
                        if new_todo_text.strip():
                            updated_todos.append({
                                "text": new_todo_text.strip(),
                                "done": False,
                                "due_date": str(new_todo_due) if new_todo_due else None,
                            })

                        # ── Claude Tips ───────────────────────────────────────────────────────
                        tips_key = f"claude_tips_{idea.id}"
                        current_tips = st.session_state.get(tips_key, idea.claude_tips)

                        st.markdown(
                            '<div style="margin-top:10px;margin-bottom:4px;border-top:1px solid rgba(76,77,88,0.15);padding-top:8px">'
                            '<span style="font-size:0.85em;font-weight:600;color:#02B793">🤖 Dicas com Claude</span>'
                            '</div>',
                            unsafe_allow_html=True,
                        )
                        tips_btn_col, _ = st.columns([2, 5])
                        with tips_btn_col:
                            tips_label = "↻ Regenerar dicas" if current_tips else "✨ Gerar dicas com Claude"
                            if st.button(tips_label, key=f"tips_btn_{idea.id}",
                                         help="Usa o modelo local (Ollama) para sugerir como usar o Claude no desenvolvimento deste item"):
                                from ingestion.extractor import suggest_claude_tips, build_client
                                with st.spinner("Gerando dicas..."):
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
                                            # Auto-save only the tips field
                                            fresh = store.load_by_id(idea.id)
                                            if fresh:
                                                fresh.claude_tips = tips_md
                                                store.save(fresh)
                                        else:
                                            st.warning("Nenhuma dica gerada. Tente adicionar uma descrição ao item.")
                                    except Exception as e:
                                        st.error(f"Ollama indisponível: {e}")
                        if current_tips:
                            st.info(current_tips)
                        else:
                            st.caption("_Nenhuma dica gerada ainda._")

                        col_save, col_del, _ = st.columns([1, 1, 3])
                        with col_save:
                            if st.button("💾 Save", key=f"save_{idea.id}", type="primary"):
                                old_status = idea.status
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
elif page == "✅ To-Do List":
    st.header("To-Do List")
    st.caption("All action items consolidated in one place. Check them off throughout the day.")
    with st.expander("📖 Legend", expanded=False):
        _render_legend()

    ideas = load_ideas()

    all_todos = []
    for idea in ideas:
        for idx, todo in enumerate(idea.todos):
            all_todos.append({
                "idea_id": idea.id,
                "idea_title": idea.title,
                "priority": idea.priority,
                "area": idea.area or "—",
                "status": idea.status,
                "todo_idx": idx,
                "text": todo["text"],
                "done": todo["done"],
                "due_date": todo.get("due_date"),
            })

    if not all_todos:
        st.info("No to-dos found. Add to-dos to ideas in the Backlog.")
    else:
        col_a, col_b, col_c = st.columns([2, 2, 2])
        with col_a:
            show_filter = st.radio("Show", ["Pending", "Done", "All"], horizontal=True)
        with col_b:
            areas = sorted(set(t["area"] for t in all_todos if t["area"] != "—"))
            filter_area = st.selectbox("Area", ["All"] + areas)
        with col_c:
            group_by = st.radio("Group by", ["Priority", "Idea", "Area", "Date"], horizontal=True)

        filtered_todos = all_todos
        if show_filter == "Pending":
            filtered_todos = [t for t in filtered_todos if not t["done"]]
        elif show_filter == "Done":
            filtered_todos = [t for t in filtered_todos if t["done"]]
        if filter_area != "All":
            filtered_todos = [t for t in filtered_todos if t["area"] == filter_area]

        prio_order = {"alta": 0, "média": 1, "baixa": 2}
        filtered_todos.sort(key=lambda t: (prio_order.get(t["priority"], 9), t["idea_id"]))

        pending_count = sum(1 for t in filtered_todos if not t["done"])
        done_count = sum(1 for t in filtered_todos if t["done"])
        st.markdown(f"**{pending_count} pending** · {done_count} done out of {len(filtered_todos)} shown")
        st.divider()

        _GROUP_DATA_ORDER = {"🔴 Overdue": 0, "📅 This week": 1, "📆 This month": 2, "🗓️ Upcoming": 3, "📭 No due date": 4}

        def _due_group(t) -> str:
            from datetime import timedelta
            raw = t.get("due_date")
            if not raw:
                return "📭 No due date"
            try:
                due = date.fromisoformat(raw)
                _today = date.today()
                week_end = _today + timedelta(days=(6 - _today.weekday()))
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
                return f"{PRIORITY_ICON.get(t['priority'], '⚪')} {PRIORITY_LABEL.get(t['priority'], t['priority'].title())}"
            elif group_by == "Idea":
                return f"💡 {t['idea_id']} — {t['idea_title']}"
            elif group_by == "Date":
                return _due_group(t)
            else:
                return f"🏷️ {t['area']}"

        from itertools import groupby
        if group_by == "Date":
            filtered_todos.sort(key=lambda t: (_GROUP_DATA_ORDER.get(_due_group(t), 9), t["idea_id"]))
        elif group_by == "Priority":
            filtered_todos.sort(key=lambda t: (prio_order.get(t["priority"], 9), t["idea_id"]))
        else:
            filtered_todos.sort(key=get_group_key)
        store = get_store()
        today = date.today()

        for group_label, group_items in groupby(filtered_todos, key=get_group_key):
            items = list(group_items)
            st.markdown(f"#### {group_label}")
            for item in items:
                idea = store.load_by_id(item["idea_id"])
                if not idea:
                    continue

                # Header row: short ID | prio | status | todo text + due
                c_id, c_prio, c_status, c_chk, c_info = st.columns([0.05, 0.07, 0.05, 0.65, 0.18])
                short = item["idea_id"].replace("idea-", "")
                c_id.caption(short)
                c_prio.markdown(PRIORITY_ICON.get(item["priority"], "⚪"))
                c_status.markdown(STATUS_COLOR.get(item["status"], _sdot("backlog")), unsafe_allow_html=True)

                with c_chk:
                    checked = st.checkbox(
                        item["text"],
                        value=item["done"],
                        key=f"tdl_{item['idea_id']}_{item['todo_idx']}",
                    )
                with c_info:
                    due_str = ""
                    if item.get("due_date"):
                        try:
                            due = date.fromisoformat(item["due_date"])
                            if due < today:
                                due_str = f"🔴 {due.strftime('%d/%m')}"
                            elif due == today:
                                due_str = "🟡 today"
                            else:
                                due_str = f"📅 {due.strftime('%d/%m')}"
                        except (ValueError, TypeError):
                            pass
                    st.caption(due_str)

                if checked != item["done"]:
                    idea.todos[item["todo_idx"]]["done"] = checked
                    store.save(idea)
                    if checked:
                        log_entry("todo_concluido", idea, item["text"])
                    st.rerun()
            st.markdown("")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3 — DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📊 Dashboard":
    from datetime import timedelta, date as _date
    import re as _re

    st.header("📊 Dashboard")

    ideas_all = load_ideas()
    todos_all = [t for idea in ideas_all for t in idea.todos]

    total = len(ideas_all)
    active = sum(1 for i in ideas_all if i.status not in ("concluído", "descartado"))
    concluidas = sum(1 for i in ideas_all if i.status == "concluído")
    todos_done = sum(1 for t in todos_all if t["done"])
    todos_pending = sum(1 for t in todos_all if not t["done"])

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Total ideas", total)
    m2.metric("Active", active)
    m3.metric("Done", concluidas)
    m4.metric("Pending to-dos", todos_pending)
    m5.metric("Done to-dos", todos_done)

    st.divider()

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("By status")
        status_counts = {}
        for i in ideas_all:
            status_counts[i.status] = status_counts.get(i.status, 0) + 1
        for status in VALID_STATUSES:
            count = status_counts.get(status, 0)
            if count:
                icon = STATUS_COLOR.get(status, _sdot("backlog"))
                pct = count / total if total else 0
                st.markdown(f"{icon} **{STATUS_LABEL.get(status, status)}** — {count}", unsafe_allow_html=True)
                st.progress(pct)

    with col_right:
        st.subheader("By priority")
        prio_counts = {}
        for i in ideas_all:
            prio_counts[i.priority] = prio_counts.get(i.priority, 0) + 1
        for p in VALID_PRIORITIES:
            count = prio_counts.get(p, 0)
            icon = PRIORITY_ICON.get(p, "⚪")
            pct = count / total if total else 0
            st.markdown(f"{icon} **{PRIORITY_LABEL.get(p, p)}** — {count}")
            st.progress(pct)

    st.divider()

    col_area, col_score = st.columns(2)

    with col_area:
        st.subheader("By area")
        area_counts = {}
        for i in ideas_all:
            area = i.area or "—"
            area_counts[area] = area_counts.get(area, 0) + 1
        for area, count in sorted(area_counts.items(), key=lambda x: -x[1]):
            pct = count / total if total else 0
            st.markdown(f"🏷️ **{area}** — {count}")
            st.progress(pct)

    with col_score:
        st.subheader("Scoring: Impact × Effort")
        scored = [i for i in ideas_all if i.impacto and i.esforco]
        if not scored:
            st.info("No ideas with impact and effort filled in yet.")
        else:
            impact_val = {"alta": 3, "média": 2, "baixa": 1}
            effort_val = {"baixo": 3, "médio": 2, "alto": 1}
            def _score(idea):
                return impact_val.get(idea.impacto, 0) * effort_val.get(idea.esforco, 0)
            ranked = sorted(scored, key=_score, reverse=True)
            for idea in ranked[:8]:
                s = _score(idea)
                icon = PRIORITY_ICON.get(idea.priority, "⚪")
                st.markdown(
                    f"{icon} `{idea.id}` **{idea.title[:40]}**  \n"
                    f"&nbsp;&nbsp;&nbsp;Impact: {IMPACT_LABEL.get(idea.impacto, idea.impacto)} · Effort: {EFFORT_LABEL.get(idea.esforco, idea.esforco)} · Score: **{s}**"
                )

    st.divider()

    st.subheader("📋 Period report")

    @st.dialog("Generate period report", width="large")
    def _report_dialog():
        from pathlib import Path as _Path
        from config import VAULT_ROOT as _VAULT_ROOT

        today = _date.today()
        preset = st.selectbox("Period", [
            "Last 7 days", "Last 30 days", "Current week",
            "Current month", "Current year", "Custom",
        ])
        if preset == "Last 7 days":
            start, end = today - timedelta(days=7), today
        elif preset == "Last 30 days":
            start, end = today - timedelta(days=30), today
        elif preset == "Current week":
            start = today - timedelta(days=today.weekday())
            end = today
        elif preset == "Current month":
            start = today.replace(day=1)
            end = today
        elif preset == "Current year":
            start = today.replace(month=1, day=1)
            end = today
        else:
            col_s, col_e = st.columns(2)
            start = col_s.date_input("From", value=today - timedelta(days=30), format="DD/MM/YYYY")
            end = col_e.date_input("To", value=today, format="DD/MM/YYYY")

        if st.button("Generate report", type="primary"):
            log_dir = _Path(_VAULT_ROOT) / "Backlog - to do - app" / "Log"
            entries = {"CRIADA": [], "ALTERADA": [], "CONCLUÍDA": [], "TO-DO": []}
            current = start
            while current <= end:
                log_file = log_dir / f"diario-{current.isoformat()}.md"
                if log_file.exists():
                    for line in log_file.read_text(encoding="utf-8").splitlines():
                        for label in entries:
                            if f"`{label}`" in line:
                                entries[label].append(line.strip())
                current += timedelta(days=1)

            total_events = sum(len(v) for v in entries.values())
            period_str = f"{start.strftime('%d/%m/%Y')} to {end.strftime('%d/%m/%Y')}"

            report_md = f"# Report — {period_str}\n\n"
            report_md += f"**Period:** {period_str}  \n"
            report_md += f"**Total events:** {total_events}\n\n"
            report_md += f"| Type | Count |\n|---|---|\n"
            for label, items in entries.items():
                report_md += f"| {label} | {len(items)} |\n"
            for label, items in entries.items():
                if items:
                    report_md += f"\n## {label} ({len(items)})\n"
                    for item in items:
                        report_md += f"{item}\n"

            st.markdown(report_md)
            st.divider()

            col_save, _ = st.columns([2, 3])
            with col_save:
                if st.button("💾 Save to vault"):
                    fname = f"report-{start.isoformat()}-{end.isoformat()}.md"
                    out = log_dir / fname
                    frontmatter = f"---\ndate: {today.isoformat()}\ntype: report\nperiodo: {period_str}\ntags: [report, backlog]\n---\n\n"
                    out.write_text(frontmatter + report_md, encoding="utf-8")
                    st.success(f"Saved to Log/{fname}")

    if st.button("📋 Generate period report"):
        _report_dialog()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 4 — TUTORIAL
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📖 Tutorial":
    st.header("📖 Installation Tutorial")
    st.caption("Complete guide to install and configure TechColab Backlog on a new machine.")

    st.info("**Source code:** [github.com/keok-netzsch/techcolab-backlog](https://github.com/keok-netzsch/techcolab-backlog)", icon="📦")

    st.markdown("""
## Prerequisites

| Tool | Minimum version | Download |
|---|---|---|
| Python | 3.10 | python.org/downloads |
| Ollama | Any recent | ollama.com/download |
| Obsidian | Any recent | obsidian.md |
| Git | Any recent | git-scm.com |

> **Tip:** When installing Python on Windows, check the **"Add Python to PATH"** option before clicking Install Now.

---

## Installation

### Step 1 — Clone the repository

```bat
git clone https://github.com/keok-netzsch/techcolab-backlog.git
cd techcolab-backlog
```

### Step 2 — Install dependencies

**Option A — Automatic script (recommended)**

Double-click **`install.bat`** in the project folder.

**Option B — Manual**

```bat
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
```

---

## Configuration

Open **`config.py`** and set `VAULT_ROOT` to your Obsidian vault path:

```python
VAULT_ROOT = r"C:\\Users\\YourUser\\Documents\\MyVault"
```

Or set the environment variable `TECHCOLAB_VAULT` (takes precedence over `config.py`):

```bat
set TECHCOLAB_VAULT=C:\\Users\\YourUser\\Documents\\MyVault
```

**How to find the path:** Obsidian → Settings → About → Vault path.

> Use `r"..."` before the quotes (raw string) to avoid issues with backslashes on Windows.

---

## Ollama model download

```bat
ollama pull llama3.2:3b
```

Download ~2 GB. To verify: `ollama list` — the model should appear in the list.

---

## Starting the app

- **Easiest:** double-click **`start_app.bat`**
- **Command line:**
  ```bat
  .venv\\Scripts\\activate
  streamlit run app.py
  ```
- Access at: **http://localhost:8501**

---

## Using the app

| Section | Purpose |
|---|---|
| 📋 Backlog | Create, edit and view ideas |
| ✅ To-Do List | All action items consolidated |
| 📊 Dashboard | Metrics, scoring and period report |

**Status flow:**
```
backlog → under review → approved → waiting → in development → in validation → done ✅
                       └─► rejected / discarded ⛔
```

---

## Daily agent

The agent runs every morning at 08:00, analyses the backlog, and proposes actions.
You interact with it in two steps:

### Step 1 — Review the report (Obsidian)

Open the file `Backlog - to do - app/agent-reports/report-YYYY-MM-DD.md` in Obsidian.

The **Proposed actions** section lists specific to-dos from your backlog, grouped by idea:

```
**`idea-004`** ⭐⭐⭐ _Análise de agentes_ — Backlog, effort: ?
- [ ] Criar um fluxo de ideias

**`idea-008`** ⭐⭐⭐ _Planejamento OKR FY27_ — Backlog, effort: médio
- [ ] Pensar em áreas de melhoria (due 2026-05-29)
- [ ] Incluir item sobre adesão de AI no time
```

Check the boxes (`- [x]`) next to every to-do you want the agent to implement.
Leave unchecked what you don't approve — the agent will not touch those.

### Step 2 — Execute approved items (Claude Code)

1. Double-click **`execute_agent.bat`** in the project folder
2. A terminal opens showing today's report path and a confirmation prompt — press any key
3. Claude Code opens in the project directory
4. Type exactly:

```
Execute the approved items from today's agent report
```

5. Claude reads the report, lists the approved to-dos, and asks you to confirm
6. After confirmation, Claude implements each to-do, runs the tests, and commits

> **Tip:** You can be more specific — e.g. *"Execute only the first two approved items"*
> or *"Skip idea-008, execute the rest."*

---

## Troubleshooting

| Issue | Solution |
|---|---|
| Connection error when suggesting to-dos | Start Ollama (tray icon) |
| App shows stale data | Click **🔄 Reload ideas** in the sidebar |
| Port 8501 in use | `streamlit run app.py --server.port 8502` |
| "python not recognized" | Reinstall Python with "Add to PATH" checked |
| pip install error | Activate `.venv` first: `.venv\\Scripts\\activate` |
| Agent report not found | Run `run_agent.bat` manually to generate it |
| `TECHCOLAB_VAULT` error in app | Restart the app — the env var is set but needs a new process |
""")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 5 — DOCUMENTAÇÃO
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📚 Documentation":
    st.header("📚 Documentation & Context")
    st.info("**Repository:** [github.com/keok-netzsch/techcolab-backlog](https://github.com/keok-netzsch/techcolab-backlog)", icon="📦")

    st.markdown("## Overview")
    st.markdown("""
**TechColab Backlog** is a personal idea management system integrated with Obsidian.
The goal is to capture and structure ideas using a local language model (Ollama) —
no API key, no per-use cost, no data leaving your machine.
""")

    st.divider()
    st.markdown("## System architecture")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
**Extraction pipeline**

```
Manual form (app)
    ↓ store.py — saves idea-NNN.md
    ↓ daily_log.py — records to log
Backlog - to do - app/backlog items/
```
""")
    with col2:
        st.markdown("""
**Vault structure**

```
TechColab_D&A_KO/
└── Backlog - to do - app/
    ├── backlog items/
    │   ├── idea-001.md
    │   └── idea-002.md
    ├── Log/
    │   └── diario-YYYY-MM-DD.md
    ├── _index.md
    └── Documentacao.md
```
""")

    st.divider()
    st.markdown("## Idea file format")
    st.code("""---
id: idea-001
titulo: "Nome da ideia"
status: backlog
prioridade: alta
area: dados
origem: entrada direta
criado_em: 2026-05-15
atualizado_em: 2026-05-15
due_date: 2026-06-30
---

## Descricao
Descrição da ideia.

## To-dos
- [ ] Next pending step
- [x] Step already done @2026-05-20

## Notas
Anotações livres.
""", language="markdown")

    st.divider()
    st.markdown("## Current configuration")

    config_data = {
        "Vault": str(VAULT_ROOT),
        "Items folder": str(BACKLOG_DIR),
        "LLM model": EXTRACTION_MODEL,
        "Ollama endpoint": OLLAMA_BASE_URL,
    }
    for k, v in config_data.items():
        st.markdown(f"**{k}:** `{v}`")

    st.caption("To change settings, edit the `config.py` file in the project root.")

    st.divider()
    st.markdown("## Planned next phases")
    st.markdown("""
- **Phase 2** — Analysis agent: given an idea "under review", researches, validates hypotheses and generates a report
- **Phase 3** — Parallel orchestrator: runs multiple analyses simultaneously
- **Phase 4** — Notion integration (optional bidirectional sync)
""")

elif page == "📈 Claude Pro":
    import streamlit.components.v1 as components
    from config import CLAUDE_PRO_REPORT_HTML
    st.markdown('<h1 style="margin-bottom:0.2rem">Claude Pro Report</h1>',
                unsafe_allow_html=True)
    st.caption("Relatório vivo de uso do Claude Pro · NBS D&A · Techco.lab — "
               "atualizado automaticamente pelo agente diário")
    if CLAUDE_PRO_REPORT_HTML.exists():
        _report_html = CLAUDE_PRO_REPORT_HTML.read_text(encoding="utf-8")
        components.html(_report_html, height=900, scrolling=True)
    else:
        st.warning(
            f"Relatório não encontrado em `{CLAUDE_PRO_REPORT_HTML}`. "
            "Execute o agente diário para gerar o arquivo."
        )
