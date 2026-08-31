"""Ledger de pendências do Kelvin — o que espera decisão/graduação dele, num lugar só.

Por que existe (pedido dele, 2026-08-31): cada sessão de Claude deixava as
pendências no seu próprio ADR ou handoff, e a pergunta "o que precisa ser
graduado/resolvido?" não tinha onde ser respondida — nem "o que eu já resolvi",
para consulta posterior. Este ledger é o lugar único: sessões REGISTRAM aqui em
vez de enterrar no documento da vez; o lembrete das 08:45 mostra a contagem; a
resolução vira histórico consultável em vez de evaporar na conversa.

Modelo igual ao resto do toolkit: dados em JSON (fonte), visão em Markdown
(gerada, no vault, para o Obsidian). Nunca editar o .md à mão — ele é
regenerado inteiro a cada mudança, como o Action-Dashboard.

Uso:
    python agent/pending.py add --tipo decisao --texto "..." [--origem "..."]
    python agent/pending.py resolve P-003 --como "aprovado em conversa"
    python agent/pending.py list [--json] [--todas]
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from config import VAULT_ROOT  # noqa: E402

STORE = VAULT_ROOT / "pendencias.json"
VIEW = VAULT_ROOT.parent.parent / "Pendencias.md"  # raiz do vault, ao lado do Action-Dashboard

# "graduacao" = nota candidata ao vault central (10_2ndBrain), só o Kelvin aprova.
# "verificacao" = algo que só ele consegue conferir (uma tela, uma rotina no app).
VALID_TIPOS = ["decisao", "graduacao", "verificacao"]


def _load() -> dict:
    if STORE.exists():
        return json.loads(STORE.read_text(encoding="utf-8"))
    return {"seq": 0, "itens": []}


def _save(data: dict) -> None:
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    _render(data)


def _render(data: dict) -> None:
    abertas = [i for i in data["itens"] if not i.get("resolvida_em")]
    resolvidas = [i for i in data["itens"] if i.get("resolvida_em")]
    resolvidas.sort(key=lambda i: i["resolvida_em"], reverse=True)

    lines = [
        "# Pendências — o que espera o Kelvin",
        "",
        "> Gerado por `agent/pending.py` — não editar à mão. Para resolver:",
        '> `python agent/pending.py resolve P-NNN --como "..."` (ou peça ao Claude).',
        "",
        f"## Abertas ({len(abertas)})",
        "",
    ]
    if not abertas:
        lines.append("*Nada esperando você.*")
    for i in abertas:
        origem = f" — *{i['origem']}*" if i.get("origem") else ""
        lines.append(f"- **{i['id']}** `[{i['tipo']}]` {i['texto']}{origem} "
                     f"(desde {i['criada_em']})")
    lines += ["", f"## Resolvidas ({len(resolvidas)})", ""]
    for i in resolvidas:
        como = f" → {i['resolucao']}" if i.get("resolucao") else ""
        lines.append(f"- ~~**{i['id']}**~~ `[{i['tipo']}]` {i['texto']}{como} "
                     f"({i['criada_em']} → {i['resolvida_em']})")
    lines.append("")
    VIEW.write_text("\n".join(lines), encoding="utf-8")


def cmd_add(args) -> int:
    if args.tipo not in VALID_TIPOS:
        print(f"[ERRO] tipo '{args.tipo}' inválido; use: {', '.join(VALID_TIPOS)}")
        return 1
    data = _load()
    # Dedup por texto: a mesma pendência registrada por duas sessões (o cenário
    # que motivou o ledger) não pode virar duas linhas para o Kelvin fechar.
    norm = " ".join(args.texto.lower().split())
    for i in data["itens"]:
        if not i.get("resolvida_em") and " ".join(i["texto"].lower().split()) == norm:
            print(f"[JA EXISTE] {i['id']}: {i['texto']}")
            return 2
    data["seq"] += 1
    item = {
        "id": f"P-{data['seq']:03d}",
        "tipo": args.tipo,
        "texto": args.texto.strip(),
        "origem": (args.origem or "").strip(),
        "criada_em": date.today().isoformat(),
    }
    data["itens"].append(item)
    _save(data)
    print(f"[OK] {item['id']} registrada ({item['tipo']})")
    return 0


def cmd_resolve(args) -> int:
    data = _load()
    for i in data["itens"]:
        if i["id"] == args.id:
            if i.get("resolvida_em"):
                print(f"[JA RESOLVIDA] {i['id']} em {i['resolvida_em']}")
                return 2
            i["resolvida_em"] = date.today().isoformat()
            i["resolucao"] = (args.como or "").strip()
            _save(data)
            print(f"[OK] {i['id']} resolvida: {i['texto'][:60]}")
            return 0
    print(f"[ERRO] {args.id} não encontrada")
    return 1


def cmd_list(args) -> int:
    data = _load()
    itens = data["itens"] if args.todas else \
        [i for i in data["itens"] if not i.get("resolvida_em")]
    if args.json:
        print(json.dumps(itens, ensure_ascii=False))
        return 0
    if not itens:
        print("Nada esperando você.")
        return 0
    for i in itens:
        marca = "x" if i.get("resolvida_em") else " "
        origem = f"  ({i['origem']})" if i.get("origem") else ""
        print(f"[{marca}] {i['id']} [{i['tipo']}] {i['texto']}{origem}")
    return 0


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Ledger de pendências do Kelvin")
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add", help="registrar pendência")
    a.add_argument("--tipo", required=True, help="decisao | graduacao | verificacao")
    a.add_argument("--texto", required=True)
    a.add_argument("--origem", default="", help="de onde veio (ADR, sessão, call)")

    r = sub.add_parser("resolve", help="marcar como resolvida")
    r.add_argument("id")
    # A resolucao entra LITERAL, nas palavras do Kelvin. Parafrasear aqui apaga
    # o registro dele e deixa a minha leitura no lugar - foi o que aconteceu na
    # P-002 em 31/08 e ele cobrou. O historico so serve para consulta se for o
    # que ele disse, nao o meu resumo do que ele disse.
    r.add_argument("--como", default="", help="qual foi a resolução (palavras do Kelvin, literal)")

    l = sub.add_parser("list", help="listar")
    l.add_argument("--json", action="store_true")
    l.add_argument("--todas", action="store_true", help="inclui resolvidas")

    args = ap.parse_args(argv)
    return {"add": cmd_add, "resolve": cmd_resolve, "list": cmd_list}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
