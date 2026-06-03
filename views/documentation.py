"""views/documentation.py — Documentation & Context page."""

import streamlit as st

from config import BACKLOG_DIR, EXTRACTION_MODEL, OLLAMA_BASE_URL, VAULT_ROOT


def render() -> None:
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
`%USERPROFILE%\\techcolab-backlog\\DESIGN_SYSTEM.md`
""")
        st.markdown("""
**Quick reference** (hex values, Canva/PPT/Figma, snippets)
`Resources/techcolab-brand.md` no vault
""")
    with col_ds2:
        st.markdown("""
**CSS pronto para importar** em HTML/relatórios
`%USERPROFILE%\\techcolab-backlog\\scripts\\techcolab-brand.css`
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
