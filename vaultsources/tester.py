"""vaultsources/tester.py — o ensaio ponta a ponta com conteudo real.

Diferenca deliberada para os testes de `tests/`: aqueles rodam offline, com fixture,
e provam que o codigo faz o que o codigo diz. Este sai na rede, pega material que
existe de verdade e prova que **o processo inteiro entrega**, incluindo as partes
que nenhum unittest cobre: a CA da rede corporativa, a legenda que o YouTube
resolve devolver hoje, o yt-dlp que mudou de versao, o disco onde a nota cai.

O que ele faz de util para o Kelvin, alem de testar: ele **vai buscar**. Quando a
watchlist ainda esta vazia, o tester le as perguntas abertas do sistema (ledger,
backlog, conceitos fracos de estudo, riscos de OKR), transforma as mais pesadas em
busca no YouTube e traz candidatos reais. Isso e o "tester pegando coisas por mim"
do pedido de 2026-09-10: o primeiro conteudo do cano nao precisa ser digitado.

Estagios, em ordem, cada um com veredito proprio:

    deps        as pecas do cano existem e a rede valida
    questions   ha pergunta aberta para puxar conteudo
    discover    achou material real (watchlist ou busca por pergunta)
    fetch       a fonte virou nota com procedencia
    roundtrip   a nota relida bate byte a byte com o que foi gravado
    concept     proposta de conceito nasce, aparece na fila e sai sem sujeira
    governance  payload do vault e recusado por provedor externo
    qa          o QA nao acusa erro nas notas recem-criadas

`--dry-run` roda tudo o que nao escreve, e diz o que teria escrito.
"""

from __future__ import annotations

import time
import traceback
from datetime import datetime
from pathlib import Path

from vaultsources import concepts, feeds, governance, note, paths, qa, questions

STAGES = ("deps", "questions", "discover", "fetch", "roundtrip",
          "concept", "governance", "qa")


class Stage:
    def __init__(self, name: str):
        self.name = name
        self.ok: bool | None = None
        self.detail = ""
        self.data: dict = {}
        self.seconds = 0.0
        self.error = ""

    def as_dict(self) -> dict:
        return {"stage": self.name, "ok": self.ok, "detail": self.detail,
                "data": self.data, "seconds": round(self.seconds, 1),
                "error": self.error}


def _run_stage(name: str, fn, out: list[Stage]) -> Stage:
    s = Stage(name)
    t0 = time.time()
    try:
        fn(s)
        if s.ok is None:
            s.ok = True
    except Exception as exc:
        s.ok = False
        s.error = "%s: %s" % (type(exc).__name__, str(exc)[:300])
        s.detail = s.detail or "estagio abortou"
        s.data["traceback"] = traceback.format_exc()[-1200:]
    s.seconds = time.time() - t0
    out.append(s)
    return s


def run(*, dry_run: bool = False, limit: int = 2, search: str = "") -> dict:
    stages: list[Stage] = []
    ctx: dict = {"dry_run": dry_run, "limit": limit, "created": []}

    # 1. deps
    def _deps(s: Stage) -> None:
        f = qa.check_deps(online=True)
        erros = [x for x in f if x.severity == qa.ERRO]
        s.ok = not erros
        s.data["achados"] = [x.as_dict() for x in f]
        s.detail = ("cano completo e rede validando" if s.ok
                    else "; ".join(x.title for x in erros))
    _run_stage("deps", _deps, stages)

    # 2. questions
    def _questions(s: Stage) -> None:
        qs = questions.as_search_queries(limit=8)
        ctx["questions"] = qs
        s.ok = bool(qs)
        s.data["summary"] = questions.summary()
        s.detail = ("%d pergunta(s) externalizavel(is); a mais pesada: %s"
                    % (len(qs), qs[0]["text"][:80]) if qs
                    else "nenhuma pergunta aberta nao sensivel: o cano nao tem o que puxar")
    _run_stage("questions", _questions, stages)

    # 3. discover
    def _discover(s: Stage) -> None:
        from vaultsources import adapters
        found: list[dict] = []
        wl = feeds.load_watchlist()
        if wl["feeds"]:
            res = feeds.collect(questions=questions.collect(), min_score=1)
            found += res["added"]
            s.data["watchlist"] = {"feeds": res["feeds"], "novos": len(res["added"]),
                                   "erros": res["errors"]}
        if len(found) < limit:
            queries = [search] if search else [q["text"] for q in ctx.get("questions", [])[:3]]
            s.data["buscas"] = queries
            for q in queries:
                if len(found) >= limit + 2:
                    break
                try:
                    hits = adapters.search_youtube(q, n=3)
                except Exception as exc:
                    s.data.setdefault("falhas_busca", []).append("%s: %s" % (q[:40], exc))
                    continue
                for h in hits:
                    h["reason"] = "busca a partir da pergunta aberta: %s" % q[:100]
                    if not any(f.get("video_id") == h["video_id"] for f in found):
                        found.append(h)
        ctx["candidates"] = found
        s.ok = bool(found)
        s.detail = ("%d candidato(s) real(is)" % len(found) if found
                    else "nenhum candidato encontrado")
        s.data["candidatos"] = [{"id": c["video_id"], "title": c["title"],
                                 "channel": c.get("channel", ""),
                                 "reason": c.get("reason", "")} for c in found[:8]]
    _run_stage("discover", _discover, stages)

    # 4. fetch
    def _fetch(s: Stage) -> None:
        from vaultsources import adapters
        cands = ctx.get("candidates", [])[:limit]
        if not cands:
            s.ok = False
            s.detail = "nada para buscar"
            return
        if dry_run:
            s.ok = True
            s.detail = "dry-run: buscaria %d fonte(s)" % len(cands)
            s.data["would_fetch"] = [c["video_id"] for c in cands]
            return
        ok, fails = [], []
        for c in cands:
            try:
                doc = adapters.from_youtube(c["video_id"], question=c.get("reason", ""))
                if len(doc.text) < 200:
                    fails.append({"id": c["video_id"], "why": "texto curto demais (%d chars): "
                                  "provavelmente sem legenda util" % len(doc.text)})
                    continue
                p = note.write(doc, overwrite=True)
                ctx["created"].append(p)
                ok.append({"id": c["video_id"], "note": p.name, "chars": len(doc.text),
                           "provenance": doc.provenance, "title": doc.title})
            except Exception as exc:
                fails.append({"id": c["video_id"], "why": "%s: %s"
                              % (type(exc).__name__, str(exc)[:200])})
        ctx["fetched"] = ok
        s.ok = bool(ok)
        s.data = {"ok": ok, "falhas": fails}
        s.detail = "%d fonte(s) gravada(s), %d falha(s)" % (len(ok), len(fails))
    _run_stage("fetch", _fetch, stages)

    # 5. roundtrip
    def _roundtrip(s: Stage) -> None:
        created = ctx.get("created", [])
        if dry_run or not created:
            s.ok = True
            s.detail = "sem nota nova para reler"
            return
        bad = []
        for p in created:
            doc = note.read_doc(p)
            head = p.read_text(encoding="utf-8", errors="replace")[:1500]
            declared = ""
            for line in head.splitlines():
                if line.startswith("text-sha256:"):
                    declared = line.split(":", 1)[1].strip()
            if doc.text_sha256 != declared:
                bad.append({"note": p.name, "lido": doc.text_sha256[:12],
                            "declarado": declared[:12]})
        s.ok = not bad
        s.data["divergencias"] = bad
        s.detail = ("procedencia integra em %d nota(s)" % len(created) if s.ok
                    else "%d nota(s) com hash divergente" % len(bad))
    _run_stage("roundtrip", _roundtrip, stages)

    # 6. concept
    def _concept(s: Stage) -> None:
        fetched = ctx.get("fetched", [])
        if dry_run or not fetched:
            s.ok = True
            s.detail = "sem fonte nova para propor conceito"
            return
        name = "Ensaio do cano de fontes"
        page = concepts.concept_path(name)
        created_page = False
        if not page.exists():
            concepts.create(name, stance="Pagina de ensaio criada pelo tester.",
                            why="Existe para provar que proposta nasce e sai sem "
                                "sujeira. Pode ser apagada.", tags=["ensaio"])
            created_page = True
        prop = concepts.propose(name, source_slug=Path(fetched[0]["note"]).stem,
                                relation="acrescenta",
                                claim="Ensaio automatico do tester.",
                                confidence="speculation")
        listed = any(p["_file"] == prop.name for p in concepts.pending_proposals())
        concepts.reject(prop.name, why="ensaio do tester")
        gone = not any(p["_file"] == prop.name for p in concepts.pending_proposals())
        kept = (paths.REJECTED_DIR / prop.name).exists()
        if created_page:
            page.unlink(missing_ok=True)
        (paths.REJECTED_DIR / prop.name).unlink(missing_ok=True)
        s.ok = listed and gone and kept
        s.detail = ("proposta nasceu, apareceu na fila, saiu e ficou guardada"
                    if s.ok else "o ciclo de proposta nao fechou")
        s.data = {"apareceu": listed, "saiu_da_fila": gone, "foi_guardada": kept}
    _run_stage("concept", _concept, stages)

    # 7. governance
    def _governance(s: Stage) -> None:
        casos = [("research-web", "vault", True), ("x-read", "vault", True),
                 ("research-web", "user", False), ("transcript-fetch", "public", False)]
        falhas = []
        for purpose, origin, deve_barrar in casos:
            try:
                governance.check_egress(purpose, origin)
                barrou = False
            except governance.EgressDenied:
                barrou = True
            if barrou != deve_barrar:
                falhas.append("%s/%s: esperado barrar=%s" % (purpose, origin, deve_barrar))
        leak = [q for q in questions.as_search_queries(50) if q.get("sensitive")]
        if leak:
            falhas.append("%d pergunta(s) sensivel(is) na fila externa" % len(leak))
        s.ok = not falhas
        s.data["falhas"] = falhas
        s.detail = ("a fronteira segura: vault nao sai para provedor externo"
                    if s.ok else "; ".join(falhas))
    _run_stage("governance", _governance, stages)

    # 8. qa
    def _qa(s: Stage) -> None:
        f = qa.run(["notes", "governance"], online=False)
        erros = [x for x in f if x.severity == qa.ERRO]
        s.ok = not erros
        s.data["achados"] = [x.as_dict() for x in f]
        s.detail = ("QA limpo nas notas" if s.ok
                    else "; ".join(x.title for x in erros[:4]))
    _run_stage("qa", _qa, stages)

    falhas = sum(1 for s in stages if s.ok is False)
    return {
        "quando": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "dry_run": dry_run,
        "estagios": [s.as_dict() for s in stages],
        "falhas": falhas,
        "notas_criadas": [p.name for p in ctx.get("created", [])],
        "veredito": "passou" if falhas == 0 else "%d estagio(s) falhou(aram)" % falhas,
    }


def render(res: dict) -> str:
    lines = ["Tester do cano de fontes · %s%s"
             % (res["quando"], "  (dry-run)" if res["dry_run"] else ""), ""]
    for s in res["estagios"]:
        mark = "ok  " if s["ok"] else "FALHA"
        lines.append("%-5s %-11s %5.1fs  %s" % (mark, s["stage"], s["seconds"], s["detail"]))
        if s["error"]:
            lines.append("                        %s" % s["error"])
    lines.append("")
    if res["notas_criadas"]:
        lines.append("Notas criadas:")
        for n in res["notas_criadas"]:
            lines.append("  - %s" % n)
        lines.append("")
    lines.append("Veredito: %s" % res["veredito"])
    return "\n".join(lines)
