"""
vaultindex/lint.py — structural health of the vault, from the index, with zero LLM.

Broken wikilinks, notes without frontmatter or `type`, recency markers gone stale,
duplicate stems (Obsidian cannot tell them apart), typed links (`contradicts`,
`supersedes`, …) and their resolution. Output is a report in `_reports/Vault-Lint.md`,
which is generated output by convention (ARCHITECTURE: `_reports/` is written by code).
No note is edited. The semantic contradiction pass stays with `/obsidian-reconcile`.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from vaultindex.db import connect_ro, default_root

STALE_MONTHS = 6
_RECENCY_RE = re.compile(r"\bas of (\d{4})-(\d{2})\b", re.I)
REPORT_REL = "_reports/Vault-Lint.md"
SAMPLE = 40


def _months_between(y: int, m: int, today: date) -> int:
    return (today.year - y) * 12 + (today.month - m)


def lint(*, root: Path | None = None, index_dir: Path | None = None, today: date | None = None) -> dict:
    root = Path(root or default_root())
    today = today or date.today()
    con = connect_ro(index_dir)
    try:
        notes = {r["id"]: r for r in con.execute("SELECT id, rel_path, stem, title, type, has_frontmatter, sensitive, folder FROM notes")}

        broken: dict[str, list[str]] = defaultdict(list)
        for r in con.execute("SELECT l.to_title, n.rel_path FROM links l JOIN notes n ON n.id = l.from_note WHERE l.to_note IS NULL AND l.kind = 'wikilink'"):
            broken[r["to_title"]].append(r["rel_path"])
        broken_sorted = sorted(broken.items(), key=lambda kv: (-len(kv[1]), kv[0]))

        no_fm = sorted(n["rel_path"] for n in notes.values() if not n["has_frontmatter"])
        no_type = sorted(n["rel_path"] for n in notes.values() if n["has_frontmatter"] and not n["type"])
        no_type_by_folder = Counter(p.split("/")[0] if "/" in p else "(raiz)" for p in no_type)

        stems: dict[str, list[str]] = defaultdict(list)
        for n in notes.values():
            stems[n["stem"].lower()].append(n["rel_path"])
        dup_stems = sorted(((s, sorted(ps)) for s, ps in stems.items() if len(ps) > 1), key=lambda x: x[0])

        stale: list[dict] = []
        for r in con.execute("SELECT c.text, n.rel_path FROM chunks c JOIN notes n ON n.id = c.note_id"):
            for m in _RECENCY_RE.finditer(r["text"]):
                y, mo = int(m.group(1)), int(m.group(2))
                if 1 <= mo <= 12 and _months_between(y, mo, today) > STALE_MONTHS:
                    stale.append({"path": r["rel_path"], "marker": f"as of {y}-{mo:02d}"})
        stale_by_path: dict[str, set[str]] = defaultdict(set)
        for s in stale:
            stale_by_path[s["path"]].add(s["marker"])

        typed = [
            {"kind": r["kind"], "from": r["rel_path"], "to": r["to_title"], "resolved": r["to_note"] is not None}
            for r in con.execute(
                "SELECT l.kind, l.to_title, l.to_note, n.rel_path FROM links l JOIN notes n ON n.id = l.from_note WHERE l.kind != 'wikilink' ORDER BY l.kind, n.rel_path"
            )
        ]
        superseded_targets = {t["to"].lower() for t in typed if t["kind"] == "supersedes" and t["resolved"]}
        contradictions = [t for t in typed if t["kind"] == "contradicts" and t["resolved"]]
        open_contradictions = [t for t in contradictions if t["to"].lower() not in superseded_targets and t["from"].lower()[:-3] not in superseded_targets]

        sensitive_by_type_only = sorted(
            n["rel_path"] for n in notes.values() if n["sensitive"] and not n["rel_path"].startswith(("Team/", "Stakeholders/"))
        )

        return {
            "root": str(root),
            "today": today.isoformat(),
            "notes": len(notes),
            "broken_links": {"targets": len(broken_sorted), "references": sum(len(v) for v in broken_sorted), "items": [{"target": t, "count": len(ps), "sources": sorted(set(ps))[:5]} for t, ps in broken_sorted]},
            "no_frontmatter": {"count": len(no_fm), "items": no_fm},
            "no_type": {"count": len(no_type), "by_folder": dict(no_type_by_folder.most_common()), "items": no_type},
            "duplicate_stems": {"count": len(dup_stems), "items": [{"stem": s, "paths": ps} for s, ps in dup_stems]},
            "stale_recency": {"count": len(stale_by_path), "months": STALE_MONTHS, "items": [{"path": p, "markers": sorted(ms)} for p, ms in sorted(stale_by_path.items())]},
            "typed_links": {"count": len(typed), "unresolved": sum(1 for t in typed if not t["resolved"]), "open_contradictions": open_contradictions, "items": typed},
            "sensitive_by_type_only": {"count": len(sensitive_by_type_only), "items": sensitive_by_type_only},
        }
    finally:
        con.close()


def render(rep: dict) -> str:
    L = [
        "---",
        f"date: {rep['today']}",
        "type: lint-report",
        "generated-by: python -m vaultindex lint",
        "tags: [vault-lint, generated]",
        "---",
        "",
        f"# Vault lint · {rep['today']}",
        "",
        "> Gerado por código a partir do índice (`vaultindex`). Nada aqui foi editado à mão; rodar de novo sobrescreve.",
        "",
        f"{rep['notes']} notas indexadas.",
        "",
        f"## Wikilinks quebrados: {rep['broken_links']['targets']} alvos, {rep['broken_links']['references']} referências",
        "",
    ]
    for it in rep["broken_links"]["items"][:SAMPLE]:
        L.append(f"- `[[{it['target']}]]` × {it['count']} · em: " + ", ".join(f"`{s}`" for s in it["sources"]))
    if rep["broken_links"]["targets"] > SAMPLE:
        L.append(f"- … e mais {rep['broken_links']['targets'] - SAMPLE} alvos (`--json` lista todos)")
    L += ["", f"## Sem frontmatter: {rep['no_frontmatter']['count']}", ""]
    L += [f"- `{p}`" for p in rep["no_frontmatter"]["items"][:SAMPLE]]
    if rep["no_frontmatter"]["count"] > SAMPLE:
        L.append(f"- … e mais {rep['no_frontmatter']['count'] - SAMPLE}")
    L += ["", f"## Com frontmatter mas sem `type`: {rep['no_type']['count']}", ""]
    L += [f"- {folder}: {n}" for folder, n in rep["no_type"]["by_folder"].items()]
    L += ["", f"## Nomes de arquivo duplicados (Obsidian resolve `[[Nome]]` para um só): {rep['duplicate_stems']['count']}", ""]
    for it in rep["duplicate_stems"]["items"][:SAMPLE]:
        L.append(f"- `{it['stem']}`: " + ", ".join(f"`{p}`" for p in it["paths"]))
    L += ["", f"## Marcadores de recência com mais de {rep['stale_recency']['months']} meses: {rep['stale_recency']['count']} notas", ""]
    for it in rep["stale_recency"]["items"][:SAMPLE]:
        L.append(f"- `{it['path']}`: " + ", ".join(it["markers"]))
    tl = rep["typed_links"]
    L += ["", f"## Ligações tipadas (supersedes/contradicts/causes/fixes): {tl['count']} · sem alvo: {tl['unresolved']} · contradições em aberto: {len(tl['open_contradictions'])}", ""]
    for t in tl["open_contradictions"][:SAMPLE]:
        L.append(f"- `{t['from']}` contradicts `{t['to']}`")
    for t in tl["items"][:SAMPLE]:
        L.append(f"- {t['kind']}: `{t['from']}` → `{t['to']}`" + ("" if t["resolved"] else " (alvo não encontrado)"))
    L += ["", f"## Sensível só pelo `type`, fora de Team/ e Stakeholders/: {rep['sensitive_by_type_only']['count']}", ""]
    L += [f"- `{p}`" for p in rep["sensitive_by_type_only"]["items"][:SAMPLE]]
    return "\n".join(L) + "\n"


def write_report(rep: dict, root: Path | None = None) -> Path:
    root = Path(root or default_root())
    out = root / REPORT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(rep), encoding="utf-8")
    return out
