"""components/prefs.py — Tiny on-disk UI preferences.

The custom top-nav navigates via `<form method="get">`, which does a full page
reload and therefore starts a fresh Streamlit session (session_state is wiped).
To remember a UI choice (e.g. the Backlog List/Kanban view) across navigation,
persist it to a small local JSON file instead of session_state.

Stored in .ui_prefs.json at the project root (git-ignored).
"""

import json
from pathlib import Path

_PREFS_FILE = Path(__file__).parent.parent / ".ui_prefs.json"


def get_pref(key: str, default=None):
    try:
        return json.loads(_PREFS_FILE.read_text(encoding="utf-8")).get(key, default)
    except Exception:
        return default


def set_pref(key: str, value) -> None:
    try:
        data = json.loads(_PREFS_FILE.read_text(encoding="utf-8")) if _PREFS_FILE.exists() else {}
    except Exception:
        data = {}
    data[key] = value
    try:
        _PREFS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
