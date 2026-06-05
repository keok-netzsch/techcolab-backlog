"""views/documentation.py — Documentation & Context page."""

import streamlit as st

from config import BACKLOG_DIR, EXTRACTION_MODEL, OLLAMA_BASE_URL, VAULT_ROOT


def render() -> None:
    st.markdown('<h1 style="margin-bottom:0.4rem">Documentation & Context</h1>', unsafe_allow_html=True)
    st.info("**Repository:** [github.com/keok-netzsch/techcolab-backlog](https://github.com/keok-netzsch/techcolab-backlog)", icon="📦")

    st.markdown("## Overview")
    st.markdown("""
**Personal Toolkit · Techco.lab** is a personal productivity toolkit integrated with an Obsidian vault.
Ideas are captured, structured and tracked locally — no external API, no cloud dependency.
Transcription (Whisper) and LLM inference (Ollama + llama3.2:3b) run entirely on-machine.
""")

    st.divider()
    st.markdown("## System architecture")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
**Data flow**

```
Manual form (Backlog page)
    ↓ backlog/store.py → idea-NNN.md
    ↓ backlog/daily_log.py → diario-YYYY-MM-DD.md
    ↓ backlog/cache.py → load_ideas() (cached)

Call Recorder (call-recorder.ps1)
    ↓ record.py → WAV → Whisper transcription
    ↓ process.py → Ollama → structured notes
    ↓ vault/Team/{Person}/1on1/{date}_1on1.md

Daily agent (run_agent.bat @ 08:00)
    ↓ agent/daily_report.py → report-YYYY-MM-DD.md
    ↓ agent/scrape_sessions.py → claude-pro-timeline.json
```
""")
    with col2:
        st.markdown("""
**Vault structure**

```
TechColab_D&A_KO/
├── App/
│   └── Personal toolkit/
│       ├── backlog items/    ← idea-NNN.md
│       ├── Log/              ← diario-YYYY-MM-DD.md
│       ├── agent-reports/    ← report-YYYY-MM-DD.md
│       └── techcolab-backlog-faq.md
├── Team/
│   └── {Person}/
│       ├── 1on1.md           ← structured 1:1 history
│       ├── 1on1/             ← call notes (standalone)
│       ├── OKR.md
│       ├── PDI.md
│       └── Overview.md
├── Stakeholders/
│   └── {Person}/
│       ├── 1on1.md
│       └── 1on1/
└── Resources/
    └── techcolab-brand.md
```
""")

    st.divider()
    st.markdown("## Pages & views")

    st.markdown("""
| View file | Page | Data source |
|---|---|---|
| `views/dashboard.py` | Dashboard | `load_ideas()` — live backlog |
| `views/backlog.py` | Backlog | `load_ideas()`, `BacklogStore` |
| `views/todo_list.py` | To-Do List | `load_ideas()` |
| `views/team.py` | Team | Vault `Team/{Person}/` files |
| `views/claude_pro.py` | Claude Pro | `load_ideas()` + `reports/claude-pro-data.json` (exec summary + tools only) |
| `views/weekly_brief.py` | Weekly Brief | `load_ideas()` + vault `Log/` + vault `Team/{Person}/1on1/` |
| `views/english_coach.py` | English Coach | Vault `English-Coach/` |
| `views/settings.py` | Settings | `settings.local.json` + `config.py` |
| `views/tutorial.py` | Tutorial | Static content |
| `views/documentation.py` | Documentation | Static content + live `config.py` values |
| `views/faq.py` | FAQ | Vault `techcolab-backlog-faq.md` |
""")

    st.divider()
    st.markdown("## Idea file format")
    st.code("""---
id: idea-001
titulo: "Nome da ideia"
status: backlog
prioridade: alta
area: dados & IA
origem: entrada direta
criado_em: 2026-05-15
atualizado_em: 2026-05-15
due_date: 2026-06-30
impacto: alta
esforco: médio
is_bug: false
agente_autorizado: false
---

## Descricao
Descrição da ideia.

## To-dos
- [ ] Next pending step
- [x] Step already done @2026-05-20 ~2026-05-22

## Notas
Anotações livres.
""", language="markdown")

    st.markdown("""
**To-do annotation format:**
- `@YYYY-MM-DD` — due date
- `~YYYY-MM-DD` — completed date (set automatically when marked done)
- `{bug}` — marks the to-do as a bug (shows BUG badge in To-Do List)
- `{auto}` — marks as pre-approved for the daily agent

**Valid values:**

| Field | Values |
|---|---|
| `status` | `backlog`, `em análise`, `análise - aprovado`, `análise - rejeitado`, `aguardando desenvolvimento`, `em desenvolvimento`, `em validação`, `concluído`, `descartado` |
| `prioridade` | `alta`, `média`, `baixa` |
| `impacto` | `alta`, `média`, `baixa` |
| `esforco` | `alto`, `médio`, `baixo` |
| `area` | `produto`, `dados & IA`, `automação`, `gestão`, `governança`, `infraestrutura`, `comunicação`, `business` |
| `sprint` | Free text — e.g. `S1`, `Jun/26`. Groups ideas for burn tracking. |
| `okr_ref` | Free text — e.g. `Pedro O1-KR2`. Links idea to an OKR objective/key result. |
| `blocked_by` | YAML list of idea IDs — e.g. `[idea-003, idea-007]`. |
""")

    st.divider()
    st.markdown("## Key files")

    st.markdown("""
| File | Purpose |
|---|---|
| `app.py` | Entry point — nav routing, dark mode, CSS injection |
| `config.py` | All configurable paths and constants |
| `assets/brand.css` | Global CSS (always loaded) — fonts, primary buttons, expander stability rules |
| `backlog/store.py` | CRUD for idea files — `create()`, `save()`, `delete()`, auto-status-advance |
| `backlog/cache.py` | `load_ideas()` (cached), `get_store()`, `rebuild_index()` |
| `backlog/schema.py` | `Idea` dataclass, `VALID_STATUSES`, `VALID_AREAS` |
| `components/ui.py` | Shared HTML helpers — `sdot()`, `pbadge()`, `stat_grid()`, `STATUS_LABEL`, `STATUS_HEX` |
| `agent/daily_report.py` | Morning agent — backlog analysis + Claude Pro timeline update |
| `agent/scrape_sessions.py` | Reads Claude Code JSONL session files → timeline entries |
| `reports/claude-pro-data.json` | Static config for Claude Pro page (exec summary bullets + tools list only) |
| `call-recorder/call-recorder.ps1` | Unified recorder — team + stakeholder menu, auto-language detection |
| `call-recorder/record.py` | Whisper transcription — returns `(text, detected_lang)` |
| `call-recorder/process.py` | Ollama note structuring — saves BLOCO content to vault |
| `tests/` | 150 tests — run with `python -m pytest tests/ -v` |
""")

    st.divider()
    st.markdown("## CSS architecture")

    st.markdown("""
CSS is split into three layers, injected in `app.py` on every page load:

| Layer | Source | When |
|---|---|---|
| Brand CSS | `assets/brand.css` | Always — fonts, buttons, expander stability, nav |
| Dark mode CSS | `_DARK_CSS` string in `app.py` | Only when `?dark=1` query param |
| Page-scoped CSS | `st.markdown("<style>...")` inside each view | Only on that page |

**Critical rule:** never use `div[data-testid="stVerticalBlockBorderWrapper"]` as a global CSS selector in any view — it bleeds across Streamlit SPA navigation and clips expander content. Use `st.container(height=N)` instead.
""")

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

    st.caption("To change Ollama settings, use the **Settings** page. To change vault path, set the `TECHCOLAB_VAULT` environment variable.")
