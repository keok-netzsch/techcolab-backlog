"""views/faq.py — FAQ page."""

import re

import streamlit as st

from config import VAULT_ROOT


def render() -> None:
    _FAQ_FILE = VAULT_ROOT / "techcolab-backlog-faq.md"

    st.markdown('<h1 style="margin-bottom:0.4rem">FAQ</h1>', unsafe_allow_html=True)
    st.caption(
        "Questions and answers · source: `techcolab-backlog-faq.md`  "
        "— append new entries in Obsidian following the `| Question | Answer |` format."
    )

    if not _FAQ_FILE.exists():
        st.warning(f"FAQ file not found: `{_FAQ_FILE}`")
        return

    _faq_text = _FAQ_FILE.read_text(encoding="utf-8", errors="replace")

    _faq_entries: list[tuple[str, str]] = []
    for _line in _faq_text.splitlines():
        _line = _line.strip()
        if not _line.startswith("|"):
            continue
        _cols = [c.strip() for c in _line.strip("|").split("|")]
        if len(_cols) < 2:
            continue
        _q, _a = _cols[0], _cols[1]
        if not _q or set(_q.replace("-", "").replace(" ", "")) == set() or _q.lower() in ("dúvida", "question", "pergunta"):
            continue
        if re.match(r"^[-:]+$", _q.replace(" ", "")):
            continue
        _faq_entries.append((_q, _a))

    if not _faq_entries:
        st.info("No FAQ entries found in the file.")
        return

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
        return

    if _faq_q:
        st.caption(f"{len(_filtered)} of {len(_faq_entries)} entries match.")
    st.markdown("<div style='margin-top:.5rem'></div>", unsafe_allow_html=True)
    for _fq, _fa in _filtered:
        with st.expander(_fq, expanded=bool(_faq_q)):
            st.markdown(_fa)
