"""
vaultindex — derived search index over the Obsidian vault.

Markdown in the vault is the source of truth. This package builds a SQLite index (FTS5 +
local ONNX embeddings) that can be deleted and rebuilt at any moment, and answers queries
from the CLI (`python -m vaultindex ...`) and from the `techcolab-vault` MCP. No LLM
anywhere in the path. Nothing leaves the machine.

Design: vault/decisions/2026-09-03-vault-index-busca-hibrida-local.md (idea-097).
"""

__all__ = ["build", "check", "search", "stats"]

from vaultindex.db import build, check, stats  # noqa: E402
from vaultindex.search import search  # noqa: E402
