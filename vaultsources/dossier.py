"""vaultsources/dossier.py — o vault falando antes de ser perguntado.

Ate 2026-09-10 o vault so respondia quando o Kelvin perguntava. Ele tem 1129
notas, um indice hibrido e nenhum momento em que aquilo chega sozinho. O momento
obvio e o mais caro de perder: 15 minutos antes de uma call com alguem sobre quem
o vault tem historico.

Este modulo monta a materia-prima do dossie de forma **deterministica** — nada de
modelo resumindo pessoa (padrao 2). Ele so recorta e data o que ja esta escrito:

    ultimo 1:1        de que dia foi, e os topicos daquela conversa
    compromissos      `- [ ] (Dono) ... @data` em aberto nas notas da pessoa
    o que mudou       notas tocadas desde o ultimo encontro
    pendencias        itens do ledger que citam a pessoa
    projetos          projetos onde o nome aparece

Tudo local. Nada daqui sai da maquina: e conteudo de `Team/` e `Stakeholders/`,
que o `governance.py` classifica como origem `vault` e nunca deixa ir a provedor
externo.

Consumidor: a rotina Claude `dossie-do-dia` (dias uteis 07:45), que le a agenda do
dia e chama isto para cada reuniao com pessoa conhecida.
"""

from __future__ import annotations

import re
import sys
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path

from vaultsources import paths

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

TODO_OPEN = re.compile(r"^\s*-\s*\[ \]\s*(.+)$", re.M)
DATE_IN_NAME = re.compile(r"(\d{4}-\d{2}-\d{2})")


def _deaccent(text: str) -> str:
    norm = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in norm if not unicodedata.combining(c))


def person_dir(name: str) -> Path | None:
    """Acha a pasta da pessoa em Team/ ou Stakeholders/, por nome aproximado."""
    target = re.sub(r"[^a-z]+", "", _deaccent(name).lower())
    if not target:
        return None
    best = None
    for base in ("Team", "Stakeholders"):
        root = paths.VAULT / base
        if not root.exists():
            continue
        for d in root.iterdir():
            if not d.is_dir() or d.name.startswith(("_", ".")):
                continue
            flat = re.sub(r"[^a-z]+", "", _deaccent(d.name).lower())
            if flat == target:
                return d
            if best is None and (target in flat or flat in target) and len(target) >= 4:
                best = d
    return best


def last_meeting(pdir: Path) -> dict | None:
    """A nota de 1:1 mais recente da pessoa, com data e topicos."""
    hits = []
    for p in list(pdir.glob("1on1/*.md")) + list(pdir.glob("1on1.md")):
        m = DATE_IN_NAME.search(p.name)
        when = m.group(1) if m else datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d")
        hits.append((when, p))
    if not hits:
        return None
    when, p = max(hits, key=lambda x: x[0])
    text = p.read_text(encoding="utf-8", errors="replace")
    topics = [ln.strip("#* ").strip() for ln in text.splitlines()
              if ln.startswith(("## ", "### ")) and len(ln) < 120][:8]
    return {"date": when, "file": str(p.relative_to(paths.VAULT)), "topics": topics}


def open_actions(pdir: Path, limit: int = 12) -> list[dict]:
    out = []
    for p in sorted(pdir.rglob("*.md")):
        text = p.read_text(encoding="utf-8", errors="replace")
        for item in TODO_OPEN.findall(text):
            item = re.sub(r"[*_`]", "", item).strip()
            if len(item) < 8:
                continue
            due = re.search(r"@(\d{4}-\d{2}-\d{2})", item)
            out.append({"text": item[:180], "due": due.group(1) if due else "",
                        "file": str(p.relative_to(paths.VAULT))})
    out.sort(key=lambda a: (a["due"] == "", a["due"]))
    return out[:limit]


def changed_since(pdir: Path, since: str, limit: int = 8) -> list[dict]:
    try:
        cutoff = datetime.strptime(since, "%Y-%m-%d")
    except ValueError:
        cutoff = datetime.now() - timedelta(days=30)
    out = []
    for p in sorted(pdir.rglob("*.md")):
        mt = datetime.fromtimestamp(p.stat().st_mtime)
        if mt > cutoff:
            out.append({"file": str(p.relative_to(paths.VAULT)),
                        "when": mt.strftime("%Y-%m-%d")})
    out.sort(key=lambda x: x["when"], reverse=True)
    return out[:limit]


def ledger_items(name: str, limit: int = 6) -> list[dict]:
    try:
        from agent import pending
        data = pending._load()
    except Exception:
        return []
    needle = " " + re.sub(r"[^a-z0-9]+", " ", _deaccent(name).lower()).strip() + " "
    first = needle.strip().split(" ")[0]
    out = []
    for item in data.get("itens", []):
        if item.get("resolvida_em"):
            continue
        hay = " " + re.sub(r"[^a-z0-9]+", " ", _deaccent(item.get("texto", "")).lower()) + " "
        if needle in hay or (len(first) > 3 and (" " + first + " ") in hay):
            out.append({"id": item.get("id", ""), "texto": item.get("texto", "")[:200],
                        "prioridade": item.get("prioridade", "")})
    return out[:limit]


def projects_mentioning(name: str, limit: int = 6) -> list[str]:
    root = paths.VAULT / "Projects"
    if not root.exists():
        return []
    first = _deaccent(name).split()[0].lower() if name.split() else ""
    if len(first) < 4:
        return []
    out = []
    for p in sorted(root.rglob("*.md")):
        text = _deaccent(p.read_text(encoding="utf-8", errors="replace")).lower()
        if first in text:
            out.append(str(p.relative_to(paths.VAULT)))
        if len(out) >= limit:
            break
    return out


def build(name: str) -> dict:
    pdir = person_dir(name)
    if pdir is None:
        return {"name": name, "found": False,
                "why": "nao ha pasta para esta pessoa em Team/ nem em Stakeholders/"}
    last = last_meeting(pdir)
    since = last["date"] if last else (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    return {
        "name": name,
        "found": True,
        "folder": str(pdir.relative_to(paths.VAULT)),
        "last_meeting": last,
        "open_actions": open_actions(pdir),
        "changed_since": changed_since(pdir, since),
        "ledger": ledger_items(name),
        "projects": projects_mentioning(name),
    }


def render(d: dict) -> str:
    if not d.get("found"):
        return "%s: %s" % (d["name"], d.get("why", ""))
    lines = ["## %s" % d["name"], ""]
    last = d.get("last_meeting")
    if last:
        dias = (datetime.now() - datetime.strptime(last["date"], "%Y-%m-%d")).days
        lines.append("Ultimo 1:1: %s (%d dias atras)" % (last["date"], dias))
        for t in last["topics"][:5]:
            lines.append("  · %s" % t)
    else:
        lines.append("Sem 1:1 registrado.")
    lines.append("")
    acoes = d.get("open_actions") or []
    if acoes:
        lines.append("Compromissos em aberto (%d):" % len(acoes))
        hoje = datetime.now().strftime("%Y-%m-%d")
        for a in acoes[:6]:
            atraso = " ATRASADO" if a["due"] and a["due"] < hoje else ""
            lines.append("  - %s%s%s" % (a["text"][:130],
                                         (" @" + a["due"]) if a["due"] else "", atraso))
        lines.append("")
    led = d.get("ledger") or []
    if led:
        lines.append("Ledger:")
        for i in led:
            lines.append("  - %s %s" % (i["id"], i["texto"][:130]))
        lines.append("")
    mud = d.get("changed_since") or []
    if mud:
        lines.append("Mudou desde o ultimo encontro:")
        for m in mud[:5]:
            lines.append("  - %s (%s)" % (m["file"], m["when"]))
        lines.append("")
    proj = d.get("projects") or []
    if proj:
        lines.append("Projetos onde o nome aparece: " + ", ".join(
            Path(x).stem for x in proj[:5]))
    return "\n".join(lines).rstrip()
