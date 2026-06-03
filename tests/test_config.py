"""Tests for config.py — verify paths resolve correctly after folder renames."""

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
