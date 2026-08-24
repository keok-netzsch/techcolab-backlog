"""
config.py — adjust paths to match your environment.
"""

import json
import os
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

# ── Vault roots ────────────────────────────────────────────────────────────────
# Two related paths, kept explicit to avoid confusion:
#   VAULT_ROOT  = the app's working area  (…/TechColab_D&A_KO/App/Personal toolkit)
#   VAULT_BASE  = the vault top level     (…/TechColab_D&A_KO)
# VAULT_BASE is the SAME directory the call-recorder reads from its own
# TECHCOLAB_VAULT_ROOT env var. Team/ and Areas/ live under VAULT_BASE.
VAULT_ROOT = Path(
    os.environ.get(
        "TECHCOLAB_VAULT",
        r"C:\Users\YourUser\Documents\YourVault",
    )
)
VAULT_BASE = VAULT_ROOT.parent.parent

# Make the base discoverable to child processes (e.g. call-recorder) that look
# for TECHCOLAB_VAULT_ROOT, without overriding an explicit value.
os.environ.setdefault("TECHCOLAB_VAULT_ROOT", str(VAULT_BASE))

# ── Team folder (under the vault base, TechColab_D&A_KO) ──────────────────────
TEAM_DIR = VAULT_BASE / "Team"

# ── English Coach folder (vault restructure 2026-05-28: English-Coach → Areas/English-Learning)
EC_DIR = VAULT_BASE / "Areas" / "English-Learning"

# ── Source: raw notes to be ingested ───────────────────────────────────────────
VAULT_NOTES_DIR = VAULT_ROOT / "notes"

# ── Destination: structured backlog ────────────────────────────────────────────
BACKLOG_DIR = VAULT_ROOT / "backlog items"
BACKLOG_ARCHIVE_DIR = VAULT_ROOT / "excluídas"
BACKLOG_INDEX = VAULT_ROOT / "_index.md"

# ── Consolidated claude.md ──────────────────────────────────────────────────────
CLAUDE_MD = VAULT_ROOT / "claude.md"

# ── LLM backend — Ollama (local, default) or NETZSCH gateway ───────────────────
# LLM_PROVIDER = "ollama" (default, unchanged behavior) or "gateway" (routes
# through the NETZSCH LiteLLM gateway — same infra the `claude-api` CLI entry
# point uses). Flip back to "ollama" any time with no code changes.
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "ollama")
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
GATEWAY_BASE_URL = os.environ.get("GATEWAY_BASE_URL", "https://litellm.chatbot.netzsch.com")
GATEWAY_API_KEY = os.environ.get("NETZSCH_GATEWAY_KEY", "")

# Extraction/classification tasks (backlog ingestion, to-dos, tips, priority,
# translation) — high volume, low reasoning need.
EXTRACTION_MODEL = os.environ.get(
    "EXTRACTION_MODEL",
    "claude-haiku-4-5" if LLM_PROVIDER == "gateway" else "llama3.2:3b",
)
# Heavier-reasoning tasks (idea approve/reject decisions, dashboard narrative
# synthesis, Claude Code usage analysis) — separate so it can be tuned without
# touching the extraction model.
ANALYSIS_MODEL = os.environ.get(
    "ANALYSIS_MODEL",
    "claude-sonnet-5" if LLM_PROVIDER == "gateway" else EXTRACTION_MODEL,
)

# ── Claude Pro Report ─────────────────────────────────────────────────────────
# Rendered natively as a Streamlit page — no HTML file or external URL needed.
# Date when Claude Pro adoption started — used to compute "Days since adoption"
CLAUDE_PRO_START_DATE = os.environ.get("CLAUDE_PRO_START_DATE", "2026-05-11")

# ── Analysis agent parallelism ────────────────────────────────────────────────
# Number of concurrent Ollama calls for Phase 2/3 analysis.
# Default 1 = sequential (safe for single-GPU/CPU Ollama). Bump to 2-4 when
# running a faster backend or multiple Ollama instances.
ANALYSIS_WORKERS = int(os.environ.get("ANALYSIS_WORKERS", "1"))

# ── Optional password gate ────────────────────────────────────────────────────
# Format: "pbkdf2$<hex-salt>$<hex-hash>" — set via Settings page or env var.
# Empty string means gate is disabled (default).
APP_PASSPHRASE_HASH = os.environ.get("APP_PASSPHRASE_HASH", "")

# ── Ingestion behaviour ────────────────────────────────────────────────────────
# Tag appended to notes that have been fully ingested — do NOT remove manually.
INGESTED_TAG = "<!-- techcolab:ingested -->"

# Minimum character length for a note to be considered for extraction.
MIN_NOTE_LENGTH = 50
