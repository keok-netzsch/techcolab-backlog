"""
components/ui.py — Pure HTML/CSS helpers and shared display constants.

Import from here instead of duplicating in every view:
    from components.ui import sdot, pbadge, area_chip, STATUS_HEX, STATUS_LABEL, ...
"""

# ── Status ────────────────────────────────────────────────────────────────────

STATUS_HEX: dict[str, str] = {
    "backlog":                    "#9CA3AF",
    "em análise":                 "#8B5CF6",
    "análise - aprovado":         "#02B793",
    "análise - rejeitado":        "#EF4444",
    "aguardando desenvolvimento": "#F59E0B",
    "em desenvolvimento":         "#F97316",
    "em validação":               "#3B82F6",
    "concluído":                  "#059669",
    "descartado":                 "#6B7280",
}

STATUS_LABEL: dict[str, str] = {
    "backlog":                    "Backlog",
    "em análise":                 "Under review",
    "análise - aprovado":         "Approved",
    "análise - rejeitado":        "Rejected",
    "aguardando desenvolvimento": "Waiting",
    "em desenvolvimento":         "In development",
    "em validação":               "In validation",
    "concluído":                  "Done",
    "descartado":                 "Discarded",
}

# ── Priority ──────────────────────────────────────────────────────────────────

PRIORITY_ICON: dict[str, str] = {"alta": "⭐⭐⭐", "média": "⭐⭐", "baixa": "⭐"}

PRIORITY_LABEL: dict[str, str] = {"alta": "High", "média": "Medium", "baixa": "Low"}

# ── Impact / Effort / Area ────────────────────────────────────────────────────

IMPACT_LABEL: dict[str, str] = {"alta": "High", "média": "Medium", "baixa": "Low"}

EFFORT_LABEL: dict[str, str] = {"alto": "High", "médio": "Medium", "baixo": "Low"}

AREA_LABEL: dict[str, str] = {
    "produto":       "Product",
    "dados & IA":    "Data & AI",
    "automação":     "Automation",
    "gestão":        "Management",
    "governança":    "Governance",
    "infraestrutura":"Infrastructure",
    "comunicação":   "Communication",
    "business":      "Business",
}

# ── HTML component functions ──────────────────────────────────────────────────

def pbadge(n: str, bg: str, fg: str = "#fff") -> str:
    """Numbered circle badge for priority display."""
    return (
        f'<span style="display:inline-flex;align-items:center;justify-content:center;'
        f'width:1.25rem;height:1.25rem;border-radius:50%;background:{bg};color:{fg};'
        f'font-weight:800;font-size:0.65rem;font-family:Georgia,serif;vertical-align:middle">{n}</span>'
    )


def sdot(status: str, size: int = 10) -> str:
    """Coloured circle indicator for a backlog status value."""
    color = STATUS_HEX.get(status, "#9CA3AF")
    return (
        f'<span style="display:inline-block;width:{size}px;height:{size}px;'
        f'border-radius:50%;background:{color};vertical-align:middle"></span>'
    )


def area_chip(area: str | None) -> str:
    """Compact muted chip for the backlog area column."""
    if not area:
        return '<span style="color:#9CA3AF;font-size:0.78rem">—</span>'
    label = AREA_LABEL.get(area, area.title())
    return (
        f'<span style="display:inline-block;font-size:0.72rem;font-weight:600;'
        f'color:#64748B;background:rgba(100,116,139,0.12);padding:2px 8px;'
        f'border-radius:10px;white-space:nowrap">{label}</span>'
    )


# ── Pre-built priority badge dict (same as app.py PRIORITY_NUM) ───────────────

PRIORITY_NUM: dict[str, str] = {
    "alta":  pbadge("3", "#1e293b"),
    "média": pbadge("2", "#64748b"),
    "baixa": pbadge("1", "#94a3b8"),
}

STATUS_COLOR: dict[str, str] = {k: sdot(k) for k in STATUS_HEX}


# ── Stat-card grid (.cc-sg / .cc-sc / .cc-sl / .cc-sv) ────────────────────────
# Dark-mode overrides for these classes live in app.py's global _DARK_CSS, so the
# component only emits the light base styles + structure.

# Column count is set INLINE on each grid div (not in the .cc-sg class) so that
# multiple grids with different column counts on the same page do not clobber each
# other via the CSS cascade.
_STAT_GRID_CSS = (
    "<style>"
    ".cc-sg{display:grid;gap:6px;margin:.5rem 0}"
    ".cc-sc{background:#F9FAFB;border:1px solid #E5E7EB;border-radius:8px;padding:8px 12px}"
    ".cc-sl{font-size:.7rem;color:#6B7280;font-weight:500;margin-bottom:2px;white-space:nowrap}"
    ".cc-sv{font-size:1.2rem;font-weight:700;color:#111827;line-height:1.2}"
    "</style>"
)


def stat_grid(cards, columns: int = 4) -> str:
    """Build the HTML for a grid of stat cards (the repeated .cc-sg/.cc-sc pattern).

    `cards` is a list of either:
      - (label, value) tuples, or
      - dicts: {"label", "value", "color"?, "vstyle"?, "extra"?} where `color`
        sets the value text colour, `vstyle` is a raw style string for the value
        (overrides `color`), and `extra` is extra HTML appended inside the card
        (e.g. a progress bar).

    Returns a self-contained string (style + grid) for st.markdown(..., unsafe_allow_html=True).
    """
    cells = []
    for c in cards:
        if isinstance(c, dict):
            label = c.get("label", "")
            value = c.get("value", "")
            color = c.get("color")
            vstyle = c.get("vstyle")
            extra = c.get("extra", "")
        else:
            label, value = c
            color, vstyle, extra = None, None, ""
        if not vstyle and color:
            vstyle = f"color:{color}"
        attr = f' style="{vstyle}"' if vstyle else ""
        cells.append(
            f'<div class="cc-sc"><div class="cc-sl">{label}</div>'
            f'<div class="cc-sv"{attr}>{value}</div>{extra}</div>'
        )
    return (
        _STAT_GRID_CSS
        + f'<div class="cc-sg" style="grid-template-columns:repeat({columns},1fr)">'
        + "".join(cells)
        + "</div>"
    )
