"""vaultsources/cli.py — `python -m vaultsources <cmd>`.

Toda interacao acontece por aqui ou pelo chat. Nenhum comando deste pacote pede
que o Kelvin abra o Obsidian para marcar, ticar ou aprovar coisa nenhuma
(regra global de 2026-08-31: o vault e registro, o chat e interacao).

Comandos:

    fetch URL [--question Q]        busca uma fonte e grava a nota (analise pendente)
    clip --url --title --text-file  entra com texto que a sessao ja leu (LinkedIn)
    analyse --list | --apply FILE   lista fontes sem analise; aplica a analise em json
    watch add|rm|list               assinatura de canal e playlist do YouTube
    poll [--min-score N]            varre a watchlist e propoe candidatos
    queue [--approve ID|--reject ID] fila de candidatos
    ingest [--all|--id ID]          busca o que foi aprovado na fila
    questions [--json]              perguntas abertas que puxam conteudo
    concept new|propose|accept|reject|list
    qa [--only a,b] [--offline] [--json]   o QA de consistencia
    tester [--dry-run]              ensaio ponta a ponta com conteudo real
    status                          uma tela com o estado do cano

Exit codes: 0 ok · 1 erro · 2 QA com achado de severidade `erro`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from vaultsources import concepts, dossier, feeds, importlist, linkedin, note, paths, qa, questions

EXIT_OK, EXIT_ERROR, EXIT_QA_FAIL = 0, 1, 2


def _utf8() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _dump(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


# ── fetch / clip ──────────────────────────────────────────────────────────────

def cmd_fetch(args) -> int:
    from vaultsources import adapters
    existing = note.find_by_url(args.url)
    if existing and not args.force:
        print("ja ingerido: %s" % existing.name)
        print("use --force para regravar")
        return EXIT_OK
    doc = adapters.fetch(args.url, question=args.question or "")
    p = note.write(doc, overwrite=True, retain_raw=not args.no_raw)
    print("fonte: %s" % doc.title)
    print("autor: %s · publicado: %s · %s caracteres · %s"
          % (doc.author or "?", doc.published or "?", len(doc.text), doc.provenance))
    print("nota:  %s" % p.relative_to(paths.VAULT))
    print("analise: pendente — rode `python -m vaultsources analyse --list`")
    return EXIT_OK


def cmd_clip(args) -> int:
    from vaultsources import adapters
    text = Path(args.text_file).read_text(encoding="utf-8") if args.text_file else args.text
    doc = adapters.from_clip(url=args.url, title=args.title, text=text or "",
                             author=args.author or "", published=args.published or "",
                             question=args.question or "", kind=args.kind)
    p = note.write(doc, overwrite=True)
    print("clip gravado: %s" % p.relative_to(paths.VAULT))
    return EXIT_OK


def cmd_analyse(args) -> int:
    if args.apply:
        payload = json.loads(Path(args.apply).read_text(encoding="utf-8"))
        target = paths.SOURCES_DIR / payload["note"]
        note.complete(target, payload["analysis"])
        for imp in payload["analysis"].get("impacts", []):
            if imp.get("concept"):
                concepts.propose(imp["concept"], source_slug=target.stem,
                                 relation=imp.get("relation", "acrescenta"),
                                 claim=imp.get("note", ""),
                                 confidence=imp.get("confidence", "medium"))
        print("analise aplicada em %s" % target.name)
        return EXIT_OK
    pend = []
    for p in sorted(paths.SOURCES_DIR.glob("*.md")) if paths.SOURCES_DIR.exists() else []:
        head = p.read_text(encoding="utf-8", errors="replace")[:1200]
        if "analysis: pending" in head:
            pend.append(p)
    if not pend:
        print("nenhuma fonte esperando analise")
        return EXIT_OK
    print("%d fonte(s) sem analise:" % len(pend))
    for p in pend:
        print(" - %s" % p.name)
    return EXIT_OK


# ── watchlist / fila ──────────────────────────────────────────────────────────

def cmd_watch(args) -> int:
    if args.action == "list":
        wl = feeds.load_watchlist()
        if not wl["feeds"]:
            print("watchlist vazia")
            return EXIT_OK
        for f in wl["feeds"]:
            err = (" · ERRO: " + f["last_error"]) if f.get("last_error") else ""
            print(" - [%s] %s (%s) topicos=%s%s"
                  % (f["kind"], f["label"], f["ref"], ",".join(f["topics"]) or "-", err))
        return EXIT_OK
    if args.action == "rm":
        print("removido" if feeds.remove_feed(args.ref) else "nao estava na lista")
        return EXIT_OK
    ref = args.ref
    if ref.startswith("http"):
        ref = feeds.resolve_channel_id(ref)
        print("channel_id resolvido: %s" % ref)
    entry = feeds.add_feed(ref, label=args.label or "", topics=args.topic or [])
    print("assinado: %s (%s)" % (entry["label"], entry["kind"]))
    return EXIT_OK


def cmd_poll(args) -> int:
    qs = questions.collect()
    res = feeds.collect(questions=qs, min_score=args.min_score)
    print("feeds: %d · novos candidatos: %d · ignorados: %d"
          % (res["feeds"], len(res["added"]), res["skipped"]))
    for e in res["errors"]:
        print("  ERRO no feed %s: %s" % (e["feed"], e["error"]))
    for c in res["added"][:15]:
        print("  [%d] %s — %s" % (c["score"], c["title"][:80], c["channel"]))
        print("       %s" % c["reason"][:110])
        print("       %s" % c["url"])
    return EXIT_OK


def cmd_queue(args) -> int:
    if args.approve:
        c = feeds.set_state(args.approve, "approved")
        print("aprovado: %s" % c["title"])
        return EXIT_OK
    if args.reject:
        c = feeds.set_state(args.reject, "rejected", note=args.why or "")
        print("rejeitado: %s" % c["title"])
        return EXIT_OK
    if args.approve_feed:
        n = feeds.set_state_feed(args.approve_feed, "approved")
        print("aprovados %d candidato(s) do feed %s" % (n, args.approve_feed))
        return EXIT_OK
    if args.reject_feed:
        n = feeds.set_state_feed(args.reject_feed, "rejected", note=args.why or "")
        print("rejeitados %d candidato(s) do feed %s" % (n, args.reject_feed))
        return EXIT_OK

    grupos = feeds.pending_by_feed()
    if not grupos:
        print("fila vazia")
        return EXIT_OK
    total = sum(len(g["itens"]) for g in grupos)
    print("%d candidato(s) em %d feed(s). Decida por feed, nao item a item."
          % (total, len(grupos)))
    print("")
    for g in grupos:
        print("[%d] %s — %d item(ns)   (ref: %s)"
              % (g["score"], g["label"][:52], len(g["itens"]), g["feed"]))
        for c in g["itens"][:3]:
            print("     · %s" % (c["title"] or c["video_id"])[:88])
        if len(g["itens"]) > 3:
            print("     · … e mais %d" % (len(g["itens"]) - 3))
        print("     %s" % g["itens"][0]["reason"][:100])
    print("")
    print("Aprovar um feed inteiro: queue --approve-feed <ref>")
    print("Aprovar um item so:     queue --approve <video_id>")
    return EXIT_OK


def cmd_ingest(args) -> int:
    from vaultsources import adapters
    q = feeds.load_queue()
    targets = [c for c in q["candidates"]
               if c["state"] == "approved" and (not args.id or c["video_id"] == args.id)]
    if not targets:
        print("nada aprovado esperando ingestao")
        return EXIT_OK
    ok = 0
    for c in targets:
        try:
            doc = adapters.from_youtube(c["video_id"], question=c.get("reason", ""))
            p = note.write(doc, overwrite=True)
            feeds.set_state(c["video_id"], "ingested", note=p.name)
            print("ok: %s -> %s" % (c["title"][:60], p.name))
            ok += 1
        except Exception as exc:
            feeds.set_state(c["video_id"], "failed", note="%s: %s" % (type(exc).__name__, exc))
            print("FALHOU: %s — %s: %s" % (c["title"][:50], type(exc).__name__, str(exc)[:160]))
    print("ingeridos: %d/%d" % (ok, len(targets)))
    return EXIT_OK if ok == len(targets) else EXIT_ERROR


def cmd_import(args) -> int:
    res = importlist.import_list(Path(args.file), label=args.label,
                                 probe=args.probe, pause=args.pause)
    print("lidos: %(lidos)d · novos na fila: %(novos)d · ja no vault: %(ja_no_vault)d "
          "· sem titulo: %(sem_titulo)d" % res)
    for f in res["falhas"][:5]:
        print("  falha %s: %s" % (f["id"], f["why"]))
    if res["sem_titulo"]:
        print("Sem titulo nao da para ranquear. Rode: "
              "python -m vaultsources fill-titles --limit 25")
    return EXIT_OK


def cmd_fill_titles(args) -> int:
    res = importlist.fill_titles(limit=args.limit, pause=args.pause)
    print("titulos preenchidos: %(preenchidos)d · ainda sem: %(restantes)d" % res)
    for f in res["falhas"][:5]:
        print("  falha %s: %s" % (f["id"], f["why"]))
    return EXIT_OK


# ── perguntas / conceitos ─────────────────────────────────────────────────────

def cmd_questions(args) -> int:
    qs = questions.collect(drop_sensitive=args.external)
    if args.json:
        _dump({"summary": questions.summary(), "questions": qs[: args.limit]})
        return EXIT_OK
    s = questions.summary()
    print("perguntas abertas: %d (%d sensiveis, %d externalizaveis)"
          % (s["total"], s["sensitive"], s["externalizaveis"]))
    for q in qs[: args.limit]:
        mark = "x" if q.get("sensitive") else " "
        print(" [%s] %d %-8s %s" % (mark, q["weight"], q["kind"], q["text"][:95]))
        print("        origem: %s" % q["origin"])
    return EXIT_OK


def cmd_concept(args) -> int:
    if args.action == "new":
        p = concepts.create(args.name, stance=args.stance, why=args.why,
                            tags=args.tag or [])
        print("conceito criado: %s" % p.relative_to(paths.VAULT))
    elif args.action == "propose":
        p = concepts.propose(args.name, source_slug=args.source, relation=args.relation,
                             claim=args.claim, confidence=args.confidence)
        print("proposta gravada: %s" % p.name)
    elif args.action == "accept":
        p = concepts.accept(args.file)
        print("aplicada em %s" % p.relative_to(paths.VAULT))
    elif args.action == "reject":
        p = concepts.reject(args.file, why=args.why or "")
        print("descartada (guardada em %s)" % p.parent.name)
    else:
        st = concepts.stats()
        print("conceitos: %(conceitos)d · propostas abertas: %(propostas_abertas)d "
              "· contradicoes: %(contradicoes)d" % st)
        for pr in concepts.pending_proposals():
            if pr.get("state") != "proposed":
                continue
            print(" - [%s] %s <- %s" % (pr["relation"], pr["concept"], pr["source"]))
            print("   %s" % pr["claim"][:110])
            print("   arquivo: %s" % pr["_file"])
    return EXIT_OK


def cmd_linkedin(args) -> int:
    if args.action == "import":
        res = linkedin.import_metrics(Path(args.file) if args.file else None)
        print("importados %d post(s) de %s" % (res["posts"], res["arquivo"]))
        print("log: %s" % res["log"])
        return EXIT_OK
    cands = linkedin.candidates(days=args.days, limit=args.limit)
    if not cands:
        print("nenhum candidato na janela de %d dias" % args.days)
        return EXIT_OK
    print("%d candidato(s) a materia-prima de post (NAO sao posts prontos):" % len(cands))
    for c in cands:
        print("")
        print("[%d] %s" % (c["score"], c["pillar"]))
        print("    onde: %s" % c["where"])
        print("    %s" % c["raw"][:300])
    print("")
    print("Texto assinado como Kelvin passa pelo voice-gate antes de sair.")
    return EXIT_OK


def cmd_dossier(args) -> int:
    """Materia-prima do dossie de uma pessoa, montada so com o que ja esta escrito."""
    for nome in args.name:
        d = dossier.build(nome)
        if args.json:
            _dump(d)
        else:
            print(dossier.render(d))
            print("")
    return EXIT_OK


# ── qa / tester / status ──────────────────────────────────────────────────────

def cmd_qa(args) -> int:
    only = [x.strip() for x in args.only.split(",")] if args.only else None
    findings = qa.run(only, online=not args.offline)
    report = qa.write_report(findings)
    s = qa.summary(findings)
    if args.json:
        _dump({"summary": s, "findings": [f.as_dict() for f in findings],
               "report": str(report)})
    else:
        print("QA: %d erro(s), %d aviso(s)" % (s["erros"], s["avisos"]))
        for f in findings:
            if f.severity != qa.ERRO and not args.all:
                continue
            print(" [%s] %-12s %s" % (f.severity, f.check, f.title[:95]))
            if f.where:
                print("              onde: %s" % f.where)
            if f.fix:
                print("              conserto: %s" % f.fix)
        print("relatorio: %s" % report.relative_to(paths.VAULT))
    return EXIT_QA_FAIL if s["erros"] else EXIT_OK


def cmd_tester(args) -> int:
    from vaultsources import tester
    res = tester.run(dry_run=args.dry_run, limit=args.limit, search=args.search)
    if args.json:
        _dump(res)
        return EXIT_OK if res["falhas"] == 0 else EXIT_ERROR
    print(tester.render(res))
    return EXIT_OK if res["falhas"] == 0 else EXIT_ERROR


def cmd_status(args) -> int:
    src = ([p for p in paths.SOURCES_DIR.glob("*.md") if not p.name.startswith("_")]
           if paths.SOURCES_DIR.exists() else [])
    pend = [p for p in src if "analysis: pending"
            in p.read_text(encoding="utf-8", errors="replace")[:1200]]
    wl = feeds.load_watchlist()
    q = feeds.load_queue()
    st = concepts.stats()
    qs = questions.summary()
    print("Fontes         : %d notas (%d sem analise)" % (len(src), len(pend)))
    print("Watchlist      : %d feeds" % len(wl["feeds"]))
    print("Fila           : %d propostos, %d aprovados, %d ingeridos"
          % (sum(1 for c in q["candidates"] if c["state"] == "proposed"),
             sum(1 for c in q["candidates"] if c["state"] == "approved"),
             sum(1 for c in q["candidates"] if c["state"] == "ingested")))
    print("Conceitos      : %d paginas, %d propostas abertas"
          % (st["conceitos"], st["propostas_abertas"]))
    print("Perguntas      : %d abertas, %d podem virar busca externa"
          % (qs["total"], qs["externalizaveis"]))
    return EXIT_OK


# ── parser ────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="vaultsources", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch", help="busca uma fonte por URL")
    f.add_argument("url")
    f.add_argument("--question", default="")
    f.add_argument("--force", action="store_true")
    f.add_argument("--no-raw", action="store_true",
                   help="guarda procedencia e analise, descarta o texto bruto")
    f.set_defaults(func=cmd_fetch)

    c = sub.add_parser("clip", help="entra com texto lido no navegador")
    c.add_argument("--url", required=True)
    c.add_argument("--title", required=True)
    c.add_argument("--text", default="")
    c.add_argument("--text-file", default="")
    c.add_argument("--author", default="")
    c.add_argument("--published", default="")
    c.add_argument("--question", default="")
    c.add_argument("--kind", default="post", choices=list(note.KINDS))
    c.set_defaults(func=cmd_clip)

    a = sub.add_parser("analyse", help="fontes sem analise / aplicar analise")
    a.add_argument("--list", action="store_true")
    a.add_argument("--apply", default="")
    a.set_defaults(func=cmd_analyse)

    w = sub.add_parser("watch", help="assinatura de canal/playlist")
    w.add_argument("action", choices=["add", "rm", "list"])
    w.add_argument("ref", nargs="?", default="")
    w.add_argument("--label", default="")
    w.add_argument("--topic", action="append")
    w.set_defaults(func=cmd_watch)

    po = sub.add_parser("poll", help="varre a watchlist e propoe candidatos")
    po.add_argument("--min-score", type=int, default=1)
    po.set_defaults(func=cmd_poll)

    qu = sub.add_parser("queue", help="fila de candidatos")
    qu.add_argument("--approve", default="")
    qu.add_argument("--reject", default="")
    qu.add_argument("--approve-feed", default="")
    qu.add_argument("--reject-feed", default="")
    qu.add_argument("--why", default="")
    qu.set_defaults(func=cmd_queue)

    ing = sub.add_parser("ingest", help="busca o que foi aprovado")
    ing.add_argument("--id", default="")
    ing.add_argument("--all", action="store_true")
    ing.add_argument("--no-raw", action="store_true",
                     help="guarda procedencia e analise, descarta o texto bruto")
    ing.set_defaults(func=cmd_ingest)

    im = sub.add_parser("import", help="entra com lista de video (Takeout do Watch Later, txt de URLs)")
    im.add_argument("file")
    im.add_argument("--label", default="watch-later")
    im.add_argument("--probe", type=int, default=25, help="quantos titulos buscar agora")
    im.add_argument("--pause", type=float, default=1.0)
    im.set_defaults(func=cmd_import)

    ft = sub.add_parser("fill-titles", help="busca titulo dos candidatos importados sem titulo")
    ft.add_argument("--limit", type=int, default=25)
    ft.add_argument("--pause", type=float, default=1.0)
    ft.set_defaults(func=cmd_fill_titles)

    qn = sub.add_parser("questions", help="perguntas abertas")
    qn.add_argument("--json", action="store_true")
    qn.add_argument("--limit", type=int, default=15)
    qn.add_argument("--external", action="store_true",
                    help="so as que podem virar busca externa")
    qn.set_defaults(func=cmd_questions)

    co = sub.add_parser("concept", help="camada de conceito")
    co.add_argument("action", choices=["new", "propose", "accept", "reject", "list"],
                    nargs="?", default="list")
    co.add_argument("--name", default="")
    co.add_argument("--stance", default="")
    co.add_argument("--why", default="")
    co.add_argument("--tag", action="append")
    co.add_argument("--source", default="")
    co.add_argument("--relation", default="acrescenta", choices=list(concepts.RELATIONS))
    co.add_argument("--claim", default="")
    co.add_argument("--confidence", default="medium")
    co.add_argument("--file", default="")
    co.set_defaults(func=cmd_concept)

    qa_p = sub.add_parser("qa", help="QA de consistencia")
    qa_p.add_argument("--only", default="")
    qa_p.add_argument("--offline", action="store_true")
    qa_p.add_argument("--json", action="store_true")
    qa_p.add_argument("--all", action="store_true", help="mostra tambem os avisos")
    qa_p.set_defaults(func=cmd_qa)

    t = sub.add_parser("tester", help="ensaio ponta a ponta com conteudo real")
    t.add_argument("--dry-run", action="store_true")
    t.add_argument("--limit", type=int, default=2)
    t.add_argument("--search", default="")
    t.add_argument("--json", action="store_true")
    t.set_defaults(func=cmd_tester)

    li = sub.add_parser("linkedin", help="metricas e materia-prima de post")
    li.add_argument("action", choices=["import", "candidates"], nargs="?",
                    default="candidates")
    li.add_argument("--file", default="", help="xlsx do export; vazio = mais recente em Downloads")
    li.add_argument("--days", type=int, default=21)
    li.add_argument("--limit", type=int, default=6)
    li.set_defaults(func=cmd_linkedin)

    do = sub.add_parser("dossier", help="dossie de uma pessoa antes da reuniao")
    do.add_argument("name", nargs="+")
    do.add_argument("--json", action="store_true")
    do.set_defaults(func=cmd_dossier)

    s = sub.add_parser("status", help="estado do cano")
    s.set_defaults(func=cmd_status)
    return p


def main(argv=None) -> int:
    _utf8()
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return EXIT_ERROR
    except Exception as exc:
        print("ERRO: %s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        return EXIT_ERROR
