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
