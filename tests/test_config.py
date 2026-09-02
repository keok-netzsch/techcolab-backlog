"""Tests for config.py — verify paths resolve correctly after folder renames."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from config import BACKLOG_DIR, EXTRACTION_MODEL, OLLAMA_BASE_URL, VAULT_ROOT

# The filesystem-existence checks below validate the *local* environment (the real
# Obsidian vault). They are skipped when the vault is absent (e.g. CI), where only
# the path-resolution and default-config tests are meaningful.
requires_vault = pytest.mark.skipif(
    not Path(VAULT_ROOT).exists(),
    reason="local vault not present (e.g. CI) — environment check skipped",
)


def test_backlog_dir_contains_backlog_items():
    assert "backlog items" in str(BACKLOG_DIR)


def test_backlog_dir_is_absolute():
    assert Path(BACKLOG_DIR).is_absolute()


@requires_vault
def test_vault_root_exists():
    assert Path(VAULT_ROOT).exists(), f"Vault root not found: {VAULT_ROOT}"


@requires_vault
def test_backlog_dir_exists():
    assert Path(BACKLOG_DIR).exists(), f"Backlog dir not found: {BACKLOG_DIR}"


@requires_vault
def test_log_dir_exists():
    log_dir = Path(VAULT_ROOT) / "Log"
    assert log_dir.exists(), f"Log dir not found: {log_dir}"


@requires_vault
def test_documentacao_md_exists():
    doc = Path(VAULT_ROOT) / "Documentacao.md"
    assert doc.exists(), f"Documentacao.md not found: {doc}"


def test_ollama_endpoint_default():
    assert OLLAMA_BASE_URL == "http://localhost:11434/v1"


def test_extraction_model_default():
    assert EXTRACTION_MODEL == "llama3.2:3b"


# Regression 2026-09-01: config.py used to fall back to a placeholder vault path
# when TECHCOLAB_VAULT was unset. Reads then resolved to missing files and returned
# empty with exit code 0 (pending.py list printed "nothing pending" while three
# pendings were open). The fallback is gone; import must fail loudly instead.
def test_missing_vault_env_raises():
    project_root = Path(__file__).parent.parent
    settings_local = project_root / "settings.local.json"
    if settings_local.exists():
        data = json.loads(settings_local.read_text(encoding="utf-8"))
        if "TECHCOLAB_VAULT" in data:
            pytest.skip("settings.local.json supplies TECHCOLAB_VAULT")

    env = {k: v for k, v in os.environ.items() if k != "TECHCOLAB_VAULT"}
    proc = subprocess.run(
        [sys.executable, "-c", "import config"],
        cwd=str(project_root),
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0, "importing config without TECHCOLAB_VAULT must fail"
    assert "TECHCOLAB_VAULT is not set" in proc.stderr
