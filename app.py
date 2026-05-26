"""
Personal Toolkit · Techco.lab — Streamlit UI
Run with: streamlit run app.py
"""

import sys
import json
import requests
from pathlib import Path
from datetime import date

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from config import BACKLOG_DIR, BACKLOG_ARCHIVE_DIR, VAULT_ROOT, EXTRACTION_MODEL, OLLAMA_BASE_URL, CLAUDE_PRO_START_DATE
from backlog.store import BacklogStore
from backlog.schema import VALID_STATUSES, VALID_PRIORITIES, VALID_IMPACTS, VALID_EFFORTS, VALID_AREAS
from backlog.daily_log import log_entry

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Personal Toolkit · Techco.lab",
    page_icon="🤖",
    layout="wide",
)

# ── Dark mode (read early — used by CSS injection and nav) ─────────────────────
_dark_mode = st.query_params.get("dark", "0") == "1"

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

/* ── Prevent outer page scroll ───────────────────────────── */
html, body { overflow: hidden !important; height: 100vh !important; }
[data-testid="stAppViewContainer"] { height: 100vh !important; overflow: hidden !important; }
[data-testid="stMain"] { height: 100vh !important; overflow: hidden !important; }
[data-testid="stMainBlockContainer"] {
    height: 100vh !important;
    overflow-y: auto !important;
    overflow-x: hidden !important;
    padding-bottom: 1rem !important;
}

/* ── Top navigation (pure HTML) ──────────────────────────── */
div[data-testid="stSidebar"] { display: none !important; }
[data-testid="stMainBlockContainer"] {
    padding-top: 0 !important;
    padding-bottom: 0.5rem !important;
}

/* ── Global: never wrap button text ──────────────────────── */
button { white-space: nowrap !important; }

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

/* Idea row buttons — only inside scrollable list containers (backlog, todo-list) */
[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stHorizontalBlock"] .stButton > button[kind="secondary"]:not([data-testid*="nav_"]) {
    text-align: left !important;
    justify-content: flex-start !important;
    background: transparent !important;
    border: none !important;
    color: #2A2A2A !important;
    font-size: 0.9rem !important;
}
[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stHorizontalBlock"] .stButton > button[kind="secondary"]:not([data-testid*="nav_"]):hover {
    background: rgba(2,183,147,0.07) !important;
    color: #007167 !important;
}
</style>
"""

_DARK_CSS = """
<style>
/* ── Dark mode ─────────────────────────────────────────────────────────────── */
html, body { background-color: #0E1117 !important; color: #E2E8F0 !important; }
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
[data-testid="stMainBlockContainer"] { background-color: #0E1117 !important; }

/* Column/block containers — fixes transparent buttons showing white Streamlit bg */
[data-testid="column"],
[data-testid="stHorizontalBlock"],
[data-testid="stVerticalBlock"] { background-color: #0E1117; }

/* Containers with border */
[data-testid="stVerticalBlockBorderWrapper"] > div {
    background: #1A1D2E !important;
    border-color: #2D3748 !important;
}

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

/* General secondary buttons */
.stButton > button[kind="secondary"] {
    background: #1A1D2E !important;
    border-color: #2D3748 !important;
    color: #E2E8F0 !important;
}
.stButton > button[kind="secondary"]:hover {
    background: #1E2640 !important;
    border-color: #02B793 !important;
}

/* Idea row borderless buttons — keep transparent (now shows dark container bg) */
[data-testid="stHorizontalBlock"]:not([data-sidebar]) .stButton > button[kind="secondary"]:not([data-testid*="nav_"]) {
    background: transparent !important;
    border: none !important;
    color: #CBD5E0 !important;
}
[data-testid="stHorizontalBlock"]:not([data-sidebar]) .stButton > button[kind="secondary"]:not([data-testid*="nav_"]):hover {
    background: rgba(2,183,147,0.1) !important;
    color: #0AD4A8 !important;
}

/* Sidebar footer icon buttons */
.sidebar-footer .stButton > button {
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

/* ── Calendar dark overrides ─────────────────────────────────────────────── */
.cal-th  { border-bottom-color: #2D3748 !important; color: #64748B !important; }
.cal-td  { border-color: #1F2937 !important; background: #0E1117 !important; }
.cal-td-today { background: rgba(2,183,147,0.06) !important; }
.cal-dnum-cur { color: #02B793 !important; }
.cal-future   { background: rgba(100,116,139,0.1) !important;
                border-color: #475569 !important; color: #94A3B8 !important; }
.cal-overdue  { background: rgba(239,68,68,0.12) !important; }
.cal-today    { background: rgba(245,158,11,0.12) !important; }
.cal-soon     { background: rgba(2,183,147,0.1) !important; }
.cal-more     { color: #64748B !important; }

/* Scrollbars */
::-webkit-scrollbar { background: #161B2E; width: 6px; }
::-webkit-scrollbar-thumb { background: #2D3748; border-radius: 4px; }

/* ── Markdown tables ─────────────────────────────────────────────────────── */
[data-testid="stMarkdownContainer"] table { background: #1A1D2E !important; width: 100% !important; }
[data-testid="stMarkdownContainer"] th {
    background: #161B2E !important; color: #64748B !important;
    border: 1px solid #2D3748 !important; padding: 8px 12px !important;
}
[data-testid="stMarkdownContainer"] td {
    background: #1A1D2E !important; color: #CBD5E0 !important;
    border: 1px solid #2D3748 !important; padding: 8px 12px !important;
}
[data-testid="stMarkdownContainer"] tr:hover td { background: #1E2640 !important; }
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
_PAGES_MAIN = ["Dashboard", "Backlog", "To-Do List", "Claude Pro", "Weekly Brief", "English Coach"]
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
                _nsc2.caption(_nstgd["text"])
                if _nsc3.button("✕", key=f"rm_ni_staged_{_nsi}", help="Remove"):
                    st.session_state["ni_staged_todos"].pop(_nsi)
                    st.rerun()

            # Input row
            _ni_col_txt, _ni_col_btn = st.columns([10, 1])
            with _ni_col_txt:
                ni_new_todo = st.text_input(
                    "To-dos", placeholder="Add a to-do and press ➕...",
                    key=f"ni_new_todo_{_ni_ctr}",
                )
            with _ni_col_btn:
                st.markdown('<div style="margin-top:28px">', unsafe_allow_html=True)
                if st.button("➕", key="ni_add_todo_btn",
                             disabled=not ni_new_todo.strip(),
                             use_container_width=True):
                    st.session_state["ni_staged_todos"].append(
                        {"text": ni_new_todo.strip(), "done": False, "due_date": None}
                    )
                    st.session_state[_ni_ctr_key] += 1
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

            if st.button("Add to backlog", type="primary", disabled=not ni_title.strip()):
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
                    agente_autorizado=False,
                )
                log_entry("criada", idea)
                _rebuild_index(store)
                st.session_state["backlog_flash"] = ("success", f"✅ {idea.id} added to backlog.")
                st.session_state["backlog_panel"] = None
                for k in ["ni_title", "ni_area", "ni_desc", "ni_priority", "ni_impact", "ni_effort",
                          "ni_suggested_todos", "ni_staged_todos"]:
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
    col_f1, col_f2, col_f3 = st.columns([1.2, 1.8, 5])
    with col_f1:
        filter_priority = st.multiselect("Priority", VALID_PRIORITIES, placeholder="All",
                                         format_func=lambda x: PRIORITY_LABEL.get(x, x))
    with col_f2:
        filter_status = st.multiselect("Status", VALID_STATUSES, placeholder="All statuses",
                                       format_func=lambda x: STATUS_LABEL.get(x, x))
    with col_f3:
        filter_text = st.text_input("Search", placeholder="Title, description or notes...")

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
            with st.container(height=600, border=False):
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
                        _ktitle = idea.title.replace("**", "").strip()
                        card_col.markdown(
                            f"{picon} `{idea.id}`  \n**{_ktitle[:45]}**"
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
            _h1, _h2, _h3, _h4 = st.columns([0.06, 0.09, 0.04, 0.81])
            _h1.caption("ID")
            _h2.caption("Prio")
            _h3.caption("Status")
            _h4.caption("Backlog item")
            st.markdown('<hr style="margin:2px 0 6px 0;border-color:rgba(76,77,88,0.12)">', unsafe_allow_html=True)

            with st.container(height=600, border=False):
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

                    c1, c2, c3, c4 = st.columns([0.06, 0.09, 0.04, 0.81])
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

                            re_col, tips_col, hist_col, tr_col = st.columns([2, 2, 2, 2])
                            with tr_col:
                                if st.button("🌐 Translate", key=f"translate_{idea.id}",
                                             help="Translate title, description and to-dos between PT ↔ EN using Ollama"):
                                    _active_idx = [
                                        idx for idx, _ in enumerate(idea.todos)
                                        if idx not in st.session_state.get(deleted_idx_key, set())
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
                                    from ingestion.extractor import suggest_todos, build_client
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
                                    from ingestion.extractor import suggest_claude_tips, build_client
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
                            h_state, h_txt, h_date, h_auto, h_bug, h_del = st.columns([0.6, 7.5, 1.5, 0.4, 0.4, 0.4])
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
                                c_state, c_txt, c_date, c_auto, c_bug, c_del = st.columns([0.7, 6, 2, 0.5, 0.5, 0.5], vertical_alignment="center")
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
                                "div[data-testid='stMarkdown']:has(.save-del-marker)"
                                " ~ div[data-testid='stColumns']"
                                " > div[data-testid='column']:nth-child(2) button"
                                "{ border-color:rgba(185,28,28,0.5)!important; color:#B91C1C!important; }"
                                "div[data-testid='stMarkdown']:has(.save-del-marker)"
                                " ~ div[data-testid='stColumns']"
                                " > div[data-testid='column']:nth-child(2) button:hover"
                                "{ background:rgba(185,28,28,0.85)!important; color:#fff!important;"
                                " border-color:#B91C1C!important; }"
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
    st.markdown('<h1 style="margin-bottom:0.4rem">To-Do List</h1>', unsafe_allow_html=True)
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
                "is_bug": todo.get("is_bug", False),
                "todo_idx": idx,
                "text": todo["text"],
                "done": todo["done"],
                "in_progress": todo.get("in_progress", False),
                "due_date": todo.get("due_date"),
                "completed_at": todo.get("completed_at"),
            })

    if not all_todos:
        st.info("No to-dos found. Add to-dos to ideas in the Backlog.")
    else:
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

        pending_count = sum(1 for t in filtered_todos if not t["done"])
        in_progress_count = sum(1 for t in filtered_todos if not t["done"] and t.get("in_progress"))
        done_count = sum(1 for t in filtered_todos if t["done"])
        ip_badge = f" · **{in_progress_count} 🔄 in progress**" if in_progress_count else ""
        st.markdown(f"**{pending_count} pending**{ip_badge} · {done_count} done out of {len(filtered_todos)} shown")
        st.markdown(
            "<style>"
            "div.tdl-num button {"
            " background:#F3F4F6!important; border:none!important; box-shadow:none!important;"
            " border-radius:4px!important; font-size:0.73rem!important; font-weight:700!important;"
            " color:#6B7280!important; padding:1px 2px!important;"
            " min-height:22px!important; width:100%!important; }"
            "div.tdl-num button:hover {"
            " background:rgba(2,183,147,0.12)!important; color:#007167!important; }"
            "div.tdl-sel div[data-testid='stSelectbox'] > div > div {"
            " min-height:26px!important; padding:1px 6px!important; font-size:0.82rem!important; }"
            "</style>",
            unsafe_allow_html=True,
        )

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

        from itertools import groupby
        if group_by == "Date":
            filtered_todos.sort(key=lambda t: (_GROUP_DATA_ORDER.get(_due_group(t), 9), t["idea_id"]))
        elif group_by == "Priority":
            filtered_todos.sort(key=lambda t: (prio_order.get(t["priority"], 9), t["idea_id"]))
        else:
            filtered_todos.sort(key=get_group_key)
        store = get_store()
        today = date.today()

        # In "Pending" filter, always include this-week done items (show as strikethrough)
        if show_filter == "Pending":
            this_week_done = [
                t for t in all_todos
                if t["done"] and _due_group(t) == "📅 This week"
                and (filter_area == "All" or t["area"] == filter_area)
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

        # ── Sort state ─────────────────────────────────────────────────────────
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

        # ── Header row ─────────────────────────────────────────────────────────
        _h1, _h2, _h3, _h4, _h5, _h6 = st.columns(_TDL_COLS)
        _hdrbtn("#", "id", _h1)
        _hdrbtn("Prio", "priority", _h2)
        _h3.caption("")
        _hdrbtn("Estado", "state", _h4)
        _hdrbtn("To-Do · Backlog item", "text", _h5)
        _hdrbtn("Prazo", "due_date", _h6)

        # ── Rows (scrollable, header stays pinned above) ────────────────────────
        _STATE_OPTS = ["⬜", "🔄", "✅"]
        _STATE_IDX  = {"open": 0, "in_progress": 1, "done": 2}
        st.markdown(
            "<style>div[data-testid='stVerticalBlockBorderWrapper']"
            "{ height:calc(100vh - 360px)!important; }</style>",
            unsafe_allow_html=True,
        )
        with st.container(height=600, border=False):
            for group_label, group_items in groupby(filtered_todos, key=get_group_key):
                items = list(group_items)
                # intra-group sort by header column
                if _sc == "id":
                    items.sort(key=lambda t: t["idea_id"], reverse=(_sd == -1))
                elif _sc == "priority":
                    items.sort(key=lambda t: prio_order.get(t["priority"], 9), reverse=(_sd == -1))
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
                    idea = store.load_by_id(item["idea_id"])
                    if not idea:
                        continue

                    c_id, c_prio, c_status, c_chk, c_text, c_info = st.columns(_TDL_COLS, vertical_alignment="center")

                    short = str(int(item["idea_id"].replace("idea-", "")))
                    with c_id:
                        st.markdown('<div class="tdl-num">', unsafe_allow_html=True)
                        if st.button(short, key=f"nav_{item['idea_id']}_{item['todo_idx']}",
                                     use_container_width=True):
                            st.session_state["page"] = "Backlog"
                            st.session_state[f"exp_{item['idea_id']}"] = True
                            st.rerun()
                        st.markdown('</div>', unsafe_allow_html=True)

                    c_prio.markdown(PRIORITY_NUM.get(item["priority"], "⚪"), unsafe_allow_html=True)
                    c_status.markdown(STATUS_COLOR.get(item["status"], _sdot("backlog")), unsafe_allow_html=True)

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
                    new_state = ["open", "in_progress", "done"][_STATE_OPTS.index(sel)]
                    state_clicked = new_state != cur_state

                    with c_text:
                        if item["done"]:
                            text_html = f"<s>{item['text']}</s>"
                        elif item.get("in_progress"):
                            text_html = f"<em>{item['text']}</em>"
                        else:
                            text_html = item["text"]
                        bug_badge = (
                            ' <span style="background:#FEE2E2;color:#B91C1C;font-size:9px;font-weight:700;'
                            'letter-spacing:.04em;padding:1px 4px;border-radius:3px;vertical-align:middle">BUG</span>'
                            if item.get("is_bug") else ""
                        )
                        idea_ref = (
                            f'<div style="font-size:0.72rem;color:#9CA3AF;margin-top:1px">'
                            f'<code style="font-size:0.68rem;background:#F3F4F6;padding:0 3px;'
                            f'border-radius:2px;color:#6B7280">{item["idea_id"]}</code>'
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
                        todo_entry["done"] = new_state == "done"
                        todo_entry["in_progress"] = new_state == "in_progress"
                        todo_entry["completed_at"] = today.isoformat() if new_state == "done" else None
                        store.save(idea)
                        if new_state == "done":
                            log_entry("todo_concluido", idea, item["text"])
                        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3 — DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Dashboard":
    from datetime import timedelta, date as _date
    import re as _re

    st.markdown('<h1 style="margin-bottom:0.4rem">Dashboard</h1>', unsafe_allow_html=True)

    st.subheader("Claude Code Activity")
    st.caption("Real activity from session files `~/.claude/projects/`")

    # ── Session state for period filter ──────────────────────────────
    if "cc_window" not in st.session_state:
        st.session_state["cc_window"] = 0  # 0 = todos, 30, 7

    # ── All-time stats loader ─────────────────────────────────────────
    def _load_full_cc_stats():
        import json, re as _re2
        from collections import Counter
        from datetime import datetime as _dt

        msgs_by_day:   Counter = Counter()
        msgs_by_hour:  Counter = Counter()
        tokens_by_day: Counter = Counter()
        output_by_day: Counter = Counter()
        cache_read = cache_create = 0
        model_counts: Counter = Counter()
        sessions: set = set()
        projects: Counter = Counter()

        _hist = Path.home() / ".claude" / "history.jsonl"
        if _hist.exists():
            try:
                with open(_hist, encoding="utf-8") as _hf:
                    for _line in _hf:
                        try:
                            _e = json.loads(_line)
                            _p = _e.get("project", "")
                            if _p:
                                projects[Path(_p).name] += 1
                        except Exception:
                            continue
            except Exception:
                pass

        _pdir = Path.home() / ".claude" / "projects"
        if _pdir.exists():
            for _jf in _pdir.glob("**/*.jsonl"):
                sessions.add(_jf.stem)
                try:
                    with open(_jf, encoding="utf-8") as _sf:
                        for _line in _sf:
                            try:
                                _e = json.loads(_line)
                                _ts = _e.get("timestamp", "")
                                if not _ts:
                                    continue
                                _dobj = _dt.fromisoformat(_ts.replace("Z", "+00:00"))
                                _d = _dobj.date()
                                _etype = _e.get("type", "")
                                if _etype == "user":
                                    _msg = _e.get("message", _e)
                                    _cnt = _msg.get("content", "")
                                    if isinstance(_cnt, str) and _cnt.strip():
                                        msgs_by_day[_d] += 1
                                        msgs_by_hour[_dobj.hour] += 1
                                elif _etype == "assistant":
                                    _mod = _e.get("message", {}).get("model", "")
                                    if _mod and _mod != "<synthetic>":
                                        model_counts[_mod] += 1
                                    _usage = _e.get("message", {}).get("usage")
                                    if _usage:
                                        _inp = _usage.get("input_tokens", 0)
                                        _out = _usage.get("output_tokens", 0)
                                        _cr  = _usage.get("cache_read_input_tokens", 0)
                                        _cc2 = _usage.get("cache_creation_input_tokens", 0)
                                        tokens_by_day[_d] += _inp + _out + _cr + _cc2
                                        output_by_day[_d] += _out
                                        cache_read  += _cr
                                        cache_create += _cc2
                            except Exception:
                                continue
                except Exception:
                    continue

        return dict(
            sessions=len(sessions),
            msgs_by_day=msgs_by_day,
            msgs_by_hour=msgs_by_hour,
            tokens_by_day=tokens_by_day,
            output_by_day=output_by_day,
            cache_read=cache_read,
            cache_create=cache_create,
            models=model_counts,
            projects=projects,
        )

    def _fmt_model(m: str) -> str:
        import re as _re3
        m2 = m.lower().removeprefix("claude-")
        m2 = _re3.sub(r"-\d{8,}$", "", m2)
        parts = m2.split("-")
        if len(parts) >= 3:
            return f"{parts[0].capitalize()} {parts[1]}.{parts[2]}"
        if len(parts) == 2:
            return f"{parts[0].capitalize()} {parts[1]}"
        return m2.capitalize()

    def _fmt_tok(n: int) -> str:
        if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
        if n >= 1_000:     return f"{n/1_000:.1f}K"
        return str(n)

    def _compute_streaks(active_days):
        from datetime import timedelta as _td3
        if not active_days:
            return 0, 0
        _sd = sorted(active_days)
        _max_s = _cur_s = 1
        for _i in range(1, len(_sd)):
            if (_sd[_i] - _sd[_i - 1]).days == 1:
                _cur_s += 1
                _max_s = max(_max_s, _cur_s)
            else:
                _cur_s = 1
        _today2 = date.today()
        _streak = 0
        _start = _today2 if _today2 in active_days else (
            _today2 - _td3(days=1) if (_today2 - _td3(days=1)) in active_days else None
        )
        if _start:
            _dd = _start
            while _dd in active_days:
                _streak += 1
                _dd -= _td3(days=1)
        return _streak, _max_s

    def _fun_tagline(total_tokens: int) -> str:
        _refs = [
            (95_000,  "The Hobbit"),
            (100_000, "Harry Potter and the Philosopher's Stone"),
            (120_000, "1984 by Orwell"),
            (163_000, "Pride and Prejudice"),
            (775_000, "War and Peace"),
        ]
        for _tok, _name in _refs:
            if total_tokens >= _tok * 1.5:
                _ratio = round(total_tokens / _tok)
                return f'You used ~{_ratio}&times; more tokens than <em>{_name}</em>.'
        if total_tokens >= 50_000:
            return 'You have accumulated enough tokens to write a novel.'
        return f'You have accumulated {_fmt_tok(total_tokens)} tokens so far.'

    # ── Load all-time data ────────────────────────────────────────────
    _all_stats = _load_full_cc_stats()

    # ── Period filter buttons ─────────────────────────────────────────
    _w = st.session_state.get("cc_window", 0)
    _pc1, _pc2, _pc3, _pc4 = st.columns([6, 1, 1, 1])
    with _pc2:
        if st.button("All", type="primary" if _w == 0 else "secondary",
                     use_container_width=True, key="cc_all"):
            st.session_state["cc_window"] = 0
            st.rerun()
    with _pc3:
        if st.button("30d", type="primary" if _w == 30 else "secondary",
                     use_container_width=True, key="cc_30d"):
            st.session_state["cc_window"] = 30
            st.rerun()
    with _pc4:
        if st.button("7d", type="primary" if _w == 7 else "secondary",
                     use_container_width=True, key="cc_7d"):
            st.session_state["cc_window"] = 7
            st.rerun()

    # Apply period filter to displayed metrics
    from datetime import timedelta as _td
    if _w > 0:
        _cutoff_disp  = date.today() - _td(days=_w - 1)
        _msgs_by_day  = {d: c for d, c in _all_stats["msgs_by_day"].items()   if d >= _cutoff_disp}
        _tk_total     = {d: c for d, c in _all_stats["tokens_by_day"].items() if d >= _cutoff_disp}
        _tk_out       = {d: c for d, c in _all_stats["output_by_day"].items() if d >= _cutoff_disp}
    else:
        _msgs_by_day  = dict(_all_stats["msgs_by_day"])
        _tk_total     = dict(_all_stats["tokens_by_day"])
        _tk_out       = dict(_all_stats["output_by_day"])
    _cr_total    = _all_stats["cache_read"]
    _cc_total    = _all_stats["cache_create"]
    _cc_projects = _all_stats["projects"]

    if not _all_stats["msgs_by_day"] and not _all_stats["tokens_by_day"]:
        st.info("No data found in `~/.claude/`.")
    else:
        _total_msgs   = sum(_msgs_by_day.values())
        _total_tk_val = sum(_tk_total.values())
        _active_days  = set(_msgs_by_day.keys())
        _streak_cur, _streak_max = _compute_streaks(_active_days)
        _peak_h       = max(_all_stats["msgs_by_hour"], key=_all_stats["msgs_by_hour"].get) \
                        if _all_stats["msgs_by_hour"] else 0
        _fav_mod      = max(_all_stats["models"], key=_all_stats["models"].get) \
                        if _all_stats["models"] else ""
        _fav_mod_str  = _fmt_model(_fav_mod) if _fav_mod else "—"
        _total_out    = sum(_tk_out.values())
        _cache_pct    = round(_cr_total / (_cr_total + _cc_total) * 100) \
                        if (_cr_total + _cc_total) > 0 else 0
        _num_projects = len(_cc_projects)

        # ── Stats grid 3×4 ────────────────────────────────────────────
        _sg_html = (
            '<style>'
            '.cc-sg{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin:.5rem 0}'
            '.cc-sc{background:#F9FAFB;border:1px solid #E5E7EB;border-radius:8px;padding:8px 12px}'
            '.cc-sl{font-size:.7rem;color:#6B7280;font-weight:500;margin-bottom:2px;white-space:nowrap}'
            '.cc-sv{font-size:1.2rem;font-weight:700;color:#111827;line-height:1.2}'
            '</style>'
            '<div class="cc-sg">'
            # Row 1 — atividade
            f'<div class="cc-sc"><div class="cc-sl">Sessions</div>'
            f'<div class="cc-sv">{_all_stats["sessions"]}</div></div>'
            f'<div class="cc-sc"><div class="cc-sl">Messages</div>'
            f'<div class="cc-sv">{_total_msgs:,}</div></div>'
            f'<div class="cc-sc"><div class="cc-sl">Active days</div>'
            f'<div class="cc-sv">{len(_active_days)}</div></div>'
            f'<div class="cc-sc"><div class="cc-sl">Peak hour</div>'
            f'<div class="cc-sv">{_peak_h:02d}h</div></div>'
            # Row 2 — tokens
            f'<div class="cc-sc"><div class="cc-sl">Total de tokens</div>'
            f'<div class="cc-sv">{_fmt_tok(_total_tk_val)}</div></div>'
            f'<div class="cc-sc"><div class="cc-sl">Output gerado</div>'
            f'<div class="cc-sv">{_fmt_tok(_total_out)}</div></div>'
            f'<div class="cc-sc"><div class="cc-sl">Cache hits</div>'
            f'<div class="cc-sv">{_fmt_tok(_cr_total)}</div></div>'
            f'<div class="cc-sc"><div class="cc-sl">Cache efficiency</div>'
            f'<div class="cc-sv">{_cache_pct}%</div></div>'
            # Row 3 — streaks, modelo, projetos
            f'<div class="cc-sc"><div class="cc-sl">Current streak</div>'
            f'<div class="cc-sv">{_streak_cur}d</div></div>'
            f'<div class="cc-sc"><div class="cc-sl">Longest streak</div>'
            f'<div class="cc-sv">{_streak_max}d</div></div>'
            f'<div class="cc-sc"><div class="cc-sl">Modelo favorito</div>'
            f'<div class="cc-sv" style="font-size:.9rem">{_fav_mod_str}</div></div>'
            f'<div class="cc-sc"><div class="cc-sl">Projects</div>'
            f'<div class="cc-sv">{_num_projects}</div></div>'
            '</div>'
        )
        st.markdown(_sg_html, unsafe_allow_html=True)

        # ── Contribution heatmap (52 weeks) ───────────────────────────
        _today_d  = date.today()
        _hm_start = _today_d - _td(days=364)
        _hm_start = _hm_start - _td(days=_hm_start.weekday())  # align to Monday

        def _hm_clr(n):
            if n == 0:  return "#1A2030" if _dark_mode else "#E9ECEF"
            if n <= 2:  return "#064E3B" if _dark_mode else "#A7F3D0"
            if n <= 6:  return "#065F46" if _dark_mode else "#34D399"
            if n <= 14: return "#047857" if _dark_mode else "#059669"
            return "#02B793"

        _hm_weeks = []
        _cur = _hm_start
        while _cur <= _today_d:
            _wk = []
            for _dow in range(7):
                _d2 = _cur + _td(days=_dow)
                _n2 = _all_stats["msgs_by_day"].get(_d2, 0) if _d2 <= _today_d else 0
                _wk.append((_d2 if _d2 <= _today_d else None, _n2))
            _hm_weeks.append(_wk)
            _cur += _td(days=7)

        # Month labels
        _mo_labels = [""] * len(_hm_weeks)
        _last_mo = -1
        for _wi2, _wk2 in enumerate(_hm_weeks):
            for _d3, _ in _wk2:
                if _d3 and _d3.month != _last_mo:
                    _mo_labels[_wi2] = _d3.strftime("%b")
                    _last_mo = _d3.month
                    break

        _mo_html = "".join(
            f'<div style="min-width:12px;font-size:9px;color:#9CA3AF;text-align:left">{m}</div>'
            for m in _mo_labels
        )
        _dow_html = "".join(
            f'<div style="height:12px;font-size:9px;color:#9CA3AF;line-height:12px">{lb}</div>'
            for lb in ["Mon", "", "Wed", "", "Fri", "", ""]
        )
        _cells_html = ""
        for _wk3 in _hm_weeks:
            _cells_html += '<div style="display:flex;flex-direction:column;gap:1px">'
            for _d4, _n4 in _wk3:
                if _d4 is None:
                    _cells_html += '<div style="width:11px;height:11px"></div>'
                else:
                    _border = "2px solid #047857" if _d4 == _today_d else "none"
                    _tip = f"{_d4.strftime('%d/%b')}: {_n4} msg"
                    _cells_html += (
                        f'<div title="{_tip}" style="width:11px;height:11px;border-radius:2px;'
                        f'background:{_hm_clr(_n4)};border:{_border}"></div>'
                    )
            _cells_html += "</div>"

        _hm_html = (
            '<div style="margin:.75rem 0 .25rem;overflow-x:auto">'
            f'<div style="display:flex;gap:1px;margin-left:26px;margin-bottom:2px">{_mo_html}</div>'
            '<div style="display:flex;gap:3px">'
            f'<div style="display:flex;flex-direction:column;gap:1px;padding-right:2px">{_dow_html}</div>'
            f'<div style="display:flex;gap:1px">{_cells_html}</div>'
            '</div></div>'
        )
        st.markdown(_hm_html, unsafe_allow_html=True)

        # ── CC Activity meta ──────────────────────────────────────────
        _total_all_tk = sum(_all_stats["tokens_by_day"].values())
        _meta_parts = []
        if _total_all_tk > 0:
            _meta_parts.append(f"<em>{_fun_tagline(_total_all_tk)}</em>")
        if _cc_projects:
            _proj_str = "  ·  ".join(
                f"<b>{n}</b> {c}" for n, c in sorted(_cc_projects.items(), key=lambda x: -x[1])[:4]
            )
            _meta_parts.append(f"Projects: {_proj_str}")
        if _meta_parts:
            st.markdown(
                f'<p style="font-size:.75rem;color:#9CA3AF;margin:.1rem 0 .8rem">'
                f'{"  ·  ".join(_meta_parts)}</p>',
                unsafe_allow_html=True,
            )

        # ── Diagnóstico ───────────────────────────────────────────────
        _last14_msgs   = sum(_all_stats["msgs_by_day"].get(date.today() - _td(days=i), 0) for i in range(14))
        _avg_day       = _last14_msgs / 14
        _total_tk_sum  = sum(_all_stats["tokens_by_day"].values())
        _total_msgs_all = sum(_all_stats["msgs_by_day"].values())
        _avg_tk_per_prompt = (_total_tk_sum / _total_msgs_all) if _total_msgs_all > 0 else 0
        _cache_pct_diag = round(_cr_total / (_cr_total + _cc_total) * 100) \
                          if (_cr_total + _cc_total) > 0 else 0

        _issues: list[tuple[str, str]] = []
        _opps:   list[tuple[str, str]] = []

        if _avg_day < 5:
            _issues.append((
                f"**Very low frequency** — {_avg_day:.1f} prompts/day on average. "
                "Claude Code is not yet integrated into the daily workflow.",
                "Bring smaller tasks: email reviews, drafts, quick data analysis, script generation. "
                "The habit forms through daily use, not just large projects.",
            ))
        elif _avg_day < 10:
            _issues.append((
                f"**Frequency below potential** — {_avg_day:.1f} prompts/day. "
                "There is room to expand usage to more types of tasks.",
                "Identify recurring tasks you still do manually and try delegating them to Claude.",
            ))

        if _avg_tk_per_prompt > 0 and _avg_tk_per_prompt < 3_000:
            _issues.append((
                f"**Underused context** — average {_avg_tk_per_prompt/1000:.1f}K tokens/prompt. "
                "Very short sessions make poor use of the 200K context available.",
                "Include the full file, not just the snippet. Describe the project, give examples. "
                "Claude responds proportionally to the context it receives.",
            ))

        if _cache_pct_diag < 30 and (_cr_total + _cc_total) > 10_000:
            _issues.append((
                f"**Underused cache** — {_cache_pct_diag}% efficiency. "
                "Few sessions reuse context from previous sessions.",
                "Open longer sessions instead of many short ones on the same topic. "
                "Use /clear only when switching subjects, not between related subtasks.",
            ))

        if _avg_day >= 5 and _avg_tk_per_prompt >= 10_000:
            _opps.append((
                "Deep session pattern",
                f"User makes {_avg_day:.1f} prompts/day with an average of {_avg_tk_per_prompt/1000:.0f}K tokens each. "
                "Identify where longer sessions would add even more value vs. where current depth is sufficient.",
            ))

        if _cache_pct_diag >= 60:
            _opps.append((
                "High context reuse",
                f"Cache efficiency at {_cache_pct_diag}%. "
                "Suggest how to structure recurring projects to further maximize this pattern.",
            ))

        if len(_cc_projects) >= 3:
            _top_proj = ", ".join(n for n, _ in sorted(_cc_projects.items(), key=lambda x: -x[1])[:3])
            _opps.append((
                "Multi-project",
                f"Usage distributed across {len(_cc_projects)} projects ({_top_proj}). "
                "Identify whether centralizing context across projects makes sense or if separate is better.",
            ))

        # ── Status indicator + single expander ───────────────────────
        _ni, _no = len(_issues), len(_opps)
        _s_color = "#EF4444" if _ni else "#059669"
        _s_icon  = "⚠" if _ni else "✓"
        _s_label = f"{_ni} {'issue' if _ni == 1 else 'issues'}" if _ni else "No issues"
        _o_label = f"{_no} {'opportunity' if _no == 1 else 'opportunities'}"
        st.markdown(
            f'<p style="font-size:.78rem;margin:.4rem 0 .3rem">'
            f'<span style="color:{_s_color}">{_s_icon} {_s_label}</span>'
            f'<span style="color:#9CA3AF">  ·  {_o_label}</span></p>',
            unsafe_allow_html=True,
        )

        if _issues or _opps:
            with st.expander("Details", expanded=False):
                for _err, _fix in _issues:
                    st.markdown(
                        f'<div style="margin:.4rem 0;padding:.5rem .75rem;border-radius:6px;'
                        f'border-left:3px solid #EF4444;background:rgba(239,68,68,.05)">'
                        f'<span style="font-size:.7rem;color:#EF4444;font-weight:700;'
                        f'text-transform:uppercase;letter-spacing:.04em">Issue</span><br>{_err}'
                        f'</div>', unsafe_allow_html=True,
                    )
                    st.markdown(
                        f'<div style="margin:-.2rem 0 .5rem;padding:.5rem .75rem;border-radius:6px;'
                        f'border-left:3px solid #059669;background:rgba(5,150,105,.05)">'
                        f'<span style="font-size:.7rem;color:#059669;font-weight:700;'
                        f'text-transform:uppercase;letter-spacing:.04em">How to fix</span><br>{_fix}'
                        f'</div>', unsafe_allow_html=True,
                    )
                if _opps:
                    for _opp_title, _opp_detail in _opps:
                        st.markdown(
                            f'<div style="margin:.4rem 0;padding:.5rem .75rem;border-radius:6px;'
                            f'border-left:3px solid #6366F1;background:rgba(99,102,241,.05)">'
                            f'<span style="font-size:.7rem;color:#6366F1;font-weight:700;'
                            f'text-transform:uppercase;letter-spacing:.04em">Opportunity</span><br>'
                            f'<b>{_opp_title}</b>  '
                            f'<span style="font-size:.85rem;color:#6B7280">{_opp_detail}</span>'
                            f'</div>', unsafe_allow_html=True,
                        )
                    _opp_ctx_prompt = "\n".join(f"- {t}: {d}" for t, d in _opps)
                    _metrics_summary = (
                        f"Prompts/day (14d): {_avg_day:.1f} | "
                        f"Tokens/prompt: {_avg_tk_per_prompt/1000:.1f}K | "
                        f"Cache: {_cache_pct_diag}% | "
                        f"Projects: {', '.join(list(_cc_projects.keys())[:3])}"
                    )
                    if st.button("Run Ollama analysis", key="cc_ollama_btn"):
                        _prompt = (
                            "You are an AI productivity consultant. "
                            "Analyze the Claude Code usage pattern below and provide actionable insights.\n\n"
                            f"Real metrics (last 14 days):\n{_metrics_summary}\n\n"
                            f"Identified opportunities:\n{_opp_ctx_prompt}\n\n"
                            "For each opportunity: explain when to use Claude in that context and when NOT to. "
                            "Be specific and practical. Maximum 200 words total. Respond in English."
                        )
                        try:
                            from openai import OpenAI as _OAI
                            _client = _OAI(base_url=OLLAMA_BASE_URL, api_key="ollama")
                            with st.spinner("Ollama analyzing..."):
                                _resp = _client.chat.completions.create(
                                    model=EXTRACTION_MODEL,
                                    messages=[{"role": "user", "content": _prompt}],
                                    temperature=0.4,
                                    max_tokens=350,
                                )
                            st.markdown(_resp.choices[0].message.content)
                        except Exception as _e:
                            st.warning(
                                f"Ollama not available (`{OLLAMA_BASE_URL}`). "
                                "Start the service with `ollama serve` to use this analysis."
                            )




# ══════════════════════════════════════════════════════════════════════════════

    st.divider()
    ideas_all = load_ideas()
    todos_all = [t for idea in ideas_all for t in idea.todos]

    total = len(ideas_all)
    active = sum(1 for i in ideas_all if i.status not in ("concluído", "descartado"))
    concluidas = sum(1 for i in ideas_all if i.status == "concluído")
    todos_done = sum(1 for t in todos_all if t["done"])
    todos_pending = sum(1 for t in todos_all if not t["done"])
    bugs_open = sum(1 for t in todos_all if t.get("is_bug") and not t["done"])

    _bk_html = (
        '<style>'
        '.cc-sg{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin:.5rem 0}'
        '.cc-sc{background:#F9FAFB;border:1px solid #E5E7EB;border-radius:8px;padding:8px 12px}'
        '.cc-sl{font-size:.7rem;color:#6B7280;font-weight:500;margin-bottom:2px;white-space:nowrap}'
        '.cc-sv{font-size:1.2rem;font-weight:700;color:#111827;line-height:1.2}'
        '</style>'
        '<div class="cc-sg" style="grid-template-columns:repeat(6,1fr)">'
        f'<div class="cc-sc"><div class="cc-sl">Total ideas</div>'
        f'<div class="cc-sv">{total}</div></div>'
        f'<div class="cc-sc"><div class="cc-sl">Active</div>'
        f'<div class="cc-sv">{active}</div></div>'
        f'<div class="cc-sc"><div class="cc-sl">Done</div>'
        f'<div class="cc-sv">{concluidas}</div></div>'
        f'<div class="cc-sc"><div class="cc-sl">Open to-dos</div>'
        f'<div class="cc-sv">{todos_pending}</div></div>'
        f'<div class="cc-sc"><div class="cc-sl">Completed to-dos</div>'
        f'<div class="cc-sv">{todos_done}</div></div>'
        f'<div class="cc-sc"><div class="cc-sl">Open bugs</div>'
        f'<div class="cc-sv" style="color:{"#EF4444" if bugs_open else "#111827"}">{bugs_open}</div></div>'
        '</div>'
    )
    st.markdown(_bk_html, unsafe_allow_html=True)

    st.divider()

    # ── Deadline Calendar ──────────────────────────────────────────────────────
    import calendar as _cal_mod

    if "cal_year"  not in st.session_state: st.session_state.cal_year  = _date.today().year
    if "cal_month" not in st.session_state: st.session_state.cal_month = _date.today().month

    _cal_today = _date.today()
    _cy = st.session_state.cal_year
    _cm = st.session_state.cal_month

    st.subheader("Deadline Calendar")

    # Controls: nav + mode toggle
    _cc1, _cc2, _cc3, _cc4, _cc5 = st.columns([1, 2, 1, 1, 5])
    _MONTHS_EN = ["Jan","Feb","Mar","Apr","May","Jun",
                  "Jul","Aug","Sep","Oct","Nov","Dec"]
    with _cc1:
        if st.button("◀", key="cal_prev", use_container_width=True):
            if _cm == 1: st.session_state.cal_month = 12; st.session_state.cal_year -= 1
            else:        st.session_state.cal_month -= 1
            st.rerun()
    with _cc2:
        st.markdown(
            f"<p style='text-align:center;font-weight:600;padding:.35rem 0;margin:0'>"
            f"{_MONTHS_EN[_cm-1]} {_cy}</p>",
            unsafe_allow_html=True,
        )
    with _cc3:
        if st.button("▶", key="cal_next", use_container_width=True):
            if _cm == 12: st.session_state.cal_month = 1; st.session_state.cal_year += 1
            else:         st.session_state.cal_month += 1
            st.rerun()
    with _cc5:
        _cal_mode_sel = st.radio(
            "View",
            ["Backlog items", "To-dos"],
            horizontal=True,
            key="cal_mode_radio",
            label_visibility="collapsed",
        )
    _cal_mode = "ideas" if _cal_mode_sel == "Backlog items" else "todos"

    # Build deadline map for selected mode
    _CLOSED_CAL = {"concluído", "descartado", "análise - rejeitado"}
    _PRIO_ICON  = {"alta": "⭐", "média": "·", "baixa": "·"}
    _cal_map: dict = {}

    if _cal_mode == "ideas":
        for _ci in ideas_all:
            if _ci.due_date and _ci.status not in _CLOSED_CAL:
                _cal_map.setdefault(_ci.due_date, []).append(_ci)
    else:
        for _ci in ideas_all:
            for _ct in _ci.todos:
                if not _ct.get("done") and _ct.get("due_date"):
                    try:
                        _ctd = _date.fromisoformat(_ct["due_date"])
                        _cal_map.setdefault(_ctd, []).append({"idea": _ci, "todo": _ct})
                    except (ValueError, TypeError):
                        pass

    # Chip urgency class
    def _chip_cls(d):
        if d < _cal_today:             return "cal-overdue"
        if d == _cal_today:            return "cal-today"
        if (d - _cal_today).days <= 7: return "cal-soon"
        return "cal-future"

    # Calendar grid HTML
    _DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    _weeks = _cal_mod.Calendar(firstweekday=0).monthdatescalendar(_cy, _cm)
    _month_items = {d: v for d, v in _cal_map.items() if d.month == _cm and d.year == _cy}

    # Calendar CSS — dark-mode aware (generated in Python, not overridden by cascade)
    if _dark_mode:
        _c_border    = "#1F2937"
        _c_td_bg     = "#0E1117"
        _c_out_bg    = "#060810"
        _c_out_dnum  = "#1E293B"   # very dim — barely visible on dark bg
        _c_in_dnum   = "#64748B"   # moderately visible — clearly different
        _c_th_border = "#2D3748"
        _c_th_color  = "#475569"
        _c_fut_bg    = "#1A1D2E";  _c_fut_bc = "#2D3748"; _c_fut_clr = "#64748B"
        _c_more_clr  = "#475569"
    else:
        _c_border    = "#F3F4F6"
        _c_td_bg     = "transparent"
        _c_out_bg    = "#F1F5F9"
        _c_out_dnum  = "#D1D5DB"   # very dim — barely visible on light bg
        _c_in_dnum   = "#9CA3AF"   # moderately visible
        _c_th_border = "#E5E7EB"
        _c_th_color  = "#9CA3AF"
        _c_fut_bg    = "#F9FAFB";  _c_fut_bc = "#E5E7EB"; _c_fut_clr = "#6B7280"
        _c_more_clr  = "#9CA3AF"

    _cal_css = (
        "<style>"
        ".cal-wrap{overflow-x:auto;margin-top:.5rem}"
        ".cal-tbl{width:100%;border-collapse:collapse;table-layout:fixed}"
        f".cal-th{{font-family:'DM Mono',monospace;font-size:.65rem;font-weight:500;"
        f"letter-spacing:.08em;text-transform:uppercase;color:{_c_th_color};"
        f"text-align:center;padding:6px 2px;border-bottom:1px solid {_c_th_border}}}"
        f".cal-td{{vertical-align:top;border:1px solid {_c_border};background:{_c_td_bg};padding:4px;min-height:72px;width:14.28%}}"
        f".cal-td-out{{background:{_c_out_bg}}}"
        f".cal-td-out .cal-dnum{{color:{_c_out_dnum}}}"
        f".cal-td:not(.cal-td-out) .cal-dnum{{color:{_c_in_dnum}}}"
        ".cal-td-today{background:rgba(2,183,147,.04)!important;border-color:#02B793}"
        f".cal-dnum{{font-size:.7rem;color:{_c_in_dnum};margin-bottom:3px;display:block}}"
        ".cal-dnum-cur{font-size:.7rem;color:#02B793;font-weight:700;margin-bottom:3px;display:block}"
        ".cal-chip{display:block;font-size:.65rem;border-radius:3px;padding:2px 5px;"
        "margin-bottom:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;"
        "border-left:2px solid;line-height:1.4}"
        ".cal-overdue{background:#FEE2E2;border-color:#EF4444;color:#EF4444}"
        ".cal-today{background:#FEF3C7;border-color:#F59E0B;color:#D97706}"
        ".cal-soon{background:rgba(2,183,147,.08);border-color:#02B793;color:#007167}"
        f".cal-future{{background:{_c_fut_bg};border-color:{_c_fut_bc};color:{_c_fut_clr}}}"
        f".cal-more{{font-size:.6rem;color:{_c_more_clr};display:block;padding-left:5px}}"
        "</style>"
    )
    _th_row = (
        "<thead><tr>"
        + "".join(f'<th class="cal-th">{d}</th>' for d in _DOW)
        + "</tr></thead>"
    )
    _body_rows = []
    for _week in _weeks:
        _cells = []
        for _day in _week:
            _is_cur   = (_day.month == _cm)
            _is_today = (_day == _cal_today)
            _td_cls   = ("cal-td"
                         + (" cal-td-out"   if not _is_cur  else "")
                         + (" cal-td-today" if _is_today     else ""))
            _dn_cls   = "cal-dnum-cur" if _is_today else "cal-dnum"
            _cell     = [f'<td class="{_td_cls}"><span class="{_dn_cls}">{_day.day}</span>']
            if _is_cur:
                _day_items = _cal_map.get(_day, [])
                _cc_cls    = _chip_cls(_day)
                for _it in _day_items[:3]:
                    if _cal_mode == "ideas":
                        _icon = _PRIO_ICON.get(_it.priority, "·")
                        _lbl  = (f"{_icon} {_it.id} · "
                                 f"{_it.title[:20]}{'…' if len(_it.title) > 20 else ''}")
                    else:
                        _ttxt = _it["todo"]["text"]
                        _lbl  = (f"{_ttxt[:22]}{'…' if len(_ttxt) > 22 else ''}"
                                 f" · {_it['idea'].id}")
                    _safe = (_lbl.replace("&","&amp;")
                                 .replace("<","&lt;")
                                 .replace(">","&gt;"))
                    _cell.append(
                        f'<span class="cal-chip {_cc_cls}" title="{_safe}">{_safe}</span>'
                    )
                if len(_day_items) > 3:
                    _cell.append(
                        f'<span class="cal-more">+{len(_day_items) - 3} more</span>'
                    )
            _cell.append("</td>")
            _cells.append("".join(_cell))
        _body_rows.append("<tr>" + "".join(_cells) + "</tr>")

    if not _month_items:
        st.caption(f"No deadlines scheduled for {_MONTHS_EN[_cm-1]} {_cy}.")
    else:
        st.markdown(
            _cal_css
            + '<div class="cal-wrap"><table class="cal-tbl">'
            + _th_row + "<tbody>" + "".join(_body_rows) + "</tbody>"
            + "</table></div>",
            unsafe_allow_html=True,
        )

    st.divider()

    # ── Dialog defined outside expander to avoid re-registration issues ───────
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
            log_dir = _Path(_VAULT_ROOT) / "Log"
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

    with st.expander("Detailed analysis · Report", expanded=False):
        # ── To-dos com prazo hoje ou essa semana ─────────────────────────────
        _today_d = _date.today()
        _week_end = _today_d + timedelta(days=7)
        _due_soon: list[tuple] = []
        for _t in todos_all:
            if _t["done"]:
                continue
            _td = _t.get("due_date")
            if _td:
                try:
                    _d = _date.fromisoformat(str(_td)) if not isinstance(_td, _date) else _td
                    if _d <= _week_end:
                        _due_soon.append((_d, _t))
                except Exception:
                    pass
        _due_soon.sort(key=lambda x: x[0])

        col_left, col_right, col_due = st.columns(3)

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
                badge = PRIORITY_NUM.get(p, "")
                pct = count / total if total else 0
                st.markdown(f"{badge} **{PRIORITY_LABEL.get(p, p)}** — {count}", unsafe_allow_html=True)
                st.progress(pct)

        with col_due:
            st.subheader("Due this week")
            if not _due_soon:
                st.caption("No to-dos due today or this week.")
            else:
                for _d, _t in _due_soon:
                    _is_overdue = _d < _today_d
                    _date_str = "Hoje" if _d == _today_d else _d.strftime("%d/%m")
                    _clr = "#EF4444" if _is_overdue else ("#F59E0B" if _d == _today_d else "#6B7280")
                    _bug_b = (
                        ' <span style="background:#FEE2E2;color:#B91C1C;font-size:8px;'
                        'font-weight:700;padding:1px 4px;border-radius:3px">BUG</span>'
                        if _t.get("is_bug") else ""
                    )
                    st.markdown(
                        f'<div style="padding:5px 0;border-bottom:1px solid rgba(0,0,0,0.06)">'
                        f'<span style="font-size:0.7rem;font-weight:600;color:{_clr}">{_date_str}</span>'
                        f'&nbsp;<span style="font-size:0.81rem;color:#374151">{_t["text"][:48]}</span>{_bug_b}'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

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
                _h0, _h1, _h2 = st.columns([1, 5, 3])
                _h0.caption("Score")
                _h1.caption("Idea")
                _h2.caption("Impact · Effort")
                for idea in ranked[:8]:
                    s = _score(idea)
                    _clean_title = idea.title.replace("**", "").strip()
                    _c0, _c1, _c2 = st.columns([1, 5, 3])
                    _c0.markdown(f"**{s}**")
                    _c1.markdown(f"`{idea.id}` {_clean_title[:38]}")
                    _c2.caption(
                        f"{IMPACT_LABEL.get(idea.impacto, idea.impacto)} · "
                        f"{EFFORT_LABEL.get(idea.esforco, idea.esforco)}"
                    )

        st.divider()
        st.subheader("Period report")
        if st.button("📋 Generate period report"):
            _report_dialog()

# PAGE 5 — WEEKLY BRIEF
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Weekly Brief":
    from datetime import timedelta
    import re as _wre

    _TEAM_DIR  = VAULT_ROOT / "Team"
    _LOG_DIR   = VAULT_ROOT / "Log"
    _TEAM = [
        {"name": "Ana Leite",      "folder": "Ana-Leite"},
        {"name": "Daniel Lima",    "folder": "Daniel-Lima"},
        {"name": "Lucas Shizuno",  "folder": "Lucas-Shizuno"},
        {"name": "Pedro Hennig",   "folder": "Pedro-Hennig"},
        {"name": "Pedro Klein",    "folder": "Pedro-Klein"},
    ]

    st.markdown('<h1 style="margin-bottom:0.4rem">Weekly Brief</h1>', unsafe_allow_html=True)
    st.caption("Meeting prep panel for Alberto Reuters and Stefan Lautenschlager.")

    # ── Dark-mode aware inline table styles ───────────────────────────────────
    if _dark_mode:
        _WB_TH  = ("padding:7px 12px;text-align:left;font-weight:500;font-size:12px;"
                   "color:#64748B;border-bottom:1px solid #2D3748;white-space:nowrap")
        _WB_TD  = ("padding:7px 12px;font-size:13px;color:#CBD5E0;"
                   "border-bottom:1px solid rgba(45,55,72,0.5);vertical-align:top")
        _WB_ID  = _WB_TD + ";white-space:nowrap;font-family:monospace;font-size:12px;color:#02B793"
    else:
        _WB_TH  = ("padding:7px 12px;text-align:left;font-weight:500;font-size:12px;"
                   "color:rgba(76,77,88,0.55);border-bottom:1px solid rgba(76,77,88,0.18);white-space:nowrap")
        _WB_TD  = "padding:7px 12px;font-size:13px;border-bottom:1px solid rgba(76,77,88,0.07);vertical-align:top"
        _WB_ID  = _WB_TD + ";white-space:nowrap;font-family:monospace;font-size:12px;color:#02B793"

    # ── Controls ──────────────────────────────────────────────────────────────
    _ctrl1, _ctrl2 = st.columns([1, 3])
    with _ctrl1:
        _period = st.slider("Period (days)", 3, 30, 7, key="wb_period")
    _start = date.today() - timedelta(days=_period)
    with _ctrl2:
        st.markdown("<br>", unsafe_allow_html=True)
        _c1, _c2, _c3, _c4 = st.columns(4)
        _show_devs  = _c1.checkbox("🚀 Devs",   value=True, key="wb_devs")
        _show_wip   = _c2.checkbox("🔄 WIP",    value=True, key="wb_wip")
        _show_team  = _c3.checkbox("👥 Team",   value=True, key="wb_team")
        _show_calls = _c4.checkbox("📞 Calls",  value=True, key="wb_calls")

    st.caption(f"Period: **{_start.strftime('%d/%m/%Y')}** → **{date.today().strftime('%d/%m/%Y')}**")
    st.divider()

    _store = get_store()
    _ideas = _store.load_all()
    _today = date.today()
    _export = [f"# Weekly Brief — {_today.strftime('%d/%m/%Y')}",
               f"Period: {_start.strftime('%d/%m/%Y')} → {_today.strftime('%d/%m/%Y')}", ""]

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _wb_parse_1on1(path: Path):
        if not path.exists():
            return None
        text = path.read_text(encoding="utf-8", errors="replace")
        parts = _wre.split(r"^## (\d{4}-\d{2}-\d{2})\b", text, flags=_wre.MULTILINE)
        if len(parts) < 3:
            return None
        session_date, content = parts[1], parts[2]
        topics, actions, in_topics, in_actions = [], [], False, False
        for line in content.splitlines():
            s = line.strip()
            if _wre.match(r"\*\*(T[oó]picos?|Topics?)\*\*", s):
                in_topics, in_actions = True, False; continue
            if _wre.match(r"\*\*(Action [Ii]tems?|Ac[oõ]es?)\*\*", s):
                in_topics, in_actions = False, True; continue
            if s.startswith("**") or s.startswith("---"):
                in_topics = in_actions = False
            if in_topics and s.startswith("- "):
                topics.append(s[2:])
            if in_actions and _wre.match(r"- \[[ x]\]", s):
                actions.append({"text": s[6:].strip(), "done": s[3] == "x"})
        return {"date": session_date, "topics": topics[:6], "actions": actions}

    def _wb_read_logs(start: date, end: date):
        entries, cur = [], start
        while cur <= end:
            lp = _LOG_DIR / f"diario-{cur.isoformat()}.md"
            if lp.exists():
                for line in lp.read_text(encoding="utf-8", errors="replace").splitlines():
                    m = _wre.match(r"^- (\d{2}:\d{2}) `([\w-]+)` \[(.+?)\] (.+?)(?:\s—\s(.+))?$", line)
                    if m:
                        entries.append({"date": cur, "time": m.group(1), "action": m.group(2),
                                        "idea_id": m.group(3), "title": m.group(4).strip(),
                                        "detail": (m.group(5) or "").strip()})
            cur += timedelta(days=1)
        return entries

    # ── Section 1: Desenvolvimentos ───────────────────────────────────────────
    if _show_devs:
        st.subheader("Developments")
        _logs = _wb_read_logs(_start, _today)
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
                _tipo = "Created" if e["action"] == "CRIADA" else "Status"
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

    # ── Section 2: Em andamento ───────────────────────────────────────────────
    if _show_wip:
        st.subheader("In progress")
        _active = [i for i in _ideas if i.status in ("em desenvolvimento", "em validação", "aguardando desenvolvimento")]
        _wip_todos = [(i, t) for i in _ideas for t in i.todos if t.get("in_progress") and not t.get("done")]
        _upcoming  = [i for i in _ideas if i.due_date and _today <= i.due_date <= _today + timedelta(days=7)
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
                    _dl = (i.due_date - _today).days
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

    # ── Section 3: Status do time ─────────────────────────────────────────────
    if _show_team:
        st.subheader("Team status")
        _export.append("## 👥 Team")
        for _m in _TEAM:
            _folder = _TEAM_DIR / _m["folder"]
            with st.expander(f"**{_m['name']}**", expanded=True):
                _role = ""
                _ov = _folder / "Overview.md"
                if _ov.exists():
                    _rm = _wre.search(r"\*\*Role:\*\*\s*(.+)", _ov.read_text(encoding="utf-8", errors="replace"))
                    if _rm: _role = _rm.group(1).strip()

                _latest = _wb_parse_1on1(_folder / "1on1.md")
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
            _call_dir = _TEAM_DIR / _m["folder"] / "1on1"
            if _call_dir.exists():
                for _cf in sorted(_call_dir.glob("*.md")):
                    if _cf.name.startswith("_"): continue
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
                    _body = _wre.sub(r"^---.*?---\n", "", _c["path"].read_text(encoding="utf-8", errors="replace"), flags=_wre.DOTALL).strip()
                    st.markdown(_body[:2500] + ("…" if len(_body) > 2500 else ""))
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
        st.code(_export_md, language="markdown")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 4 — TUTORIAL
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Tutorial":
    st.markdown('<h1 style="margin-bottom:0.4rem">Installation Tutorial</h1>', unsafe_allow_html=True)
    st.caption("Complete guide to install and configure Personal Toolkit · Techco.lab on a new machine.")

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

The app has a **top navigation bar** with the logo on the left and page links across the top. Click any link to navigate. The 🔄 icon on the far right refreshes all data from disk.

| Page | Purpose |
|---|---|
| Dashboard | Home — metrics overview, status/priority breakdown, to-dos due this week |
| Backlog | Create, edit and view ideas (list or kanban view) |
| To-Do List | All action items consolidated across all ideas, sortable and filterable |
| Claude Pro | HTML adoption report + Token Coach calculator |
| Weekly Brief | Preparation panel for meetings with leadership |
| English Coach | Progress tracker for AI-evaluated English practice sessions |
| 📖 (Tutorial) | This page |
| 📚 (Documentation) | Technical architecture and planned phases |

**Status flow:**
```
backlog → under review → approved → waiting → in development → in validation → done ✅
                       └─► rejected / discarded ⛔
```

### Priority badges

In the Backlog list view and To-Do List, priority is shown as a numbered circle:

| Badge | Priority |
|---|---|
| ● 3 (dark) | Alta / High |
| ● 2 (medium) | Média / Medium |
| ● 1 (light) | Baixa / Low |

### To-do states

Each to-do supports three states, toggled via the selectbox (To-Do List) or the state dropdown (Backlog card):

| Symbol | Meaning |
|---|---|
| ⬜ | Open — not started |
| 🔄 | In progress — started but not done |
| ✅ | Done — completed (records `completed_at` date) |

### Agent authorisation per to-do

The 🤖 checkbox on each to-do marks it as pre-approved for the daily agent.
Pre-approved to-dos appear with `[x]` already checked in the agent report — no manual approval needed.
You can set this during to-do creation or by editing the idea card later.

### Weekly Brief

Open **Weekly Brief** before any meeting with Alberto Reuters or Stefan Lautenschlager.

- Use the period slider (default 7 days) to set the reporting window
- Toggle sections on/off with the checkboxes
- Download the summary as `.md` for pasting into emails or Obsidian notes
- The **Calls** section auto-populates from session notes generated by the call recorder
- **Call com Gestor** (Win+Space → option 3) records calls with Alberto Reuters or Stefan Lautenschlager; notes are saved to `Stakeholders/{Name}/1on1/`

---

## Raycast shortcuts

All daily interactions are available directly via keyboard — no terminal needed.
Scripts live in `C:\\Users\\Kelvin.okuda\\Scripts\\call-recorder\\` and are registered in Raycast → Settings → Script Commands.

| Shortcut | Command | What it does |
|---|---|---|
| ⊞ Win + Space | **Call Recorder** | Opens menu: 1on1 com time / English Coach / Call com Gestor |
| ⊞ Win + C | **Encerrar Sessão** | Runs tests, commits and pushes both repos |
| *(assign)* | **Rodar Agente** | Runs Phase 1 — generates today's backlog report |
| *(assign)* | **Executar Agente** | Copies Phase 2 command to clipboard + opens Claude Code |

> **To assign a hotkey:** Raycast → Settings → Script Commands → click "Record Hotkey" next to the command.
> **To add or change scripts:** edit the `.ps1` files in the `call-recorder` folder — Raycast picks them up automatically (click "Reload Script Commands" if needed).

### Executar Agente — how it works

When you trigger **Executar Agente**:
1. The exact command is copied to your clipboard automatically
2. A terminal opens showing the report path
3. Claude Code launches in the project directory
4. Press **Ctrl+V** then **Enter** — done

No need to remember or type anything.

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

**Easiest way — Raycast:**
Trigger **Executar Agente** (assign a hotkey in Raycast → Script Commands).
The command is copied to clipboard automatically — just paste in Claude Code and press Enter.

**Manual way:**
1. Double-click **`execute_agent.bat`** in the project folder
2. A terminal opens showing today's report path — press any key
3. Claude Code opens in the project directory
4. Type (or paste) exactly:

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
| App shows stale data | Click **🔄** in the top navigation bar (far right) |
| Port 8501 in use | `streamlit run app.py --server.port 8502` |
| "python not recognized" | Reinstall Python with "Add to PATH" checked |
| pip install error | Activate `.venv` first: `.venv\\Scripts\\activate` |
| Agent report not found | Run `run_agent.bat` manually to generate it |
| `TECHCOLAB_VAULT` error in app | Restart the app — the env var is set but needs a new process |

---

## Claude Pro Report

The **Claude Pro Report** (**Claude Pro** page) is a live HTML report that tracks Claude Pro usage and adoption metrics for the NBS D&A team. The page also includes the **Token Coach** calculator.

It is stored as an HTML file inside the project repository (`reports/claude-pro-report.html`) and published automatically via GitHub Pages.

### What gets updated automatically

Every morning when the daily agent runs, it updates three values in the HTML file:

| Field | Example |
|---|---|
| "Atualizado em" (header meta) | 19/05/2026 |
| "Dias desde adoção" (stat counter) | 47 |
| Footer date | 19/05/2026 |

After updating, the agent commits the file to the repository and pushes it — GitHub Pages then serves the new version within ~1 minute.

To update manually outside the agent schedule, use the **Update now** button on the **Claude Pro** page.
""")



# ══════════════════════════════════════════════════════════════════════════════
# PAGE 5 — DOCUMENTAÇÃO
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Documentation":
    st.markdown('<h1 style="margin-bottom:0.4rem">Documentation & Context</h1>', unsafe_allow_html=True)
    st.info("**Repository:** [github.com/keok-netzsch/techcolab-backlog](https://github.com/keok-netzsch/techcolab-backlog)", icon="📦")

    st.markdown("## Overview")
    st.markdown("""
**Personal Toolkit · Techco.lab** is a personal productivity toolkit integrated with Obsidian.
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
    st.markdown("## Design System")
    st.markdown(
        "The visual identity of this app is defined in two files — reusable in any project:"
    )
    col_ds1, col_ds2 = st.columns(2)
    with col_ds1:
        st.markdown("""
**Full spec** (colors, typography, components, rules)
`C:\\Users\\Kelvin.okuda\\techcolab-backlog\\DESIGN_SYSTEM.md`
""")
        st.markdown("""
**Quick reference** (hex values, Canva/PPT/Figma, snippets)
`Resources/techcolab-brand.md` no vault
""")
    with col_ds2:
        st.markdown("""
**CSS pronto para importar** em HTML/relatórios
`C:\\Users\\Kelvin.okuda\\Scripts\\techcolab-brand.css`
""")
        st.code(
            '@import url("https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap");\n'
            ":root {\n"
            "  --tc-accent:       #02B793;\n"
            "  --tc-accent-hover: #007167;\n"
            "  --tc-accent-light: #0AD4A8;\n"
            "  --tc-text:         #111827;\n"
            "  --tc-font:         'Inter', sans-serif;\n"
            "  --tc-radius:       8px;\n"
            "}",
            language="css",
        )

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


elif page == "Claude Pro":
    import json as _cpjson
    from config import CLAUDE_PRO_START_DATE

    _CP_TIMELINE_JSON = Path(__file__).parent / "reports" / "claude-pro-timeline.json"

    # ── Static data — Active initiatives ─────────────────────────────────────
    _CP_ACTIVE = [
        {
            "number": "07",
            "title": "Claude Pro Report — Daily Auto-Update",
            "category": "Automation · Report",
            "boss": "This very report — generated and updated by Claude automatically every morning. Goal: make Claude Pro usage and value visible to stakeholders.",
            "advance": "Integrated into TechColab Backlog App, updated at 8am by the daily agent, with Techco.lab identity.",
            "body": "Live report integrated into TechColab Backlog App.",
            "bullets": [
                "Served locally — no dependency on an external URL",
                "Daily agent updates statistics at 8am",
                "Versioned in the techcolab-backlog repository",
            ],
        },
        {
            "number": "08",
            "title": "Call Recorder — Transcription & Obsidian Vault Integration",
            "category": "Automation · 1:1s",
            "boss": "Automatic recording and transcription system for meetings and 1:1s, generating structured notes. Goal: eliminate manual effort of recording meetings.",
            "advance": "Pipeline running locally (no data sent to the cloud). Next: full vault integration.",
            "body": "Recording/transcription pipeline integrated with the vault.",
            "bullets": [
                "Stack: Python 3.13 + faster-whisper (CPU, int8)",
                "record.py + call-recorder.ps1 — complete orchestrator",
                "Next step: full Obsidian vault integration",
            ],
        },
        {
            "number": "09",
            "title": "Personal Toolkit · Techco.lab — Backlog Management App",
            "category": "Product · Automation",
            "boss": "Local productivity app built with Streamlit, integrated with Obsidian vault and daily agent. Centralises idea backlog, to-do management, weekly team brief and bug tracking.",
            "advance": "App in production with 24+ backlog items, bug tracking per to-do, kanban, Claude agent integration and Claude Pro report served locally.",
            "body": "Personal productivity toolkit running 100% offline.",
            "bullets": [
                "Streamlit + Obsidian vault + daily agent at 8am",
                "Backlog with kanban, filters, bug tracking and per-idea to-dos",
                "Weekly team brief with OKR and 1:1 tables",
                "Serves the Claude Pro Report locally — no external dependency",
            ],
        },
    ]

    # ── Static data — Completed initiatives ──────────────────────────────────
    _CP_COMPLETED = [
        {
            "number": "01",
            "title": "Claude Pro Setup & Onboarding",
            "category": "Setup",
            "boss": "Initial Claude Pro environment setup for corporate use. Prerequisite for all other initiatives.",
            "advance": "Environment ready and operational from day one.",
            "body": "Installation, requirements assessment and Microsoft 365 integration mapping.",
            "bullets": [
                "Installation ticket (Claude Desktop App via MSIX)",
                "Features mapped: Computer Use, Projects, MCP",
                "Integration assessment with Power Automate and Teams",
            ],
        },
        {
            "number": "02",
            "title": "Obsidian Vault — Second Brain for D&A Management",
            "category": "Management · AI",
            "boss": "Digital knowledge base integrated with Claude. Replaces scattered notes with a centralised system automatically accessible by Claude.",
            "advance": "All 5 direct reports have OKRs, plans and 1:1 history recorded and accessible to Claude.",
            "body": "Obsidian Vault integrated with Claude Code as a persistent knowledge base.",
            "bullets": [
                "PARA structure: Inbox, Projects, Areas, Resources, Archive, AI, Templates, Team",
                "Individual profiles for 5 direct reports with OKR, 1:1, PDI and Overview",
                "obsidian-second-brain skill with 25 slash commands installed",
            ],
        },
        {
            "number": "03",
            "title": "D&A Team OKR Assessment & Consolidation",
            "category": "Governance · OKR",
            "boss": "Using Claude to review OKRs, find inconsistencies and generate ready-to-report texts — without manual rework.",
            "advance": "Standardised documentation for all 4 active direct reports, ready for meetings.",
            "body": "Analysis, correction and consolidation of the OKR matrix for 4 active members.",
            "bullets": [
                "Critical KR status review with inconsistency identification",
                "Clean report texts generated for stakeholder reporting",
                "Structured records in vault (OKR.md per direct report)",
            ],
        },
        {
            "number": "04",
            "title": "Techco.lab Deck Skill — Branded Presentations",
            "category": "Productivity · Deck",
            "boss": "Tool that allows Claude to create presentations in the Techco.lab/NETZSCH standard automatically — no manual formatting.",
            "advance": "Claude generates slides and .pptx with the correct visual identity from natural language.",
            "body": "Proprietary deck generation skill for the Techco.lab/NETZSCH standard.",
            "bullets": [
                "Output: web deck (Vite + React + Tailwind) or .pptx",
                "Classification levels: Internal Use Only, Confidential, Strictly Confidential",
            ],
        },
        {
            "number": "05",
            "title": "Knowledge Base — NETZSCH Corporate Structure",
            "category": "Knowledge Base",
            "boss": "Complete NETZSCH group mapping available as permanent context — Claude knows who is who without being reminded each session.",
            "advance": "50+ entities from all BUs documented and accessible.",
            "body": "Extraction and organisation of corporate structure in Obsidian vault.",
            "bullets": [
                "All BUs: A&T, G&D, P&S, Holding",
                "50+ entities with code, full name and BU",
                "Resources/NETZSCH/General.md with change log",
            ],
        },
        {
            "number": "06",
            "title": "One-Point Lesson — Power Platform Deployment",
            "category": "OPL · Power Platform",
            "boss": "Documentation of the process for publishing Power Platform solutions from test to production — previously relied on one person's tacit knowledge.",
            "advance": "9-step guide ready. Any team member can execute without asking for help.",
            "body": "Structured documentation for Power Platform deployment (Test → Prod).",
            "bullets": [
                "9 steps with video reference timestamps",
                "Key notes: unmanaged solution, Upgrade option, connections for service users",
            ],
        },
    ]

    # ── Static data — Tools ───────────────────────────────────────────────────
    _CP_TOOLS = [
        ("Claude Desktop App",               "claude.ai + Computer Use",         "Main interface. Windows-MCP, document generation, vault management.",                              "Active"),
        ("Claude Code",                       "CLI agentic coding",               "Obsidian vault operations, automations, slash commands (/obsidian-*).",                           "Active"),
        ("Obsidian + obsidian-second-brain",  "Local vault + open-source skill",  "Persistent knowledge base: OKRs, 1:1s, PDIs, session logs.",                                      "Active"),
        ("Techco.lab Deck Skill",             "Proprietary NETZSCH skill",        "Web and .pptx presentation generation with Techco.lab visual identity.",                          "Configured"),
        ("TechColab Backlog App",             "Streamlit + Obsidian + Ollama",    "Backlog management with daily agent, dashboard and this report integrated.",                      "Active"),
        ("Windows-MCP",                       "System control via Claude",        "Read/write local files, PowerShell execution via Claude Desktop.",                                "Active"),
    ]

    # ── Computed stats ────────────────────────────────────────────────────────
    _cp_start = date.fromisoformat(CLAUDE_PRO_START_DATE)
    _cp_days  = (date.today() - _cp_start).days

    # ── Load timeline ─────────────────────────────────────────────────────────
    _cp_timeline: list = []
    if _CP_TIMELINE_JSON.exists():
        try:
            _cp_timeline = _cpjson.loads(_CP_TIMELINE_JSON.read_text(encoding="utf-8"))
        except (_cpjson.JSONDecodeError, ValueError):
            st.warning("⚠ Timeline file is temporarily unavailable (write in progress). Reload to retry.")

    def _fmt_cp_date(iso: str) -> str:
        _m = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
        _dt = date.fromisoformat(iso)
        return f"{_dt.day} {_m[_dt.month-1]} {_dt.year}"

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
    .cp-stat-strip{display:grid;grid-template-columns:repeat(4,1fr);gap:2px;margin-bottom:1.5rem}
    .cp-stat-box{background:white;border:1px solid rgba(76,77,88,.12);padding:20px 24px;border-radius:4px}
    .cp-stat-num{font-size:36px;font-weight:700;letter-spacing:-.03em;line-height:1;margin-bottom:4px;
                 background:linear-gradient(135deg,#007167,#8AC6BD);
                 -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
    .cp-stat-lbl{font-size:13px;color:rgba(76,77,88,.55)}
    .cp-exec{background:rgba(2,183,147,.05);border:1px solid rgba(2,183,147,.35);
             border-left:4px solid #02B793;border-radius:6px;padding:24px 28px;margin-bottom:1.5rem}
    .cp-exec-lbl{font-family:'DM Mono',monospace;font-size:10px;font-weight:500;letter-spacing:.14em;
                 text-transform:uppercase;color:#02B793;margin-bottom:10px}
    .cp-exec-lead{font-size:15px;color:#2A2A2A;margin-bottom:14px;line-height:1.6}
    .cp-exec-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px 28px;list-style:none;padding:0;margin:0}
    .cp-exec-grid li{font-size:14px;color:#4A4A4A;position:relative;padding-left:14px}
    .cp-exec-grid li::before{content:'';position:absolute;left:0;top:.3em;width:4px;height:1em;
                              background:#02B793;border-radius:2px}
    .cp-exec-grid li strong{color:#2A2A2A;font-weight:500}
    .cp-sect-lbl{font-family:'DM Mono',monospace;font-size:10px;font-weight:500;letter-spacing:.18em;
                 text-transform:uppercase;color:rgba(76,77,88,.55);margin:1.5rem 0 .4rem;
                 display:flex;align-items:center;gap:12px}
    .cp-sect-lbl::after{content:'';flex:1;height:1px;background:rgba(76,77,88,.12)}
    .cp-boss{background:rgba(2,183,147,.05);border-left:3px solid #02B793;
             border-radius:0 4px 4px 0;padding:10px 14px;margin-bottom:10px}
    .cp-boss-lbl{font-family:'DM Mono',monospace;font-size:9px;font-weight:500;letter-spacing:.14em;
                 text-transform:uppercase;color:#02B793;margin-bottom:4px}
    .cp-boss-p{font-size:13px;color:#2A2A2A;line-height:1.6;margin:0}
    .cp-boss-adv{margin-top:5px;font-size:12px;color:rgba(76,77,88,.55)}
    .cp-boss-adv strong{color:#007167;font-weight:500}
    .cp-body-ul{list-style:none;padding:0;margin:6px 0 0}
    .cp-body-ul li{position:relative;padding-left:14px;margin-bottom:3px;font-size:13px;color:rgba(76,77,88,.8)}
    .cp-body-ul li::before{content:'';position:absolute;left:0;top:.6em;width:4px;height:4px;
                            border-radius:50%;background:rgba(76,77,88,.25)}
    .cp-badge-prog{font-family:'DM Mono',monospace;font-size:10px;font-weight:500;letter-spacing:.08em;
                   text-transform:uppercase;padding:3px 9px;border-radius:999px;
                   background:#fdf0e0;color:#b5640a;display:inline-block;margin-right:4px}
    .cp-badge-done{font-family:'DM Mono',monospace;font-size:10px;font-weight:500;letter-spacing:.08em;
                   text-transform:uppercase;padding:3px 9px;border-radius:999px;
                   background:rgba(2,183,147,.09);color:#007167;display:inline-block;margin-right:4px}
    .cp-badge-cfg{font-family:'DM Mono',monospace;font-size:10px;font-weight:500;letter-spacing:.08em;
                  text-transform:uppercase;padding:3px 9px;border-radius:999px;
                  background:rgba(181,100,10,.09);color:#b5640a;display:inline-block;margin-right:4px}
    .cp-badge-cat{font-family:'DM Mono',monospace;font-size:10px;font-weight:500;letter-spacing:.08em;
                  text-transform:uppercase;padding:3px 9px;border-radius:999px;
                  background:rgba(76,77,88,.07);color:rgba(76,77,88,.55);display:inline-block}
    .cp-tl-wrap{position:relative;padding-left:28px;margin-top:.5rem}
    .cp-tl-wrap::before{content:'';position:absolute;left:0;top:8px;bottom:0;width:1px;
                         background:rgba(76,77,88,.12)}
    .cp-tl-item{position:relative;margin-bottom:22px}
    .cp-tl-item::before{content:'';position:absolute;left:-32px;top:6px;width:8px;height:8px;
                         border-radius:50%;background:#02B793;border:2px solid #F9FAFB;
                         box-shadow:0 0 0 1px #02B793}
    .cp-tl-latest::before{width:10px;height:10px;left:-33px;top:5px;
                           background:linear-gradient(135deg,#02B793,#0AD4A8);
                           box-shadow:0 0 0 1px #02B793,0 0 8px rgba(2,183,147,.4)}
    .cp-tl-date{font-family:'DM Mono',monospace;font-size:11px;color:rgba(76,77,88,.55);margin-bottom:3px}
    .cp-tl-title{font-weight:500;font-size:14px;color:#2A2A2A;margin-bottom:3px}
    .cp-tl-detail{font-size:13px;color:rgba(76,77,88,.55)}
    .cp-tl-badge{display:inline-block;font-family:'DM Mono',monospace;font-size:9px;font-weight:500;
                 letter-spacing:.1em;text-transform:uppercase;background:rgba(2,183,147,.09);
                 color:#02B793;padding:2px 7px;border-radius:999px;margin-left:6px;vertical-align:middle}
    .cp-tools-tbl{width:100%;border-collapse:collapse;font-size:14px;margin-top:.5rem}
    .cp-tools-tbl th{font-family:'DM Mono',monospace;font-size:10px;font-weight:500;letter-spacing:.12em;
                     text-transform:uppercase;color:rgba(76,77,88,.55);text-align:left;
                     padding:10px 14px;border-bottom:1px solid rgba(76,77,88,.12);background:white}
    .cp-tools-tbl td{padding:12px 14px;border-bottom:1px solid rgba(76,77,88,.12);
                     vertical-align:top;background:white}
    .cp-tools-tbl tr:last-child td{border-bottom:none}
    .cp-tool-name{font-weight:500;font-size:14px;color:#2A2A2A}
    .cp-tool-sub{font-size:12px;color:rgba(76,77,88,.55);margin-top:2px}
    .cp-footer{background:#4C4D58;padding:20px 32px;border-radius:6px;display:flex;
               justify-content:space-between;align-items:center;margin-top:2rem}
    .cp-footer-l{font-family:'DM Mono',monospace;font-size:11px;color:rgba(255,255,255,.45)}
    .cp-footer-r{font-size:12px;color:rgba(255,255,255,.35)}
    .cp-dot{color:#02B793}
    @media(max-width:768px){
      .cp-header{grid-template-columns:1fr}.cp-meta{text-align:left}
      .cp-stat-strip{grid-template-columns:repeat(2,1fr)}.cp-exec-grid{grid-template-columns:1fr}
    }
    </style>""", unsafe_allow_html=True)

    # ── Header ────────────────────────────────────────────────────────────────
    st.markdown(f"""<div class="cp-header">
      <div>
        <div class="cp-org">NBS D&amp;A &middot; Techco.lab &middot; Team Lead</div>
        <div class="cp-h1">Claude Pro — Initiatives<br>&amp; Developments</div>
      </div>
      <div class="cp-meta">
        <strong>Kelvin Okuda</strong><br>
        Team Lead · D&amp;A Projects &amp; Governance<br>
        Period: 11/05/2026 &rarr; present<br>
        Updated: {date.today().strftime('%d/%m/%Y')}
      </div>
    </div>""", unsafe_allow_html=True)

    # ── Overview ──────────────────────────────────────────────────────────────
    st.markdown('<div class="cp-sect-lbl">Overview</div>', unsafe_allow_html=True)
    _cp_total_init = len(_CP_ACTIVE) + len(_CP_COMPLETED)
    st.markdown(f"""<div class="cp-stat-strip">
      <div class="cp-stat-box"><div class="cp-stat-num">{_cp_total_init}</div><div class="cp-stat-lbl">Total initiatives</div></div>
      <div class="cp-stat-box"><div class="cp-stat-num">{len(_CP_COMPLETED)}</div><div class="cp-stat-lbl">Completed</div></div>
      <div class="cp-stat-box"><div class="cp-stat-num">{len(_cp_timeline)}</div><div class="cp-stat-lbl">Sessions logged</div></div>
      <div class="cp-stat-box"><div class="cp-stat-num">{_cp_days}</div><div class="cp-stat-lbl">Days since adoption</div></div>
    </div>
    <div class="cp-exec">
      <div class="cp-exec-lbl">For the manager — what is being done with Claude Pro</div>
      <p class="cp-exec-lead">Claude Pro is being used to increase productivity and quality of D&amp;A area management.
      In {_cp_days} days, {_cp_total_init} initiatives were configured covering documentation, governance, automations and development tools.</p>
      <ul class="cp-exec-grid">
        <li><strong>Team management:</strong> knowledge base with OKRs, plans and history for all 5 direct reports</li>
        <li><strong>Governance:</strong> OKRs reviewed and consolidated; corporate structure mapped</li>
        <li><strong>Productivity:</strong> presentations generated automatically in the visual standard</li>
        <li><strong>Documentation:</strong> technical processes documented as practical guides (OPLs)</li>
        <li><strong>Automation:</strong> automatic meeting transcription in progress</li>
        <li><strong>Visibility:</strong> this report — updated automatically every morning</li>
      </ul>
    </div>""", unsafe_allow_html=True)

    # ── Active initiatives ────────────────────────────────────────────────────
    st.markdown('<div class="cp-sect-lbl">Initiatives</div>', unsafe_allow_html=True)
    st.subheader("Projects & Developments")
    st.caption("Claude Pro applied to management, governance and D&A team development.")

    _cp_body_clr = "#94A3B8" if _dark_mode else "rgba(76,77,88,.7)"
    for _init in _CP_ACTIVE:
        _bl = "".join(f"<li>{b}</li>" for b in _init["bullets"])
        with st.expander(f"**{_init['number']}** · {_init['title']}", expanded=True):
            st.markdown(
                f'<span class="cp-badge-prog">In progress</span>'
                f'<span class="cp-badge-cat">{_init["category"]}</span>',
                unsafe_allow_html=True,
            )
            st.markdown(f"""<div class="cp-boss">
              <div class="cp-boss-lbl">In summary</div>
              <p class="cp-boss-p">{_init['boss']}</p>
              <p class="cp-boss-adv"><strong>Key advance:</strong> {_init['advance']}</p>
            </div>
            <p style="font-size:13.5px;color:{_cp_body_clr};margin:.4rem 0 .3rem">{_init['body']}</p>
            <ul class="cp-body-ul">{_bl}</ul>""", unsafe_allow_html=True)

    # ── Completed toggle ──────────────────────────────────────────────────────
    if "cp_show_completed" not in st.session_state:
        st.session_state["cp_show_completed"] = False
    _ct_lbl = ("▴ Completed (6) — hide" if st.session_state["cp_show_completed"]
               else "▾ Completed (6) — show")
    if st.button(_ct_lbl, key="cp_toggle_completed", use_container_width=True):
        st.session_state["cp_show_completed"] = not st.session_state["cp_show_completed"]
        st.rerun()

    if st.session_state["cp_show_completed"]:
        for _init in _CP_COMPLETED:
            _bl = "".join(f"<li>{b}</li>" for b in _init["bullets"])
            with st.expander(f"**{_init['number']}** · {_init['title']}", expanded=False):
                st.markdown(
                    f'<span class="cp-badge-done">Done</span>'
                    f'<span class="cp-badge-cat">{_init["category"]}</span>',
                    unsafe_allow_html=True,
                )
                st.markdown(f"""<div class="cp-boss">
                  <div class="cp-boss-lbl">In summary</div>
                  <p class="cp-boss-p">{_init['boss']}</p>
                  <p class="cp-boss-adv"><strong>Key advance:</strong> {_init['advance']}</p>
                </div>
                <p style="font-size:13.5px;color:{_cp_body_clr};margin:.4rem 0 .3rem">{_init['body']}</p>
                <ul class="cp-body-ul">{_bl}</ul>""", unsafe_allow_html=True)

    # ── Timeline ──────────────────────────────────────────────────────────────
    st.markdown('<div class="cp-sect-lbl">Timeline</div>', unsafe_allow_html=True)
    st.subheader("Adoption Chronology")
    st.caption("Sequence of configurations and milestones since Pro plan access — most recent first.")

    if _cp_timeline:
        _today_iso = date.today().isoformat()
        _tl_html = ""
        for _ti, _entry in enumerate(_cp_timeline):
            _is_today   = (_entry["date"] == _today_iso)
            _cls        = "cp-tl-item cp-tl-latest" if _ti == 0 else "cp-tl-item"
            _badge      = ' <span class="cp-tl-badge">today</span>' if _is_today else ""
            _disp_date  = _entry.get("display_date") or _fmt_cp_date(_entry["date"])
            _detail_htm = (f'<div class="cp-tl-detail">{_entry["detail"]}</div>'
                           if _entry.get("detail") else "")
            _tl_html += (
                f'<div class="{_cls}">'
                f'<div class="cp-tl-date">{_disp_date}{_badge}</div>'
                f'<div class="cp-tl-title">{_entry["title"]}</div>'
                f'{_detail_htm}</div>'
            )
        st.markdown(f'<div class="cp-tl-wrap">{_tl_html}</div>', unsafe_allow_html=True)
    else:
        st.info("No timeline entries found. The JSON file may be missing.")

    # ── Tools & Integrations ──────────────────────────────────────────────────
    st.markdown('<div class="cp-sect-lbl">Configured Stack</div>', unsafe_allow_html=True)
    st.subheader("Tools & Integrations")
    st.caption("Active Claude Pro tooling ecosystem in the work environment.")

    _tool_rows = ""
    for _tn, _ts, _ta, _tst in _CP_TOOLS:
        _tbadge = ("cp-badge-done" if _tst == "Active"
                   else "cp-badge-cfg" if _tst == "Configured"
                   else "cp-badge-done")
        _tool_rows += (
            f"<tr><td><div class='cp-tool-name'>{_tn}</div>"
            f"<div class='cp-tool-sub'>{_ts}</div></td>"
            f"<td style='font-size:13px;color:{_cp_body_clr}'>{_ta}</td>"
            f"<td><span class='{_tbadge}'>{_tst}</span></td></tr>"
        )
    st.markdown(f"""<table class="cp-tools-tbl">
      <thead><tr><th>Tool</th><th>Application</th><th>Status</th></tr></thead>
      <tbody>{_tool_rows}</tbody>
    </table>""", unsafe_allow_html=True)

    # ── Update button + footer ────────────────────────────────────────────────
    st.markdown('<div style="height:1rem"></div>', unsafe_allow_html=True)
    _cp_spacer, _cp_btn_col = st.columns([5, 1])
    with _cp_btn_col:
        if st.button("🔄 Update timeline", type="primary", key="cp_update_btn",
                     use_container_width=True):
            from agent.daily_report import _update_claude_pro_report
            with st.spinner("Checking for new commits and sessions..."):
                ok = _update_claude_pro_report()
            if ok:
                st.success("✅ Timeline updated.")
                st.rerun()
            else:
                st.info("No new commits to add today.")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 7 — ENGLISH COACH
# ══════════════════════════════════════════════════════════════════════════════
elif page == "English Coach":
    import re as _ecre

    _EC_DIR      = VAULT_ROOT / "English-Coach"
    _EC_PROGRESS = _EC_DIR / "progress.md"
    _EC_SESSIONS = _EC_DIR / "sessions"

    st.markdown('<h1 style="margin-bottom:0.4rem">English Coach</h1>', unsafe_allow_html=True)
    st.caption("English practice session history · AI-rated")

    if not _EC_DIR.exists() or not _EC_PROGRESS.exists():
        st.info(
            "No sessions recorded yet. "
            "Run **english-coach.ps1** via Raycast (Win+Space → English Coach) to start your first session.",
            icon="🎙️",
        )
    else:
        # ── Parse progress table ──────────────────────────────────────────────
        _prog_text = _EC_PROGRESS.read_text(encoding="utf-8")
        _prog_rows = []
        for _line in _prog_text.splitlines():
            _m = _ecre.match(
                r"\|\s*(\d{4}-\d{2}-\d{2})[^|]*\|\s*([\d.]+)/10\s*\|\s*(\w+)\s*\|([^|]+)\|([^|]*)\|",
                _line,
            )
            if _m:
                _prog_rows.append({
                    "date":    _m.group(1),
                    "overall": float(_m.group(2)),
                    "level":   _m.group(3).strip(),
                    "scores":  _m.group(4).strip(),
                    "topic":   _m.group(5).strip(),
                })

        if _prog_rows:
            # ── KPIs ─────────────────────────────────────────────────────────
            _latest   = _prog_rows[-1]
            _avg      = sum(r["overall"] for r in _prog_rows) / len(_prog_rows)
            _best     = max(r["overall"] for r in _prog_rows)
            _k1, _k2, _k3, _k4 = st.columns(4)
            _k1.metric("Sessions", len(_prog_rows))
            _k2.metric("Latest score", f"{_latest['overall']:.1f}/10")
            _k3.metric("Overall average", f"{_avg:.1f}/10")
            _k4.metric("Best score", f"{_best:.1f}/10")
            _k1.caption(f"Current level: **{_latest['level']}**")

            st.divider()

            # ── Score trend chart ─────────────────────────────────────────────
            import pandas as _ecpd
            _df = _ecpd.DataFrame(_prog_rows).set_index("date")[["overall"]]
            _df.columns = ["Overall (0–10)"]
            st.subheader("Score progression")
            st.line_chart(_df, height=200)

            st.divider()

        # ── Recent sessions ───────────────────────────────────────────────────
        st.subheader("Recent sessions")

        _session_files = sorted(_EC_SESSIONS.glob("*_english-coach.md"), reverse=True) if _EC_SESSIONS.exists() else []

        if not _session_files:
            st.info("No session files found.")
        else:
            for _sf in _session_files[:10]:
                _stext = _sf.read_text(encoding="utf-8")
                _fm_m  = _ecre.match(r"^---\n(.*?)\n---", _stext, _ecre.DOTALL)
                if not _fm_m:
                    continue
                import yaml as _ecyaml
                _sfm = _ecyaml.safe_load(_fm_m.group(1))
                _s_date    = _sfm.get("date", _sf.stem[:10])
                _s_overall = _sfm.get("overall", "?")
                _s_level   = _sfm.get("level", "?")
                _s_body    = _stext[_fm_m.end():].strip()
                _summary_m = _ecre.search(r"> (.+)", _s_body)
                _summary   = _summary_m.group(1) if _summary_m else ""

                with st.expander(f"**{_s_date}** — {_s_overall}/10 · {_s_level}  _{_summary[:80]}_"):
                    st.markdown(_s_body, unsafe_allow_html=False)

        if _prog_rows:
            st.divider()
            st.subheader("Full log")
            st.markdown(_prog_text)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 8 — FAQ
# ══════════════════════════════════════════════════════════════════════════════
elif page == "FAQ":
    import re as _faqre

    _FAQ_FILE = VAULT_ROOT / "techcolab-backlog-faq.md"

    st.markdown('<h1 style="margin-bottom:0.4rem">FAQ</h1>', unsafe_allow_html=True)
    st.caption(
        "Questions and answers · source: `techcolab-backlog-faq.md`  "
        "— append new entries in Obsidian following the `| Question | Answer |` format."
    )

    if not _FAQ_FILE.exists():
        st.warning(f"FAQ file not found: `{_FAQ_FILE}`")
    else:
        _faq_text = _FAQ_FILE.read_text(encoding="utf-8", errors="replace")

        # ── Parse markdown table rows ─────────────────────────────────────────
        _faq_entries: list[tuple[str, str]] = []
        for _line in _faq_text.splitlines():
            _line = _line.strip()
            if not _line.startswith("|"):
                continue
            _cols = [c.strip() for c in _line.strip("|").split("|")]
            if len(_cols) < 2:
                continue
            _q, _a = _cols[0], _cols[1]
            # skip header/separator rows
            if not _q or set(_q.replace("-", "").replace(" ", "")) == set() or _q.lower() in ("dúvida", "question", "pergunta"):
                continue
            if _faqre.match(r"^[-:]+$", _q.replace(" ", "")):
                continue
            _faq_entries.append((_q, _a))

        if not _faq_entries:
            st.info("No FAQ entries found in the file.")
        else:
            # ── Search filter ─────────────────────────────────────────────────
            _faq_search = st.text_input(
                "Search", placeholder=f"Filter {len(_faq_entries)} questions...",
                key="faq_search", label_visibility="collapsed"
            )
            _faq_q = _faq_search.lower().strip()
            _filtered = [
                (q, a) for q, a in _faq_entries
                if not _faq_q or _faq_q in q.lower() or _faq_q in a.lower()
            ]

            if not _filtered:
                st.info(f"No results for **{_faq_search}**.")
            else:
                if _faq_q:
                    st.caption(f"{len(_filtered)} of {len(_faq_entries)} entries match.")
                st.markdown("<div style='margin-top:.5rem'></div>", unsafe_allow_html=True)
                for _qi, (_fq, _fa) in enumerate(_filtered):
                    with st.expander(_fq, expanded=bool(_faq_q)):
                        st.markdown(_fa)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 9 — SETTINGS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Settings":
    import json as _stjson

    _ST_JSON = Path(__file__).parent / "settings.local.json"

    # Load current overrides (if any)
    _st_overrides: dict = {}
    if _ST_JSON.exists():
        try:
            _st_overrides = _stjson.loads(_ST_JSON.read_text(encoding="utf-8"))
        except Exception:
            pass

    st.markdown('<h1 style="margin-bottom:0.2rem">Settings</h1>', unsafe_allow_html=True)
    st.caption(
        "Overrides saved to `settings.local.json` — applied at next app start. "
        "Does not modify `config.py` or environment variables directly."
    )

    # ── Ollama ────────────────────────────────────────────────────────────────
    st.divider()
    st.subheader("🦙 Ollama (local LLM)")
    st.caption("Used by the daily agent and the Claude Pro timeline updater.")

    _st_ollama_url = st.text_input(
        "OLLAMA_BASE_URL",
        value=_st_overrides.get("OLLAMA_BASE_URL", OLLAMA_BASE_URL),
        help="Base URL of the local Ollama service. Default: http://localhost:11434/v1",
        key="st_ollama_url",
    )
    _st_model = st.text_input(
        "EXTRACTION_MODEL",
        value=_st_overrides.get("EXTRACTION_MODEL", EXTRACTION_MODEL),
        help="Model used for idea extraction and summarisation. Default: llama3.2:3b",
        key="st_model",
    )

    # ── Claude Pro ────────────────────────────────────────────────────────────
    st.divider()
    st.subheader("📊 Claude Pro Report")

    _st_cp_start = st.text_input(
        "CLAUDE_PRO_START_DATE",
        value=_st_overrides.get("CLAUDE_PRO_START_DATE", CLAUDE_PRO_START_DATE),
        help="ISO date when Claude Pro adoption started (YYYY-MM-DD). Used to compute 'Days since adoption'.",
        key="st_cp_start",
    )

    # ── Read-only info ────────────────────────────────────────────────────────
    st.divider()
    st.subheader("📁 Paths (read-only)")
    st.caption("Set via environment variables — edit `.env` or system env vars to change.")

    _st_path_col1, _st_path_col2 = st.columns(2)
    with _st_path_col1:
        st.text_input("TECHCOLAB_VAULT", value=str(VAULT_ROOT), disabled=True, key="st_vault_ro")
    with _st_path_col2:
        st.text_input("Project root", value=str(Path(__file__).parent), disabled=True, key="st_root_ro")

    # ── Save ──────────────────────────────────────────────────────────────────
    st.divider()
    _st_save_col, _st_reset_col, _ = st.columns([2, 1, 5])

    with _st_save_col:
        if st.button("💾 Save settings", type="primary", use_container_width=True, key="st_save"):
            _new_overrides = {
                "OLLAMA_BASE_URL":      _st_ollama_url.strip(),
                "EXTRACTION_MODEL":     _st_model.strip(),
                "CLAUDE_PRO_START_DATE": _st_cp_start.strip(),
            }
            _ST_JSON.write_text(
                _stjson.dumps(_new_overrides, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            st.success("✅ Saved to `settings.local.json`. Restart the app to apply.")

    with _st_reset_col:
        if st.button("↺ Reset", use_container_width=True, key="st_reset"):
            if _ST_JSON.exists():
                _ST_JSON.unlink()
            st.info("Settings file removed — defaults from `config.py` will be used on next start.")
            st.rerun()

    # ── Current active values ─────────────────────────────────────────────────
    st.divider()
    st.subheader("Active values (this session)")
    st.caption("These are the values currently loaded — reflect overrides applied at startup.")
    _st_active = {
        "OLLAMA_BASE_URL": OLLAMA_BASE_URL,
        "EXTRACTION_MODEL": EXTRACTION_MODEL,
        "CLAUDE_PRO_START_DATE": CLAUDE_PRO_START_DATE,
        "TECHCOLAB_VAULT": str(VAULT_ROOT),
    }
    st.json(_st_active)
