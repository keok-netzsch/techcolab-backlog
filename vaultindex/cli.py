"""
vaultindex/cli.py — `python -m vaultindex build | search | check | stats`.

Exit codes: 0 ok · 1 error · 2 index missing (run build) · 3 another build holds the
lock · `check` exits 1 when the index disagrees with the vault.
"""

from __future__ import annotations

import argparse
import json
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


def cmd_build(args) -> int:
    rep = build(root=args.root, index_dir=args.index_dir, full=args.full)
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
            f"{rep.sensitive_notes} sensíveis · {rep.no_frontmatter} sem frontmatter · "
            f"{rep.embeddings_stale_chunks} chunks sem embedding"
        )
        for w in rep.warnings:
            print(f"AVISO {w}")
        print(f"em {rep.index_dir}")
    return EXIT_OK


def cmd_search(args) -> int:
    out = search(
        " ".join(args.query),
        k=args.k,
        include_sensitive=args.sensitive,
        types=args.type or None,
        folder=args.folder,
        since=args.since,
        until=args.until,
        refresh=not args.no_refresh,
        root=args.root,
        index_dir=args.index_dir,
    )
    if args.json:
        _dump(out)
        return EXIT_OK
    head = f"[{out['mode']}] índice de há {_fmt_age(out['index_age_seconds'])}"
    if out.get("refreshed"):
        head += f" · refresh: {out['refreshed']}"
    if out["excluded_sensitive_hits"]:
        head += f" · {out['excluded_sensitive_hits']} nota(s) sensível(is) fora (use --sensitive)"
    print(head)
    if not out["results"]:
        print("nenhum resultado" + (f" ({out['note']})" if out.get("note") else ""))
        return EXIT_OK
    for r in out["results"]:
        flag = " ⚠" if r["sensitive"] else ""
        print(f"\n{r['rank']:>2}. {r['title']}{flag}  [{r['type'] or 'sem type'} · {r['date'] or '?'}]  {r['path']}")
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


def make_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m vaultindex", description="Índice de busca derivado do vault.")
    p.add_argument("--root", type=Path, default=None, help="raiz do vault (default: config.VAULT_BASE)")
    p.add_argument("--index-dir", type=Path, default=None, help="pasta do índice (default: config.VAULT_INDEX_DIR)")
    p.add_argument("--json", action="store_true", help="saída em JSON")
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="indexa o vault (incremental por padrão)")
    b.add_argument("--full", action="store_true", help="apaga o índice e reconstrói tudo")
    b.set_defaults(fn=cmd_build)

    s = sub.add_parser("search", help="busca no índice")
    s.add_argument("query", nargs="+")
    s.add_argument("-k", type=int, default=10)
    s.add_argument("--sensitive", action="store_true", help="inclui Team/, Stakeholders/ e tipos de 1:1")
    s.add_argument("--type", action="append", help="filtra por type do frontmatter (repetível)")
    s.add_argument("--folder", help="prefixo de pasta, ex.: Projects/")
    s.add_argument("--since", help="YYYY-MM-DD")
    s.add_argument("--until", help="YYYY-MM-DD")
    s.add_argument("--no-refresh", action="store_true", help="não atualiza o índice antes de buscar")
    s.set_defaults(fn=cmd_search)

    c = sub.add_parser("check", help="compara o índice com o vault; sai 1 se divergir")
    c.set_defaults(fn=cmd_check)

    st = sub.add_parser("stats", help="contagens e metadados do índice")
    st.set_defaults(fn=cmd_stats)
    return p


def main(argv: list[str] | None = None) -> int:
    _utf8_stdout()
    args = make_parser().parse_args(argv)
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
