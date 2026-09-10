"""vaultsources/brief.py — o momento de USAR o que entrou.

Todo o resto do pacote traz conhecimento para dentro. Isto e o unico ponto que
tira. Existe porque em 2026-09-10, no fim do dia em que o cano ficou pronto, o
estado era: 15 fontes, 13 sem analise, 2 conceitos, zero contradicoes abertas.
Trazer nao e usar, e uma pasta que so enche vira a pilha de "ler depois" que o
cano existia para evitar.

`brief <tema>` responde uma pergunta e so ela: **antes de escrever ou decidir
sobre este assunto, o que eu ja sustento, o que sustenta isso, e onde ha
divergencia.** Nesta ordem, porque a posicao vem antes da fonte: fonte sem posicao
e leitura, posicao sem fonte e opiniao.

Le o indice local (`vaultindex`), sem LLM e sem rede. Nao inclui `Team/` nem
`Stakeholders/`: quem quer dossie de pessoa usa `vaultsources dossier`, que tem
outra regra.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from vaultsources import paths

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from vaultindex.corpus import split_frontmatter  # noqa: E402


def _section(text: str, head: str) -> str:
    """Corpo de uma secao, casando o TITULO no inicio da linha.

    `find(head)` casava a primeira mencao ao titulo em texto corrido: o preambulo
    das paginas de conceito diz "Leia `## Posicao atual` primeiro", e era essa
    ocorrencia que ganhava. O brief saia com a posicao vazia em toda pagina.
    Mesma classe de defeito do gate que casava por substring em prosa.
    """
    m = re.search(r"^" + re.escape(head) + r"\s*$", text, re.M)
    if not m:
        return ""
    start = m.end()
    nxt = re.search(r"^## ", text[start:], re.M)
    body = text[start: start + nxt.start() if nxt else len(text)].strip()
    return re.sub(r"\n{2,}", "\n", body)


def concepts_for(tema: str, k: int = 4) -> list[dict]:
    from vaultindex.search import search
    out = []
    try:
        res = search(tema, k=k * 3, types=["concept"], root=paths.VAULT)
    except Exception:
        res = {"results": []}
    for r in res.get("results", [])[:k]:
        p = paths.VAULT / str(r.get("path", "")).replace("/", "\\")
        if not p.exists():
            continue
        raw = p.read_text(encoding="utf-8", errors="replace")
        fm, _b, _ok = split_frontmatter(raw)
        out.append({
            "file": str(p.relative_to(paths.VAULT)),
            "concept": str(fm.get("concept", p.stem)),
            "last_revised": str(fm.get("last-revised", "")),
            "sources": fm.get("sources", 0),
            "open_contradictions": fm.get("open-contradictions", 0),
            "position": _section(raw, "## Posicao atual")[:600],
            "contradictions": _section(raw, "## Contradicoes em aberto")[:600],
        })
    return out


def _read_source(p: Path) -> dict | None:
    if not p.exists():
        return None
    raw = p.read_text(encoding="utf-8", errors="replace")
    fm, _b, _ok = split_frontmatter(raw)
    tese = _section(raw, "## Tese central")
    return {
        "file": str(p.relative_to(paths.VAULT)).replace("\\", "/"),
        "title": str(fm.get("source-title", p.stem)),
        "author": str(fm.get("source-author", "") or ""),
        "published": str(fm.get("source-published", "")),
        "provenance": str(fm.get("provenance", "")),
        "analysis": str(fm.get("analysis", "pending")),
        "thesis": "" if "pending-analysis" in tese else tese[:400],
    }


def sources_linked_from(conceitos: list[dict]) -> list[dict]:
    """Fontes que as paginas de conceito JA citam, por link.

    Vem antes da busca de proposito. O link e estrutural: alguem aprovou aquela
    fonte para aquele conceito. A busca depende de o indice estar fresco e de a
    pergunta estar no mesmo idioma do titulo — "governanca de dados" devolvia zero
    para uma fonte chamada "Data Governance Explained". Estrutura nao tem esse
    problema.
    """
    out, vistos = [], set()
    for c in conceitos:
        p = paths.VAULT / c["file"]
        if not p.exists():
            continue
        raw = p.read_text(encoding="utf-8", errors="replace")
        for slug in re.findall(r"\[\[Sources/([^\]|]+)\]\]", raw):
            if slug in vistos:
                continue
            vistos.add(slug)
            d = _read_source(paths.SOURCES_DIR / (slug.split("/")[-1] + ".md"))
            if d:
                out.append(d)
    return out


def sources_for(tema: str, k: int = 6) -> list[dict]:
    from vaultindex.search import search
    out, vistos = [], set()
    try:
        res = search(tema, k=k * 4, types=["source"], root=paths.VAULT)
    except Exception:
        res = {"results": []}
    for r in res.get("results", []):
        rel = str(r.get("path", ""))
        p = paths.VAULT / rel.replace("/", "\\")
        if not p.exists() or p.stem in vistos:
            continue
        vistos.add(p.stem)
        raw = p.read_text(encoding="utf-8", errors="replace")
        fm, _b, _ok = split_frontmatter(raw)
        tese = _section(raw, "## Tese central")
        out.append({
            "file": rel,
            "title": str(fm.get("source-title", p.stem)),
            "author": str(fm.get("source-author", "") or ""),
            "published": str(fm.get("source-published", "")),
            "provenance": str(fm.get("provenance", "")),
            "analysis": str(fm.get("analysis", "pending")),
            "thesis": "" if "pending-analysis" in tese else tese[:400],
        })
        if len(out) >= k:
            break
    return out


def questions_for(tema: str, k: int = 5) -> list[dict]:
    from vaultsources import questions
    termos = {t for t in re.findall(r"[a-zA-Zà-üÀ-Ü0-9]{4,}", tema.lower())}
    out = []
    for q in questions.collect():
        hay = q["text"].lower()
        if any(t in hay for t in termos):
            out.append(q)
        if len(out) >= k:
            break
    return out


def build(tema: str) -> dict:
    cs = concepts_for(tema)
    fontes = sources_linked_from(cs)
    vistos = {f["file"] for f in fontes}
    for f in sources_for(tema):
        if f["file"] not in vistos:
            fontes.append(f)
            vistos.add(f["file"])
    return {"tema": tema, "conceitos": cs, "fontes": fontes,
            "perguntas": questions_for(tema)}


def render(b: dict) -> str:
    L = ["# %s" % b["tema"], ""]
    cs = b["conceitos"]
    if cs:
        L.append("## O que voce ja sustenta")
        for c in cs:
            L += ["", "**%s** (revisado %s · %s fonte(s) · %s contradicao(oes))"
                  % (c["concept"], c["last_revised"] or "?", c["sources"],
                     c["open_contradictions"])]
            if c["position"]:
                L.append(c["position"])
            if c["contradictions"] and "Nenhuma" not in c["contradictions"]:
                L += ["", "_Em aberto:_ " + c["contradictions"]]
    else:
        L += ["## O que voce ja sustenta", "",
              "Nenhuma pagina de conceito sobre isto. Se o assunto e recorrente, "
              "vale abrir uma: `vaultsources concept new --name \"...\"`."]
    L += ["", "## O que sustenta ou contesta"]
    fs = b["fontes"]
    if not fs:
        L += ["", "Nenhuma fonte externa sobre isto no vault."]
    for f in fs:
        marca = "" if f["analysis"] != "pending" else "  [sem analise]"
        L += ["", "- **%s** — %s, %s · `%s`%s"
              % (f["title"][:90], f["author"] or "autor nao informado",
                 f["published"], f["provenance"], marca)]
        if f["thesis"]:
            L.append("  " + f["thesis"].replace("\n", " ")[:280])
    qs = b["perguntas"]
    if qs:
        L += ["", "## Perguntas suas em aberto sobre isto"]
        for q in qs:
            L.append("- (%s) %s" % (q["kind"], q["text"][:130]))
    return "\n".join(L)
