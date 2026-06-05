"""views/settings.py — Settings page."""

import json
from pathlib import Path

import streamlit as st

from config import (
    CLAUDE_PRO_START_DATE,
    EXTRACTION_MODEL,
    OLLAMA_BASE_URL,
    VAULT_ROOT,
)

_ST_JSON = Path(__file__).parent.parent / "settings.local.json"


def render() -> None:
    _st_overrides: dict = {}
    if _ST_JSON.exists():
        try:
            _st_overrides = json.loads(_ST_JSON.read_text(encoding="utf-8"))
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
    st.caption("Used by the daily agent, idea extraction, agenda generation, and call note processing.")

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
    st.subheader("📊 Claude Pro Dashboard")
    st.caption("The Claude Pro page reads live from the backlog. Only the start date is configurable here.")

    _st_cp_start = st.text_input(
        "CLAUDE_PRO_START_DATE",
        value=_st_overrides.get("CLAUDE_PRO_START_DATE", CLAUDE_PRO_START_DATE),
        help="ISO date when Claude Pro adoption started (YYYY-MM-DD). Used to compute 'Days since start'.",
        key="st_cp_start",
    )

    # ── Read-only paths ────────────────────────────────────────────────────────
    st.divider()
    st.subheader("📁 Paths (read-only)")
    st.caption("Set via environment variables — edit `.env` or system env vars to change.")

    _st_path_col1, _st_path_col2 = st.columns(2)
    with _st_path_col1:
        st.text_input("TECHCOLAB_VAULT", value=str(VAULT_ROOT), disabled=True, key="st_vault_ro")
    with _st_path_col2:
        st.text_input("Project root", value=str(Path(__file__).parent.parent), disabled=True, key="st_root_ro")

    # ── Save / Reset ──────────────────────────────────────────────────────────
    st.divider()
    _st_save_col, _st_reset_col, _ = st.columns([2, 1, 5])

    with _st_save_col:
        if st.button("💾 Save settings", type="primary", use_container_width=True, key="st_save"):
            _new_overrides = {
                "OLLAMA_BASE_URL":       _st_ollama_url.strip(),
                "EXTRACTION_MODEL":      _st_model.strip(),
                "CLAUDE_PRO_START_DATE": _st_cp_start.strip(),
            }
            _ST_JSON.write_text(
                json.dumps(_new_overrides, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            st.success("✅ Saved to `settings.local.json`. Restart the app to apply.")

    with _st_reset_col:
        if st.button("↺ Reset", use_container_width=True, key="st_reset"):
            if _ST_JSON.exists():
                _ST_JSON.unlink()
            st.info("Settings file removed — defaults from `config.py` will be used on next start.")
            st.rerun()

    # ── Active values ─────────────────────────────────────────────────────────
    st.divider()
    st.subheader("Active values (this session)")
    st.caption("These are the values currently loaded — reflect overrides applied at startup.")
    st.json({
        "OLLAMA_BASE_URL":       OLLAMA_BASE_URL,
        "EXTRACTION_MODEL":      EXTRACTION_MODEL,
        "CLAUDE_PRO_START_DATE": CLAUDE_PRO_START_DATE,
        "TECHCOLAB_VAULT":       str(VAULT_ROOT),
    })
