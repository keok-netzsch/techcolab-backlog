"""vaultsources/concepts.py — a camada onde uma ideia amadurece.

O diagnostico de 2026-09-10: os 25 tipos de nota do vault sao todos episodicos
(`session`, `capture`, `manager-call`, `project-meeting`, `1on1-session`). Havia 6
notas do tipo `resource` e 9 do tipo `area` em 1129. Nao existia lugar onde uma
posicao se acumulasse — so registro do que aconteceu.

Uma pagina de conceito responde "o que eu penso hoje sobre X, e por que". Ela e
reescrita quando uma fonte nova confirma, contradiz ou acrescenta. O que ela nunca
faz e ser reescrita sozinha: fonte externa **propoe** (padrao 3, silencio nao e
consentimento) e a proposta vai para `Concepts/_proposals/` ate alguem aceitar.
Descartar move para `_rejected/`, nao apaga.

Contradicao aberta e um estado legitimo e fica visivel no proprio arquivo, com as
duas datas. Uma pagina que esconde a divergencia mente mais que uma que a mostra.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

from vaultsources import paths
from vaultsources.note import slugify, _yaml_str

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from vaultindex.corpus import split_frontmatter  # noqa: E402

RELATIONS = ("confirma", "contradiz", "acrescenta", "supersedes")


def concept_path(name: str) -> Path:
    return paths.CONCEPTS_DIR / (slugify(name) + ".md")


def exists(name: str) -> bool:
    return concept_path(name).exists()


def create(name: str, *, stance: str, why: str, tags: list[str] | None = None) -> Path:
    """Cria a pagina com a posicao atual. Sem fonte ainda: fontes chegam depois."""
    paths.ensure_dirs()
    p = concept_path(name)
    if p.exists():
        raise FileExistsError("%s ja existe" % p)
    now = datetime.now().strftime("%Y-%m-%d")
    tags = sorted({"concept", *(t.lower() for t in (tags or []))})
    md = "\n".join([
        "---",
        "date: " + now,
        "type: concept",
        "concept: " + _yaml_str(name),
        "first-written: " + now,
        "last-revised: " + now,
        "open-contradictions: 0",
        "sources: 0",
        "tags: [" + ", ".join(tags) + "]",
        "ai-first: true",
        "---",
        "",
        "# " + name,
        "",
        "## For future Claude",
        "",
        "Pagina de conceito: o que o Kelvin sustenta hoje sobre **" + name + "**, com "
        "as fontes que sustentam ou contestam cada ponto. Diferente de uma nota de "
        "reuniao, ela e reescrita quando chega fonte nova. Leia `## Posicao atual` "
        "primeiro; `## Contradicoes em aberto` diz onde ainda nao ha resposta.",
        "",
        "## Posicao atual",
        "",
        stance.strip(),
        "",
        "## Por que",
        "",
        why.strip(),
        "",
        "## Fontes",
        "",
        "_Nenhuma fonte ligada ainda._",
        "",
        "## Contradicoes em aberto",
        "",
        "_Nenhuma._",
        "",
        "## Historico de revisao",
        "",
        "- " + now + " — pagina criada.",
        "",
    ])
    p.write_text(md, encoding="utf-8")
    return p


def propose(concept: str, *, source_slug: str, relation: str, claim: str,
            evidence: str = "", confidence: str = "medium") -> Path:
    """Grava uma proposta de revisao vinda de uma fonte. Nao toca na pagina."""
    if relation not in RELATIONS:
        raise ValueError("relation %r fora de %s" % (relation, RELATIONS))
    paths.ensure_dirs()
    now = datetime.now()
    payload = {
        "concept": concept,
        "concept_file": concept_path(concept).name,
        "source": source_slug,
        "relation": relation,
        "claim": claim,
        "evidence": evidence,
        "confidence": confidence,
        "proposed_at": now.strftime("%Y-%m-%d %H:%M"),
        "state": "proposed",
    }
    stem = "%s-%s-%s" % (now.strftime("%Y-%m-%d"), slugify(concept, 40), slugify(source_slug, 30))
    target = paths.PROPOSALS_DIR / (stem + ".json")
    n = 1
    while target.exists():
        n += 1
        target = paths.PROPOSALS_DIR / ("%s-%d.json" % (stem, n))
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def pending_proposals() -> list[dict]:
    if not paths.PROPOSALS_DIR.exists():
        return []
    out = []
    for p in sorted(paths.PROPOSALS_DIR.glob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        d["_file"] = p.name
        out.append(d)
    return out


def accept(proposal_file: str) -> Path:
    """Aplica uma proposta na pagina de conceito e arquiva o json."""
    src = paths.PROPOSALS_DIR / proposal_file
    if not src.exists():
        raise FileNotFoundError(str(src))
    d = json.loads(src.read_text(encoding="utf-8"))
    page = concept_path(d["concept"])
    if not page.exists():
        raise FileNotFoundError(
            "a pagina %s nao existe. Crie com `vaultsources concept new` antes de "
            "aceitar uma proposta para ela." % page.name)

    raw = page.read_text(encoding="utf-8")
    fm, _body, _ok = split_frontmatter(raw)
    today = datetime.now().strftime("%Y-%m-%d")
    line = "- `%s` [[Sources/%s]] — %s (confidence: %s)" % (
        d["relation"], d["source"], d["claim"], d.get("confidence", "medium"))

    raw = _append_to_section(raw, "## Fontes", line)
    if d["relation"] == "contradiz":
        raw = _append_to_section(
            raw, "## Contradicoes em aberto",
            "- %s — [[Sources/%s]] diz: %s" % (today, d["source"], d["claim"]))
    raw = _append_to_section(
        raw, "## Historico de revisao",
        "- %s — %s por [[Sources/%s]]." % (today, d["relation"], d["source"]))

    raw = _bump(raw, "last-revised", today)
    raw = _bump(raw, "sources", str(int(fm.get("sources", 0) or 0) + 1))
    if d["relation"] == "contradiz":
        raw = _bump(raw, "open-contradictions",
                    str(int(fm.get("open-contradictions", 0) or 0) + 1))
    page.write_text(raw, encoding="utf-8")

    d["state"] = "accepted"
    d["accepted_at"] = today
    src.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    src.replace(_archive(src))
    return page


def reject(proposal_file: str, *, why: str = "") -> Path:
    src = paths.PROPOSALS_DIR / proposal_file
    if not src.exists():
        raise FileNotFoundError(str(src))
    d = json.loads(src.read_text(encoding="utf-8"))
    d["state"] = "rejected"
    d["rejected_at"] = datetime.now().strftime("%Y-%m-%d")
    d["rejected_why"] = why
    paths.REJECTED_DIR.mkdir(parents=True, exist_ok=True)
    target = paths.REJECTED_DIR / src.name
    target.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    src.unlink()
    return target


def _archive(src: Path) -> Path:
    applied = paths.PROPOSALS_DIR / "_applied"
    applied.mkdir(parents=True, exist_ok=True)
    return applied / src.name


def _append_to_section(raw: str, heading: str, line: str) -> str:
    # O titulo tem de estar sozinho na linha. O bloco `For future Claude` cita
    # `## Contradicoes em aberto` no meio de uma frase, e o find() solto casava
    # com a citacao: em 2026-09-14 a primeira contradicao aceita foi parar
    # dentro daquele paragrafo, com a secao real ainda dizendo "_Nenhuma._".
    m = re.search(r"^" + re.escape(heading) + r"[ \t]*$", raw, re.M)
    if m is None:
        return raw.rstrip() + "\n\n" + heading + "\n\n" + line + "\n"
    start = raw.find("\n", m.start()) + 1
    nxt = raw.find("\n## ", start)
    end = nxt if nxt != -1 else len(raw)
    block = raw[start:end]
    block = re.sub(r"^_[^\n]*_\n", "", block.lstrip("\n"))
    block = block.rstrip() + ("\n" if block.strip() else "")
    return raw[:start] + "\n" + block + line + "\n\n" + raw[end:].lstrip("\n")


def _bump(raw: str, key: str, value: str) -> str:
    pat = re.compile(r"^" + re.escape(key) + r":.*$", re.M)
    if pat.search(raw):
        return pat.sub(key + ": " + value, raw, count=1)
    return raw.replace("\n---\n", "\n" + key + ": " + value + "\n---\n", 1)


def stats() -> dict:
    pages = ([p for p in paths.CONCEPTS_DIR.glob("*.md") if not p.name.startswith("_")]
             if paths.CONCEPTS_DIR.exists() else [])
    props = pending_proposals()
    return {
        "conceitos": len(pages),
        "propostas_abertas": sum(1 for p in props if p.get("state") == "proposed"),
        "contradicoes": sum(1 for p in props if p.get("relation") == "contradiz"),
    }
