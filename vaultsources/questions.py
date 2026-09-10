"""vaultsources/questions.py — as perguntas abertas que puxam conteudo para dentro.

O que apodrece qualquer pilha de "ler depois" e ingerir sem uma pergunta esperando
resposta. Este modulo nao inventa pergunta: le as que ja existem no sistema e as
poe em um formato unico, para o `feeds.score` decidir o que vale propor e para a
nota de fonte gravar em `pulled-by-question` de onde veio o interesse.

Fontes (todas ja existiam antes de 2026-09-10, nenhuma criada para isto):

    ledger      agent/pending.py — o que espera decisao do Kelvin
    backlog     BacklogStore — ideias em analise
    estudo      vault/study-tools/<area>/*-weak-concepts.json — conceito fraco e
                pergunta aberta com prazo de prova
    okr         Areas/OKR 2027/*/charter.md — risco declarado

Nao le `Team/` nem `Stakeholders/`. Pergunta que sai daqui vira query de busca
externa, e dado de pessoa nao sai da maquina (ADR 2026-08-29).
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

from vaultsources import paths

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

SENSITIVE_DIRS = ("Team", "Stakeholders", "Areas/Performance", "Areas/Career")

STUDY_ROOT = paths.VAULT / "vault" / "study-tools"
OKR_ROOT = paths.VAULT / "Areas" / "OKR 2027"


def _q(text: str, origin: str, kind: str, weight: int = 1, ref: str = "") -> dict:
    return {"text": " ".join(text.split())[:300], "origin": origin,
            "kind": kind, "weight": weight, "ref": ref}


def from_ledger() -> list[dict]:
    try:
        from agent import pending
    except Exception:
        return []
    try:
        data = pending._load()
    except Exception:
        return []
    out = []
    for item in data.get("itens", []):
        if item.get("resolvida_em"):
            continue
        peso = {"alta": 3, "media": 2, "baixa": 1}.get(item.get("prioridade", "media"), 2)
        out.append(_q(item.get("texto", ""), "ledger %s" % item.get("id", ""),
                      "decisao", peso, item.get("ref", "") or ""))
    return out


def from_backlog() -> list[dict]:
    try:
        from backlog.store import BacklogStore  # type: ignore
        store = BacklogStore()
        items = store.load_all()
    except Exception:
        return _backlog_from_disk()
    out = []
    for it in items:
        status = str(getattr(it, "status", "") or "")
        if status not in ("em análise", "em analise", "backlog"):
            continue
        titulo = str(getattr(it, "titulo", "") or "")
        out.append(_q(titulo, "backlog %s" % getattr(it, "id", ""), "ideia", 2))
    return out


def _backlog_from_disk() -> list[dict]:
    try:
        from config import BACKLOG_DIR
    except Exception:
        return []
    out = []
    for p in sorted(Path(BACKLOG_DIR).glob("idea-*.md"))[-80:]:
        try:
            head = p.read_text(encoding="utf-8", errors="replace")[:1200]
        except OSError:
            continue
        st = re.search(r"^status:\s*(.+)$", head, re.M)
        ti = re.search(r"^titulo:\s*(.+)$", head, re.M)
        if not st or not ti:
            continue
        if st.group(1).strip().strip('"') not in ("em análise", "em analise", "backlog"):
            continue
        out.append(_q(ti.group(1).strip().strip('"'), "backlog %s" % p.stem, "ideia", 2))
    return out


def from_study() -> list[dict]:
    out = []
    if not STUDY_ROOT.exists():
        return out
    for weak in STUDY_ROOT.glob("*/*-weak-concepts.json"):
        area = weak.parent.name
        try:
            data = json.loads(weak.read_text(encoding="utf-8"))
        except Exception:
            continue
        scores = data.get("concept_scores") or {}
        for concept, st in scores.items():
            attempted = int(st.get("attempted", 0) or 0)
            correct = int(st.get("correct", 0) or 0)
            if attempted == 0 or correct >= attempted:
                continue  # so entra conceito que ele ja errou
            miss = attempted - correct
            out.append(_q(concept, "estudo %s" % area, "estudo", min(3, 1 + miss),
                          str(weak.relative_to(paths.VAULT))))
    out.sort(key=lambda q: -q["weight"])
    return out[:40]


_RISK_HEADING = re.compile(r"^#{2,4}\s*[\d.]*\s*.*?(riscos?|risks?)\b.*$", re.I | re.M)


def from_okr() -> list[dict]:
    """Bullets sob a secao de riscos de cada charter de OKR.

    O formato real nao e `- Risco: ...`; e uma secao `## 8. Dependencias e riscos`
    com bullets soltos embaixo. Casar o rotulo em vez da secao devolvia zero e
    parecia "nao ha risco declarado", que e a mentira mais cara deste arquivo.
    """
    out = []
    if not OKR_ROOT.exists():
        return out
    for charter in sorted(OKR_ROOT.glob("*/charter.md")):
        if "CONFIDENCIAL" in charter.parent.name.upper():
            continue
        try:
            text = charter.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        m = _RISK_HEADING.search(text)
        if not m:
            continue
        rest = text[m.end():]
        nxt = re.search(r"^#{2,4}\s", rest, re.M)
        block = rest[: nxt.start()] if nxt else rest
        for line in re.findall(r"^\s*[-*]\s+(.{20,})$", block, re.M):
            clean = re.sub(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", r"\1", line)
            clean = re.sub(r"[*_`]", "", clean)
            out.append(_q(clean, "okr %s" % charter.parent.name, "risco", 2,
                          str(charter.relative_to(paths.VAULT))))
    return out[:30]


_PEOPLE_CACHE: list[str] | None = None


def known_people() -> list[str]:
    """Nomes de pessoa que o vault conhece, montados das pastas Team/ e Stakeholders/.

    Filtrar so por caminho nao bastava: uma pendencia do ledger tem `ref` vazio e o
    texto "Revisar Overview proposto para Stefan-Lautenschlager". Por caminho ela
    passava limpa, e viraria query numa busca externa. Nome de colega da NETZSCH
    nao sai desta maquina.
    """
    global _PEOPLE_CACHE
    if _PEOPLE_CACHE is not None:
        return _PEOPLE_CACHE
    names: set[str] = set()
    for folder in ("Team", "Stakeholders"):
        base = paths.VAULT / folder
        if not base.exists():
            continue
        for d in base.iterdir():
            if not d.is_dir() or d.name.startswith(("_", ".")):
                continue
            raw = d.name.replace("-", " ").strip()
            if len(raw.split()) < 1 or raw.lower() in ("1on1", "peers", "key stakeholders"):
                continue
            names.add(raw.lower())
            for part in raw.split():
                if len(part) > 3:
                    names.add(part.lower())
    _PEOPLE_CACHE = sorted(names)
    return _PEOPLE_CACHE


def is_sensitive(q: dict) -> tuple[bool, str]:
    ref = (q.get("ref", "") or "").replace("\\", "/")
    for d in SENSITIVE_DIRS:
        if ref.startswith(d):
            return True, "vem de %s" % d
    hay = " " + re.sub(r"[^a-z0-9]+", " ", (q.get("text", "") or "").lower()) + " "
    for name in known_people():
        if (" " + name + " ") in hay:
            return True, "cita pessoa conhecida do vault"
    return False, ""


def collect(kinds: tuple[str, ...] = ("decisao", "ideia", "estudo", "risco"),
            *, drop_sensitive: bool = False) -> list[dict]:
    """Todas as perguntas abertas, cada uma marcada como sensivel ou nao."""
    everything = from_ledger() + from_backlog() + from_study() + from_okr()
    out = []
    for q in everything:
        if q["kind"] not in kinds:
            continue
        flag, why = is_sensitive(q)
        q["sensitive"] = flag
        q["sensitive_why"] = why
        if flag and drop_sensitive:
            continue
        out.append(q)
    out.sort(key=lambda q: -q["weight"])
    return out


def as_search_queries(limit: int = 5) -> list[dict]:
    """As perguntas mais pesadas que podem virar busca externa.

    So entram as nao sensiveis. Quem manda para fora ainda declara `origin="user"`
    no `governance.check_egress`: o que viaja e a pergunta, nunca o contexto do vault.
    """
    return collect(drop_sensitive=True)[:limit]


def summary() -> dict:
    qs = collect()
    by_kind: dict[str, int] = {}
    for q in qs:
        by_kind[q["kind"]] = by_kind.get(q["kind"], 0) + 1
    sens = sum(1 for q in qs if q.get("sensitive"))
    return {"total": len(qs), "by_kind": by_kind, "sensitive": sens,
            "externalizaveis": len(qs) - sens,
            "generated": datetime.now().strftime("%Y-%m-%d %H:%M")}
