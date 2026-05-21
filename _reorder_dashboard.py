"""
1. Fix nav: replace HTML <a href> with components.v1.html (parent.location.href)
2. Reorder Dashboard: CC Activity first, then backlog metrics
"""
with open('app.py', encoding='utf-8-sig') as f:
    content = f.read()

lines = content.split('\n')

# ──────────────────────────────────────────────────────────────
# 1. REORDER DASHBOARD
#    CC block: lines 1478..end-of-Dashboard (0-indexed 1477..~1925)
#    Backlog section: lines 1280..1477 (after title, before CC)
#    We want: title (1279) → blank → CC block → blank → backlog section
# ──────────────────────────────────────────────────────────────
# Find exact boundaries (0-indexed)
dashboard_title = 1278     # elif page == "Dashboard": (line 1275, 0-indexed 1274)
# title line is 1279 (0-indexed 1278): st.markdown('<h1 ...Dashboard...</h1>')

# Backlog section starts at line 1281 (0-indexed 1280): ideas_all = load_ideas()
# Backlog section ends at line 1477 (0-indexed 1476): _report_dialog()
# Then line 1478 (0-indexed 1477): blank line
# Then line 1479 (0-indexed 1478): st.divider()
# CC block starts at line 1479 (0-indexed 1478): st.divider()
# CC block ends at line 1925 (0-indexed ~1924) — PAGE 5 WEEKLY BRIEF starts at 1926

# Find exact end of CC block (before PAGE 5 — WEEKLY BRIEF)
cc_end_idx = None
for i, line in enumerate(lines):
    if '# PAGE 5' in line and 'WEEKLY BRIEF' in line:
        cc_end_idx = i
        break

print(f'CC block ends before line {cc_end_idx+1} (0-indexed {cc_end_idx})')

# Dashboard structure (0-indexed):
# 1274: elif page == "Dashboard":
# 1275-1277: imports
# 1278: blank
# 1279: st.markdown title
# 1280: blank
# 1281-1476: backlog metrics + by status/priority/period report
# 1477: blank (after _report_dialog)
# 1478: st.divider()          ← start of CC block (including the divider)
# 1479: st.subheader("Atividade no Claude Code")
# ...
# cc_end_idx-1: last line of CC block

title_idx      = 1278   # st.markdown('<h1 ...Dashboard...')
backlog_start  = 1280   # ideas_all = load_ideas()
backlog_end    = 1477   # blank line after _report_dialog() call (inclusive)
cc_start       = 1478   # st.divider() that precedes CC subheader

# Slices
header_lines  = lines[:title_idx + 1]           # up to and including title line
backlog_lines = lines[backlog_start:backlog_end] # backlog section
cc_lines      = lines[cc_start:cc_end_idx]       # CC activity block (starts with st.divider)
after_lines   = lines[cc_end_idx:]              # everything after Dashboard

# Build new content:
# header → blank → CC block → blank → backlog → rest
new_lines = (
    header_lines
    + ['']
    + cc_lines
    + ['']
    + ['    st.divider()']
    + backlog_lines
    + after_lines
)

content = '\n'.join(new_lines)

# ──────────────────────────────────────────────────────────────
# 2. FIX NAV: replace _navlink + st.markdown(nav) with components.v1.html
# ──────────────────────────────────────────────────────────────
old_nav = '''def _navlink(label: str, key: str) -> str:
    _a = key == page
    _s = (
        "background:rgba(2,183,147,0.14);color:#007167;font-weight:600;"
        if _a else
        "color:#4C4D58;"
    )
    # Use onclick+window.top to avoid Streamlit opening links in new tab
    _nav_js = f"window.top.location.href=\'?page={key}\'; return false;"
    return (
        f\'<a href="?page={key}" onclick="{_nav_js}" \'
        f\'style="display:inline-flex;align-items:center;\'
        f\'padding:3px 10px;border-radius:6px;font-size:0.79rem;\'
        f\'font-family:Inter,sans-serif;text-decoration:none;white-space:nowrap;cursor:pointer;{_s}">\'
        f\'{label}</a>\'
    )

_nav_items  = "".join(_navlink(p, p) for p in _PAGES_MAIN)
_nav_extras = (
    _navlink("📖", "Tutorial") +
    _navlink("📚", "Documentation") +
    f\'<a href="?page={page}" onclick="window.top.location.href=\\\'?page={page}\\\'; return false;" \'
    f\'title="Atualizar dados" style="display:inline-flex;\'
    f\'align-items:center;padding:3px 8px;border-radius:6px;font-size:0.85rem;\'
    f\'color:#9CA3AF;text-decoration:none;cursor:pointer">🔄</a>\'
)

st.markdown(
    f\'<nav style="display:flex;align-items:center;padding:5px 16px;background:#FFFFFF;\'
    f\'border-bottom:1px solid rgba(0,0,0,0.09);gap:2px;margin-bottom:0.9rem">\'
    f\'<div style="line-height:0;margin-right:14px;flex-shrink:0">{_LOGO_NAV}</div>\'
    f\'{_nav_items}\'
    f\'<div style="flex:1"></div>\'
    f\'{_nav_extras}\'
    f\'</nav>\',
    unsafe_allow_html=True,
)'''

new_nav = '''import streamlit.components.v1 as _nav_comp

def _build_nav_html(current_page: str) -> str:
    _links = ""
    for _p in _PAGES_MAIN:
        _cls = "active" if _p == current_page else ""
        _links += (
            f\'<a class="{_cls}" onclick="parent.location.href=\'
            f"'?page={_p}'"
            f\'">{_p}</a>\'
        )
    _extras = (
        f\'<a class="icon" onclick="parent.location.href=\'
        f"'?page=Tutorial'"
        f\'">📖</a>\'
        f\'<a class="icon" onclick="parent.location.href=\'
        f"'?page=Documentation'"
        f\'">📚</a>\'
        f\'<a class="icon" onclick="parent.location.href=\'
        f"'?page={current_page}'"
        f\'">🔄</a>\'
    )
    _logo_svg = _LOGO_NAV.replace("\'", "\\'")
    return f"""<!DOCTYPE html><html><head><style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:\'Inter\',sans-serif;background:#fff;height:44px;overflow:hidden}}
nav{{display:flex;align-items:center;padding:4px 16px;background:#fff;
     border-bottom:1px solid rgba(0,0,0,0.09);gap:2px;height:44px}}
.logo{{margin-right:14px;line-height:0;flex-shrink:0;cursor:pointer}}
a{{display:inline-flex;align-items:center;padding:3px 10px;border-radius:6px;
   font-size:0.79rem;text-decoration:none;white-space:nowrap;color:#4C4D58;
   cursor:pointer;border:none;background:transparent;font-family:\'Inter\',sans-serif}}
a:hover{{background:rgba(2,183,147,0.08);color:#007167}}
a.active{{background:rgba(2,183,147,0.14);color:#007167;font-weight:600}}
.spacer{{flex:1}}
.icon{{font-size:1rem;padding:3px 8px;color:#9CA3AF}}
</style></head><body>
<nav>
<div class="logo" onclick="parent.location.href=\'?page=Dashboard\'">{_logo_svg}</div>
{_links}
<div class="spacer"></div>
{_extras}
</nav></body></html>"""

_nav_comp.html(_build_nav_html(page), height=48, scrolling=False)'''

if old_nav in content:
    content = content.replace(old_nav, new_nav)
    print('Nav replaced successfully')
else:
    print('WARNING: old nav string not found exactly — trying partial match')
    # Try finding the def _navlink block
    if 'def _navlink(label: str, key: str)' in content:
        print('Found _navlink definition')
    else:
        print('ERROR: _navlink not found')

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)

print(f'Total lines: {len(content.split(chr(10)))}')
