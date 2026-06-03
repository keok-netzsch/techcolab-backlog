"""
backlog/cache.py — Cached store access shared across views.

Centralises get_store / load_ideas so every view imports from here
instead of duplicating the @st.cache_data logic.
"""

from pathlib import Path

import streamlit as st

from backlog.store import BacklogStore
from config import BACKLOG_DIR


def get_store() -> BacklogStore:
    return BacklogStore(Path(BACKLOG_DIR))


def _backlog_mtime() -> tuple[int, float]:
    """Cache key for the backlog list. Includes file COUNT so adding/
    deleting an idea invalidates the cache (max-mtime alone misses moves
    and deletions — moving a file out of the dir doesn't change the max
    mtime of the survivors, leaving a stale 'ghost' card)."""
    try:
        files = list(Path(BACKLOG_DIR).glob("*.md"))
        return (len(files), max((f.stat().st_mtime for f in files), default=0.0))
    except OSError:
        return (0, 0.0)


@st.cache_data(show_spinner=False)
def _load_ideas_cached(cache_key: tuple[int, float]):
    return get_store().load_all()


def load_ideas():
    return _load_ideas_cached(_backlog_mtime())


def rebuild_index(store: BacklogStore) -> None:
    from backlog.index import generate_index
    from config import BACKLOG_INDEX
    generate_index(store.load_all(), Path(BACKLOG_INDEX))
