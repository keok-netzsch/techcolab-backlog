# Design System — Personal Toolkit · Techco.lab

> **Mandatory.** Every new page in this Streamlit app must follow this document.
> Read this before creating any new `st.*` page or section.

---

## Color Palette

| Role | Hex | Usage |
|---|---|---|
| Accent | `#02B793` | Buttons, active links, key numbers, icons |
| Accent hover | `#007167` | Hover states on accent elements |
| Accent light | `#0AD4A8` | Gradient endpoint on buttons/progress bars |
| Text primary | `#111827` | Card values, main body text |
| Text secondary | `#6B7280` | Card labels, column headers, captions |
| Text muted | `#9CA3AF` | Meta lines, taglines, secondary context |
| Border | `#E5E7EB` | Card borders, `<hr>` replacements |
| Card background | `#F9FAFB` | Stat cards (`.cc-sc`) |
| Issue / Error | `#EF4444` | Issue cards, warning status |
| Success | `#059669` | "How to fix" cards, OK status |
| Opportunity | `#6366F1` | Opportunity cards, insight callouts |

---

## Typography

- **Global font:** `Inter` (loaded via Google Fonts in the page CSS)
- **Page title (`h1`):** gradient text `#007167 → #8AC6BD`, bold, `letter-spacing: -0.02em`
- **Section headers:** use `st.subheader()` — never bold markdown `**text**` as a heading
- **Card label:** `font-size: .7rem; color: #6B7280; font-weight: 500`
- **Card value:** `font-size: 1.2rem; font-weight: 700; color: #111827; line-height: 1.2`
- **Meta / muted text:** `font-size: .75rem; color: #9CA3AF; font-style: italic`
- **Status line:** `font-size: .78rem`

---

## Card Grid Pattern

Use the `.cc-*` CSS classes (injected via `st.markdown(..., unsafe_allow_html=True)`) for stat grids.

```css
.cc-sg { display: grid; grid-template-columns: repeat(4,1fr); gap: 6px; margin: .5rem 0 }
.cc-sc { background: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 8px; padding: 8px 12px }
.cc-sl { font-size: .7rem; color: #6B7280; font-weight: 500; margin-bottom: 2px; white-space: nowrap }
.cc-sv { font-size: 1.2rem; font-weight: 700; color: #111827; line-height: 1.2 }
```

**Usage template:**

```python
st.markdown(
    '<style>'
    '.cc-sg{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin:.5rem 0}'
    '.cc-sc{background:#F9FAFB;border:1px solid #E5E7EB;border-radius:8px;padding:8px 12px}'
    '.cc-sl{font-size:.7rem;color:#6B7280;font-weight:500;margin-bottom:2px;white-space:nowrap}'
    '.cc-sv{font-size:1.2rem;font-weight:700;color:#111827;line-height:1.2}'
    '</style>'
    '<div class="cc-sg">'
    '<div class="cc-sc"><div class="cc-sl">Label</div><div class="cc-sv">Value</div></div>'
    '</div>',
    unsafe_allow_html=True,
)
```

Override column count with `style="grid-template-columns:repeat(6,1fr)"` on `.cc-sg`.

---

## Diagnostic Cards (Border-Left Pattern)

For issues, fixes, and opportunities — always use the border-left card style, never `st.error()` / `st.success()` / `st.warning()` banners for diagnostic content.

```python
# Issue card
st.markdown(
    '<div style="margin:.4rem 0;padding:.5rem .75rem;border-radius:6px;'
    'border-left:3px solid #EF4444;background:rgba(239,68,68,.05)">'
    '<span style="font-size:.7rem;color:#EF4444;font-weight:700;'
    'text-transform:uppercase;letter-spacing:.04em">Issue</span><br>{content}'
    '</div>', unsafe_allow_html=True,
)

# How to fix card
st.markdown(
    '<div style="margin:-.2rem 0 .5rem;padding:.5rem .75rem;border-radius:6px;'
    'border-left:3px solid #059669;background:rgba(5,150,105,.05)">'
    '<span style="font-size:.7rem;color:#059669;font-weight:700;'
    'text-transform:uppercase;letter-spacing:.04em">How to fix</span><br>{content}'
    '</div>', unsafe_allow_html=True,
)

# Opportunity card
st.markdown(
    '<div style="margin:.4rem 0;padding:.5rem .75rem;border-radius:6px;'
    'border-left:3px solid #6366F1;background:rgba(99,102,241,.05)">'
    '<span style="font-size:.7rem;color:#6366F1;font-weight:700;'
    'text-transform:uppercase;letter-spacing:.04em">Opportunity</span><br>{content}'
    '</div>', unsafe_allow_html=True,
)
```

---

## Status Indicator

Use a compact single-line status rather than Streamlit banners at the surface level of a section.

```python
_ni, _no = len(issues), len(opportunities)
_color = "#EF4444" if _ni else "#059669"
_icon  = "⚠" if _ni else "✓"
_label = f"{_ni} {'issue' if _ni == 1 else 'issues'}" if _ni else "No issues"
st.markdown(
    f'<p style="font-size:.78rem;margin:.4rem 0 .3rem">'
    f'<span style="color:{_color}">{_icon} {_label}</span>'
    f'<span style="color:#9CA3AF">  ·  {_no} opportunities</span></p>',
    unsafe_allow_html=True,
)
```

---

## Meta / Context Line

Combine taglines, project context, and secondary captions into **one** `<p>` element. Never use multiple separate `st.caption()` calls for items that can fit on one line.

```python
parts = ["<em>tagline text</em>", "Projects: <b>Alpha</b> 12 · <b>Beta</b> 8"]
st.markdown(
    f'<p style="font-size:.75rem;color:#9CA3AF;margin:.1rem 0 .8rem">'
    f'{"  ·  ".join(parts)}</p>',
    unsafe_allow_html=True,
)
```

---

## Minimalism Rules

These rules were established through iteration on Dashboard and CC Activity pages:

1. **No Streamlit banners for diagnostic content.** Never use `st.success()`, `st.error()`, `st.warning()` to communicate analysis results — they are too visually heavy. Reserve them for true operational alerts (e.g., "No vault found").

2. **No standalone bold headings.** Do not write `st.markdown("**N issues identified**")` as a section header. Use a status indicator line or `st.subheader()`.

3. **No manual HR dividers.** Never insert `<hr>` between sections. Use `st.divider()` only at page-level boundaries; otherwise rely on CSS spacing (margin) and Streamlit's natural column gaps.

4. **Collapse details, surface status.** For diagnostic sections: show a one-line status indicator at the surface level, and put all detail cards inside `st.expander(expanded=False)`. One expander per section, not one per category.

5. **One meta line, not many captions.** Combine tagline + project list + context notes into a single muted `<p>`. Each `st.caption()` is a separate DOM element — use it only when content is truly standalone.

6. **Tables via `st.columns()`.** Use `st.columns([1, 5, 3])` + `.caption()` / `.markdown()` for ranked lists and tables. Never build HTML `<table>` elements from Python.

7. **Cards keep their borders.** The `.cc-sc` card border (`1px solid #E5E7EB`) is the visual anchor of this design. Do not remove it for "cleaner" looks — it is the cleaner look.

---

## Page Structure Template

```
st.subheader("Page Title")                        # or st.title() for top-level pages

# One compact meta line (if contextual info needed)
st.markdown('<p style="font-size:.75rem;color:#9CA3AF;...">...</p>', unsafe_allow_html=True)

# Primary content
# Option A — Stat grid
st.markdown('<style>...</style><div class="cc-sg">...</div>', unsafe_allow_html=True)

# Option B — Column table
_h0, _h1, _h2 = st.columns([1, 5, 3])
_h0.caption("Score"); _h1.caption("Item"); _h2.caption("Detail")
for item in items:
    _c0, _c1, _c2 = st.columns([1, 5, 3])
    _c0.markdown(f"**{item.score}**")
    _c1.markdown(f"`{item.id}` {item.title}")
    _c2.caption(item.meta)

# Diagnostic section (if applicable)
# [status indicator line]
# [one st.expander(expanded=False) with all cards inside]
```

---

## UI Language

**All UI text must be in English.** This applies to every label, button, caption, heading, expander title, metric label, and status message. The only exception is user-generated vault content displayed verbatim.
