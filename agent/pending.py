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
import os
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from config import VAULT_ROOT  # noqa: E402

STORE = VAULT_ROOT / "pendencias.json"
# Congelado no import: os testes trocam STORE por um tmp_path, e a guarda de
# _save compara contra ESTE valor para saber se o alvo e o vault de verdade.
_STORE_REAL = STORE
VIEW = VAULT_ROOT.parent.parent / "Pendencias.md"  # raiz do vault, ao lado do Action-Dashboard

# "graduacao" = nota candidata ao vault central (10_2ndBrain), só o Kelvin aprova.
# "verificacao" = algo que só ele consegue conferir (uma tela, uma rotina no app).
VALID_TIPOS = ["decisao", "graduacao", "verificacao"]
VALID_PRIORIDADES = ["alta", "media", "baixa"]


def _load() -> dict:
    if STORE.exists():
        return json.loads(STORE.read_text(encoding="utf-8"))
    return {"seq": 0, "itens": []}


def _save(data: dict) -> None:
    # Trava: teste nunca escreve no ledger REAL do Kelvin.
    #
    # O ledger é chamado por código de produção (`_stage_for_review` no
    # process.py), então qualquer teste que passe por esse caminho e esqueça de
    # isolar o STORE acaba criando pendência de mentira no vault dele —
    # aconteceu em 31/08 (P-013/P-014, removidas). Uma fixture `autouse` resolve
    # só o arquivo de teste onde ela mora; esta guarda vale para todos, agora e
    # para os que ainda não existem. Falha alto, não em silêncio: teste que
    # escreveria no vault real é bug do teste.
    if os.environ.get("PYTEST_CURRENT_TEST") and STORE == _STORE_REAL:
        raise RuntimeError(
            "teste tentou escrever no ledger REAL do Kelvin "
            f"({STORE}). Isole com monkeypatch de pending.STORE e pending.VIEW, "
            "ou faça monkeypatch de process._register_pending."
        )
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    _render(data)


def _adiada(item, hoje=None) -> bool:
    """Adiada = tem data futura em adiada_ate. Volta sozinha quando a data chega."""
    ate = item.get("adiada_ate")
    return bool(ate) and ate > (hoje or date.today().isoformat())


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
        prio = (i.get("prioridade") or "media")
        adiada = f" · adiada até {i['adiada_ate']}" if _adiada(i) else ""
        lines.append(f"- **{i['id']}** `[{prio}]` `[{i['tipo']}]` {i['texto']}{origem} "
                     f"(desde {i['criada_em']}{adiada})")
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
        "prioridade": args.prioridade,
        # Caminho do artefato que a decisao destrava (ex.: o rascunho em
        # Team/<Pessoa>/_review/). Existe para que o Claude abra e mostre o
        # conteudo NO CHAT - o Kelvin nao vai ao Obsidian ler nada.
        "ref": (args.ref or "").strip(),
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


def cmd_remove(args) -> int:
    """Apagar do ledger o que NUNCA foi pendencia de verdade.

    Diferente de `resolve`: resolvida virou historico consultavel; removida some.
    Existe porque o ledger e chamado por codigo de producao (`_stage_for_review`)
    e um teste que passe por ali cria item no ledger REAL do Kelvin - aconteceu em
    31/08 (P-013/P-014). Marcar lixo de teste como "resolvido" polui justamente o
    historico que ele quer poder consultar. Nao e para descartar decisao que ele
    nao quis tomar: para isso existe resolve (com o motivo) ou snooze.
    """
    data = _load()
    alvo = next((i for i in data["itens"] if i["id"] == args.id), None)
    if alvo is None:
        print(f"[ERRO] {args.id} nao encontrada")
        return 1
    if not args.motivo.strip():
        print("[ERRO] --motivo e obrigatorio: remover sem dizer por que e como "
              "nunca ter registrado")
        return 1
    data["itens"] = [i for i in data["itens"] if i["id"] != args.id]
    _save(data)
    print(f"[OK] {args.id} REMOVIDA ({args.motivo.strip()})")
    print(f"     texto: {alvo['texto'][:70]}")
    return 0


def cmd_snooze(args) -> int:
    """Adiar sem fechar. Sem isto so existem dois estados - gritando ou morta - e
    o que ele nao quer decidir HOJE fica pesando na lista todo dia ate ele parar
    de olhar a lista inteira. Adiada volta sozinha na data."""
    if args.dias is not None and args.dias < 1:
        print("[ERRO] --dias tem que ser >= 1")
        return 1
    ate = args.ate or (date.today() + timedelta(days=args.dias or 7)).isoformat()
    try:
        date.fromisoformat(ate)
    except ValueError:
        print(f"[ERRO] data invalida: {ate} (use YYYY-MM-DD)")
        return 1
    if ate <= date.today().isoformat():
        print(f"[ERRO] {ate} nao e no futuro - adiar para hoje ou antes nao adia nada")
        return 1
    data = _load()
    for i in data["itens"]:
        if i["id"] == args.id:
            if i.get("resolvida_em"):
                print(f"[JA RESOLVIDA] {i['id']}")
                return 2
            i["adiada_ate"] = ate
            _save(data)
            print(f"[OK] {i['id']} adiada ate {ate}")
            return 0
    print(f"[ERRO] {args.id} nao encontrada")
    return 1


def cmd_list(args) -> int:
    data = _load()
    if args.todas:
        itens = data["itens"]
    else:
        # Adiada some da lista ate a data chegar. Esse e o ponto do snooze: o que
        # ele nao quer decidir hoje nao pode pesar na lista todo dia, senao ele
        # para de olhar a lista inteira.
        itens = [i for i in data["itens"]
                 if not i.get("resolvida_em")
                 and (args.incluir_adiadas or not _adiada(i))]
    # (i.get("prioridade") or "media"): item antigo tem a chave com valor None, e
    # .get(k, default) devolve None nesse caso - o default so vale se a chave
    # nao existe.
    ordem = {"alta": 0, "media": 1, "baixa": 2}
    itens = sorted(itens, key=lambda i: (ordem.get(i.get("prioridade") or "media", 1),
                                         i.get("criada_em", "")))
    if args.json:
        print(json.dumps(itens, ensure_ascii=False))
        return 0
    if not itens:
        print("Nada esperando você.")
        return 0
    for i in itens:
        marca = "x" if i.get("resolvida_em") else ("z" if _adiada(i) else " ")
        origem = f"  ({i['origem']})" if i.get("origem") else ""
        prio = (i.get("prioridade") or "media")[:1].upper()
        print(f"[{marca}] {i['id']} ({prio}) [{i['tipo']}] {i['texto']}{origem}")
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
    a.add_argument("--prioridade", default="media", choices=VALID_PRIORIDADES)
    a.add_argument("--ref", default="", help="arquivo que a decisão destrava (o "
                   "Claude mostra o conteúdo no chat; o Kelvin não abre o vault)")

    r = sub.add_parser("resolve", help="marcar como resolvida")
    r.add_argument("id")
    # A resolucao entra LITERAL, nas palavras do Kelvin. Parafrasear aqui apaga
    # o registro dele e deixa a minha leitura no lugar - foi o que aconteceu na
    # P-002 em 31/08 e ele cobrou. O historico so serve para consulta se for o
    # que ele disse, nao o meu resumo do que ele disse.
    r.add_argument("--como", default="", help="qual foi a resolução (palavras do Kelvin, literal)")

    rm = sub.add_parser("remove", help="apagar lixo que nunca foi pendencia real")
    rm.add_argument("id")
    rm.add_argument("--motivo", required=True)

    z = sub.add_parser("snooze", help="adiar sem fechar")
    z.add_argument("id")
    z.add_argument("--dias", type=int, help="adiar N dias (padrão 7)")
    z.add_argument("--ate", help="adiar até YYYY-MM-DD")

    p_list = sub.add_parser("list", help="listar")
    p_list.add_argument("--json", action="store_true")
    p_list.add_argument("--todas", action="store_true", help="inclui resolvidas")
    p_list.add_argument("--incluir-adiadas", action="store_true", dest="incluir_adiadas")

    args = ap.parse_args(argv)
    return {"add": cmd_add, "resolve": cmd_resolve, "snooze": cmd_snooze,
            "remove": cmd_remove, "list": cmd_list}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
