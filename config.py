"""
config.py — adjust paths to match your environment.
"""

import os
import json
from pathlib import Path

# ── Local settings overrides (written by the Settings page in app.py) ──────────
# settings.local.json is loaded first so its values are visible to os.environ.get()
_PROJECT_ROOT_EARLY = Path(__file__).parent
_SETTINGS_LOCAL = _PROJECT_ROOT_EARLY / "settings.local.json"
if _SETTINGS_LOCAL.exists():
    try:
        _overrides = json.loads(_SETTINGS_LOCAL.read_text(encoding="utf-8"))
        for _k, _v in _overrides.items():
            if _k not in os.environ:           # env var wins over file
                os.environ[_k] = str(_v)
    except Exception:
        pass

# ── Vault root ─────────────────────────────────────────────────────────────────
VAULT_ROOT = Path(
    os.environ.get(
        "TECHCOLAB_VAULT",
        r"C:\Users\YourUser\Documents\YourVault",
    )
)

# ── Team folder (one level above vault, under TechColab_D&A_KO) ───────────────
TEAM_DIR = VAULT_ROOT.parent.parent / "Team"

# ── English Coach folder (same level as Team) ──────────────────────────────────
EC_DIR = VAULT_ROOT.parent.parent / "English-Coach"

# ── Source: raw notes to be ingested ───────────────────────────────────────────
VAULT_NOTES_DIR = VAULT_ROOT / "notes"

# ── Destination: structured backlog ────────────────────────────────────────────
BACKLOG_DIR = VAULT_ROOT / "backlog items"
BACKLOG_ARCHIVE_DIR = VAULT_ROOT / "excluídas"
BACKLOG_INDEX = VAULT_ROOT / "_index.md"

# ── Consolidated claude.md ──────────────────────────────────────────────────────
CLAUDE_MD = VAULT_ROOT / "claude.md"

# ── Ollama (local LLM) ─────────────────────────────────────────────────────────
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
EXTRACTION_MODEL = os.environ.get("EXTRACTION_MODEL", "llama3.2:3b")

# ── Claude Pro Report (served locally, auto-updated daily by agent) ───────────
# HTML file lives inside this project under reports/. No external URL needed.
# Set CLAUDE_PRO_REPORT_HTML env var to override the path.
CLAUDE_PRO_REPORT_HTML = Path(
    os.environ.get(
        "CLAUDE_PRO_REPORT_HTML",
        str(_PROJECT_ROOT_EARLY / "reports" / "claude-pro-report.html"),
    )
)
# Date when Claude Pro adoption started — used to compute "Days since adoption"
CLAUDE_PRO_START_DATE = os.environ.get("CLAUDE_PRO_START_DATE", "2026-05-11")

# ── Ingestion behaviour ────────────────────────────────────────────────────────
# Tag appended to notes that have been fully ingested — do NOT remove manually.
INGESTED_TAG = "<!-- techcolab:ingested -->"

# Minimum character length for a note to be considered for extraction.
MIN_NOTE_LENGTH = 50
