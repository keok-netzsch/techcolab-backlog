"""
config.py — adjust paths to match your environment.
"""

import os
from pathlib import Path

# ── Vault root ─────────────────────────────────────────────────────────────────
VAULT_ROOT = Path(
    os.environ.get(
        "TECHCOLAB_VAULT",
        r"C:\Users\YourUser\Documents\YourVault",
    )
)

# ── Source: raw notes to be ingested ───────────────────────────────────────────
VAULT_NOTES_DIR = VAULT_ROOT / "notes"

# ── Destination: structured backlog ────────────────────────────────────────────
BACKLOG_DIR = VAULT_ROOT / "Backlog - to do - app" / "backlog items"
BACKLOG_ARCHIVE_DIR = VAULT_ROOT / "Backlog - to do - app" / "excluídas"
BACKLOG_INDEX = VAULT_ROOT / "Backlog - to do - app" / "_index.md"

# ── Consolidated claude.md ──────────────────────────────────────────────────────
CLAUDE_MD = VAULT_ROOT / "claude.md"

# ── Ollama (local LLM) ─────────────────────────────────────────────────────────
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
EXTRACTION_MODEL = os.environ.get("EXTRACTION_MODEL", "llama3.2:3b")

# ── Claude Pro Report repo (auto-updated daily by agent) ──────────────────────
# Set CLAUDE_PRO_REPORT_DIR env var to override. Must be a local git clone of
# github.com/keok-netzsch/claude-pro-report with push access configured.
CLAUDE_PRO_REPORT_DIR = Path(
    os.environ.get(
        "CLAUDE_PRO_REPORT_DIR",
        r"C:\Users\Kelvin.okuda\AppData\Local\Temp\claude-pro-report",
    )
)
# Date when Claude Pro adoption started — used to compute "Dias desde adoção"
CLAUDE_PRO_START_DATE = "2026-05-11"

# ── Ingestion behaviour ────────────────────────────────────────────────────────
# Tag appended to notes that have been fully ingested — do NOT remove manually.
INGESTED_TAG = "<!-- techcolab:ingested -->"

# Minimum character length for a note to be considered for extraction.
MIN_NOTE_LENGTH = 50
