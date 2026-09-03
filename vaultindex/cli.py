"""
vaultindex/cli.py — `python -m vaultindex build | embed | search | check | stats | bench | briefing | lint`.

Exit codes: 0 ok · 1 error · 2 index missing (run build) · 3 another build holds the
lock · `check` exits 1 when the index disagrees with the vault.

`--corpus memory` points root and index at the Claude Code memory directory (a second,
separate index); everything else is the same code.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from vaultindex.db import IndexLocked, IndexMissing, SchemaMismatch, build, check, stats
from vaultindex.search import search

EXIT_OK, EXIT_ERROR, EXIT_MISSING, EXIT_LOCKED = 0, 1, 2, 3


def _utf8_stdout() -> None:
    # Windows consoles default to cp1252; the vault is full of accents and arrows.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _dump(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


def _fmt_age(seconds: int | None) -> str:
    if seconds is None:
        return "idade desconhecida"
    if seconds < 90:
        return f"{seconds}s"
    if seconds < 5400:
        return f"{seconds // 60} min"
    if seconds < 172800:
        return f"{seconds // 3600} h"
    return f"{seconds // 86400} d"


def memory_corpus() -> tuple[Path, Path]:
    """Root and index dir for the Claude Code memory corpus (second index, same code)."""
    from config import VAULT_INDEX_DIR

    project = re.sub(r"[^A-Za-z0-9]", "-", str(Path.home()))
    root = Path.home() / ".claude" / "projects" / project / "memory"
    return root, Path(VAULT_INDEX_DIR).parent / "memory-index"


def _resolve_corpus(args) -> None:
    if getattr(args, "corpus", "vault") == "memory":
        root, index_dir = memory_corpus()
        args.root = args.root or root
        args.index_dir = args.index_dir or index_dir


def _progress(done: int, total: int) -> None:
    print(f"\r  embeddings {done}/{total}", end="", file=sys.stderr, flush=True)
    if done >= total:
        print(file=sys.stderr)


def cmd_build(args) -> int:
    rep = build(root=args.root, index_dir=args.index_dir, full=args.full, embed=args.embed, model=args.model, progress=None if args.json else _progress)
    if args.json:
        _dump(rep.to_dict())
    else:
        print(
            f"build {'completo' if rep.full else 'incremental'} em {rep.seconds}s: "
            f"{rep.scanned} lidos · +{rep.added} novos · ~{rep.updated} alterados · "
            f"={rep.unchanged} iguais · -{rep.removed} removidos"
        )
        print(
            f"índice: {rep.notes} notas · {rep.chunks} chunks · {rep.links_resolved}/{rep.links} links resolvidos · "
            f"{rep.sensitive_notes} sensíveis · {rep.no_frontmatter} sem frontmatter"
        )
        print(
            f"embeddings: modelo {rep.embedding_model or '(nenhum)'} · {rep.embedded} gerados agora · "
            f"{rep.embeddings_stale_chunks} chunks ainda sem vetor"
        )
        for w in rep.warnings:
            print(f"AVISO {w}")
        print(f"em {rep.index_dir}")
    return EXIT_OK


def cmd_embed(args) -> int:
    from vaultindex.db import IndexWriter
    from vaultindex.embed import DEFAULT_MODEL, embed_missing

    model = args.model or DEFAULT_MODEL
    with IndexWriter(args.index_dir) as w:
        if args.force:
            w.con.execute("DELETE FROM embeddings WHERE model = ?", (model,))
            w.con.commit()
        n = embed_missing(w.con, model, index_dir=args.index_dir, batch_size=args.batch, progress=None if args.json else _progress, activate=not args.no_activate)
        total = w.con.execute("SELECT count(*) FROM embeddings WHERE model = ?", (model,)).fetchone()[0]
    out = {"model": model, "embedded_now": n, "total_for_model": total, "active": not args.no_activate}
    if args.json:
        _dump(out)
    else:
        print(f"{model}: {n} chunks embutidos agora, {total} no total" + ("" if args.no_activate else " · modelo ativo para a busca"))
    return EXIT_OK


def cmd_search(args) -> int:
    streams = tuple(s.strip() for s in args.streams.split(",") if s.strip())
    out = search(
        " ".join(args.query),
        k=args.k,
        include_sensitive=args.sensitive,
        types=args.type or None,
        folder=args.folder,
        since=args.since,
        until=args.until,
        as_of=args.as_of,
        refresh=not args.no_refresh,
        root=args.root,
        index_dir=args.index_dir,
        streams=streams,
        model=args.model,
        neighbours=not args.no_neighbours,
    )
    if args.json:
        _dump(out)
        return EXIT_OK
    head = f"[{out['mode']}] índice de há {_fmt_age(out['index_age_seconds'])}"
    if out.get("model"):
        head += f" · {out['model']}"
    if out.get("refreshed"):
        head += f" · refresh: {out['refreshed']}"
    if out["excluded_sensitive_hits"]:
        head += f" · {out['excluded_sensitive_hits']} nota(s) sensível(is) fora (use --sensitive)"
    if out.get("embeddings_stale_chunks"):
        head += f" · {out['embeddings_stale_chunks']} chunks sem vetor"
    print(head)
    if out.get("note"):
        print(f"nota: {out['note']}")
    if not out["results"]:
        print("nenhum resultado")
        return EXIT_OK
    for r in out["results"]:
        flag = " ⚠" if r["sensitive"] else ""
        why = "+".join(r["why"])
        extra = f" · sim {r['vec_sim']}" if "vec_sim" in r else ""
        changed = ""
        if "changed_since_as_of" in r:
            changed = " · mudou depois" if r["changed_since_as_of"] else (" · sem mudança" if r["changed_since_as_of"] is False else "")
        print(f"\n{r['rank']:>2}. {r['title']}{flag}  [{r['type'] or 'sem type'} · {r['date'] or '?'} · {why}{extra}{changed}]  {r['path']}")
        for s in r["snippets"][:1]:
            text = " ".join(s["text"].split())
            print(f"    {('§ ' + s['heading'] + ': ') if s['heading'] else ''}{text}")
    return EXIT_OK


def cmd_check(args) -> int:
    rep = check(root=args.root, index_dir=args.index_dir)
    if args.json:
        _dump(rep.to_dict())
    elif rep.ok:
        print(f"ok: índice bate com o vault ({rep.corpus_files} arquivos)")
    else:
        print(
            f"DIVERGE: {len(rep.changed)} alterados · {len(rep.missing_in_index)} fora do índice · "
            f"{len(rep.extra_in_index)} só no índice"
        )
        for label, items in (("alterado", rep.changed), ("falta", rep.missing_in_index), ("sobra", rep.extra_in_index)):
            for p in items[:20]:
                print(f"  {label}: {p}")
        print("rode: python -m vaultindex build")
    return EXIT_OK if rep.ok else EXIT_ERROR


def cmd_stats(args) -> int:
    _dump(stats(index_dir=args.index_dir))
    return EXIT_OK


def cmd_bench(args) -> int:
    from vaultindex.bench import render, run_bench

    modes = tuple(m.strip() for m in args.modes.split(",") if m.strip())
    rep = run_bench(args.golden, index_dir=args.index_dir, root=args.root, models=args.model or None, modes=modes, k=args.k)
    if args.json:
        _dump(rep)
    else:
        print(render(rep))
        if args.details:
            for run in rep["runs"]:
                print(f"\n== {run['model']} · {run['mode']}")
                for d in run["details"]:
                    mark = "ok " if d["rank"] and d["rank"] <= args.k else ("   " if d["rank"] else "MISS")
                    print(f"  {mark} rank={d['rank']!s:>4}  {d['q'][:60]:<60}  top={d['top']}")
    return EXIT_OK


def cmd_briefing(args) -> int:
    from vaultindex.briefing import briefing, render

    b = briefing(root=args.root, index_dir=args.index_dir, days=args.days, include_sensitive=args.sensitive)
    if args.json:
        _dump(b)
    else:
        print(render(b))
    return EXIT_OK


def cmd_lint(args) -> int:
    from vaultindex.lint import lint, render, write_report

    rep = lint(root=args.root, index_dir=args.index_dir)
    if args.json:
        _dump(rep)
    else:
        print(render(rep) if args.stdout else "")
    if not args.no_write:
        path = write_report(rep, root=args.root)
        if not args.json:
            print(
                f"lint: {rep['broken_links']['targets']} alvos de wikilink quebrados · {rep['no_frontmatter']['count']} sem frontmatter · "
                f"{rep['no_type']['count']} sem type · {rep['duplicate_stems']['count']} nomes duplicados · "
                f"{rep['stale_recency']['count']} notas com marcador velho · {len(rep['typed_links']['open_contradictions'])} contradições em aberto"
            )
            print(f"relatório: {path}")
    return EXIT_OK


def make_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m vaultindex", description="Índice de busca derivado do vault.")
    p.add_argument("--root", type=Path, default=None, help="raiz do corpus (default: config.VAULT_BASE)")
    p.add_argument("--index-dir", type=Path, default=None, help="pasta do índice (default: config.VAULT_INDEX_DIR)")
    p.add_argument("--corpus", choices=["vault", "memory"], default="vault", help="memory = memória do Claude Code, índice separado")
    p.add_argument("--json", action="store_true", help="saída em JSON")
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="indexa o corpus (incremental por padrão)")
    b.add_argument("--full", action="store_true", help="apaga o índice e reconstrói tudo")
    b.add_argument("--embed", action="store_true", help="depois do índice, gera os vetores que faltam")
    b.add_argument("--model", help="modelo de embedding (default: o ativo, senão o padrão do pacote)")
    b.set_defaults(fn=cmd_build)

    e = sub.add_parser("embed", help="gera vetores para os chunks sem embedding")
    e.add_argument("--model", help="modelo (default: padrão do pacote ou TECHCOLAB_EMBED_MODEL)")
    e.add_argument("--force", action="store_true", help="apaga os vetores desse modelo e refaz")
    e.add_argument("--batch", type=int, default=32)
    e.add_argument("--no-activate", action="store_true", help="não torna esse o modelo ativo da busca")
    e.set_defaults(fn=cmd_embed)

    s = sub.add_parser("search", help="busca no índice")
    s.add_argument("query", nargs="+")
    s.add_argument("-k", type=int, default=10)
    s.add_argument("--sensitive", action="store_true", help="inclui Team/, Stakeholders/ e tipos de 1:1")
    s.add_argument("--type", action="append", help="filtra por type do frontmatter (repetível)")
    s.add_argument("--folder", help="prefixo de pasta, ex.: Projects/")
    s.add_argument("--since", help="YYYY-MM-DD")
    s.add_argument("--until", help="YYYY-MM-DD")
    s.add_argument("--as-of", help="YYYY-MM-DD: só notas datadas até aí; marca as que mudaram depois (via git do vault)")
    s.add_argument("--streams", default="fts,vec", help="fts,vec (default) · fts · vec")
    s.add_argument("--model", help="modelo de embedding a usar nesta busca")
    s.add_argument("--no-neighbours", action="store_true", help="desliga o fluxo de vizinhança por wikilink")
    s.add_argument("--no-refresh", action="store_true", help="não atualiza o índice antes de buscar")
    s.set_defaults(fn=cmd_search)

    c = sub.add_parser("check", help="compara o índice com o corpus; sai 1 se divergir")
    c.set_defaults(fn=cmd_check)

    st = sub.add_parser("stats", help="contagens e metadados do índice")
    st.set_defaults(fn=cmd_stats)

    bn = sub.add_parser("bench", help="mede hit@k e MRR contra o golden set")
    bn.add_argument("--golden", type=Path, default=None, help="JSONL {q, expect} (default: App/Personal toolkit/bench/golden.jsonl)")
    bn.add_argument("--model", action="append", help="modelo(s) a comparar (repetível); default: o ativo")
    bn.add_argument("--modes", default="fts,vec,hybrid")
    bn.add_argument("--k", type=int, default=5)
    bn.add_argument("--details", action="store_true", help="mostra o rank de cada pergunta")
    bn.set_defaults(fn=cmd_bench)

    br = sub.add_parser("briefing", help="abertura de sessão sem LLM: última sessão, pendências, notas e decisões recentes")
    br.add_argument("--days", type=int, default=7)
    br.add_argument("--sensitive", action="store_true")
    br.set_defaults(fn=cmd_briefing)

    ln = sub.add_parser("lint", help="saúde estrutural do vault → _reports/Vault-Lint.md")
    ln.add_argument("--no-write", action="store_true", help="não grava o relatório no vault")
    ln.add_argument("--stdout", action="store_true", help="imprime o relatório inteiro")
    ln.set_defaults(fn=cmd_lint)
    return p


def main(argv: list[str] | None = None) -> int:
    _utf8_stdout()
    args = make_parser().parse_args(argv)
    _resolve_corpus(args)
    try:
        return args.fn(args)
    except IndexMissing as e:
        print(f"ERRO: {e}", file=sys.stderr)
        return EXIT_MISSING
    except IndexLocked as e:
        print(f"ERRO: {e}", file=sys.stderr)
        return EXIT_LOCKED
    except SchemaMismatch as e:
        print(f"ERRO: {e}", file=sys.stderr)
        return EXIT_ERROR
    except FileNotFoundError as e:
        print(f"ERRO: {e}", file=sys.stderr)
        return EXIT_ERROR
