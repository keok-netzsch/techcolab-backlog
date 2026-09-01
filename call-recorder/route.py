"""Route a transcribed call by SUBJECT, to as many destinations as it deserves.

The old flow asked Kelvin where a recording belonged at 16:00, from the Teams
window title, before a single word had been transcribed — and let him pick exactly
one destination. Neither holds up: the title carries the scheduled subject, never
the real one, and a Daily BIZ that spends ten minutes on Daniel's OKR and the rest
on project work has two destinations, not one.

So transcription (20:00 batch) now parks the job as `<base>.job.json.routing`, and
routing happens afterwards against the content. See
`vault/decisions/2026-08-28-roteamento-por-assunto.md`.

    python route.py                       # o que foi transcrito e espera destino
    python route.py --json                # o mesmo, legivel por maquina
    python route.py 08-15 --texto         # despeja a transcricao para leitura

    # um destino, call inteira
    python route.py 08-15 --para project

    # varios destinos, cada um com a sua janela de tempo
    python route.py 08-15 \
        --para person:Daniel-Lima --de 0 --ate 11:20 --assunto "OKR de artigos" \
        --para project --de 11:20 --assunto "andamento das entregas"

    python route.py 08-15 --descartar     # nao interessa: arquiva sem escrever no vault

`--para` aceita `kind` ou `kind:alvo`, e consome os `--de` / `--ate` / `--assunto`
que vierem logo depois. Tempo em segundos, `mm:ss` ou `h:mm:ss`.

**O corte e por tempo, nao por busca semantica.** A primeira versao pedia ao Ollama
que achasse as falas sobre um assunto; o qwen2.5-coder respondeu `(nada)` para uma
janela que discutia o assunto abertamente, e recorte errado e pior que recorte
nenhum — arquiva uma nota confiante feita sobre a metade errada da call. Quem leu a
transcricao da os limites; o script so obedece. `--assunto` e rotulo da nota, nao
consulta.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
RECORDINGS = HERE / "recordings"

KINDS_WITH_TARGET = ("person", "manager")


def _parked():
    return sorted(RECORDINGS.glob("*.job.json.routing"))


def _held():
    """Jobs deliberadamente segurados fora da fila de roteamento.

    Um job vira `.routing.hold` quando a transcricao dele nao e confiavel e
    rotea-la sujaria o vault. Sao contados e anunciados porque a alternativa e
    pior: dez gravacoes somem da listagem e `listar()` responde "nada
    aguardando destino", que le como "tudo em dia". O repo ja pagou por um
    zero-pendentes silencioso uma vez.
    """
    return sorted(RECORDINGS.glob("*.job.json.routing.hold"))


def _load(p):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _stem(p: Path) -> str:
    return p.name.replace(".job.json.routing", "")


def _meeting(j) -> str:
    """Teams window titles carry framing junk around the actual subject."""
    title = j.get("meeting", "") or ""
    parts = [x.strip() for x in title.split("|")
             if x.strip() and "microsoft teams" not in x.lower()
             and x.strip().lower() not in ("chat", "meeting join", "ingresso na reuniao",
                                           "ingresso na reunião")]
    return " / ".join(parts) if parts else title


def _transcript_text(j) -> str:
    t = Path(j.get("transcript", ""))
    if not t.exists():
        return ""
    try:
        return t.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return t.read_text(encoding="utf-8", errors="replace")


# ── Regras de roteamento por reuniao ─────────────────────────────────────────
# Decididas pelo Kelvin; aparecem na listagem (humana e --json) para que a
# sessao que roteia as veja SEM depender de ter lido CLAUDE.md ou o ADR.
#
# 2026-08-29 — Daily BIZ / Daily PM sao territorio do Team Memory Agent: o TMA
# ja captura o resumo docx dessas series e consolida no vault central. Sem esta
# regra, o mesmo fato do time apareceria no relatorio semanal do TMA e numa
# nota roteada, com versoes divergentes. Aqui, rotear SO o que e pessoal do
# Kelvin (decisao dele, 1:1 embutido, item de stakeholder) e descartar o resto.
ROUTING_RULES = [
    (("daily biz", "daily pm"),
     "territorio do TMA - rotear SO o pessoal do Kelvin (decisao dele, 1:1 "
     "embutido, item de stakeholder); o resto --descartar. "
     "ADR 2026-08-29-call-recorder-avaliacao-arquitetura.md, secao C1"),
]


# ── Contrato de extracao (2026-08-31, pedido do Kelvin) ──────────────────────
# Alem de rotear, a sessao das 09:00 EXTRAI de cada transcricao:
#
# 1. COMPROMISSOS -> linhas `- [ ] (Dono) texto @YYYY-MM-DD` DENTRO das notas
#    roteadas. Essa sintaxe nao e estilo: e o formato que process.py dashboard
#    coleta (dono entre parenteses no inicio, @data em qualquer lugar; sem dono
#    E sem data a linha e ignorada como ruido). O monitoramento inteiro - o
#    Action-Dashboard e o lembrete diario de vencidos - le SO esse formato.
#
# 2. OPORTUNIDADES -> BacklogStore via create_idea.py, status "em analise"
#    (e o estagio de curadoria do schema: Kelvin aprova ou rejeita), com
#    --origin apontando a transcricao. Titulo duplicado e recusado pelo
#    proprio create_idea (exit 2) - e o dedup entre conversas.
#
# Antes de criar, CRUZAR: conferir o Action-Dashboard.md (acoes ja abertas) e
# o backlog (ideias ja registradas) - compromisso repetido em duas calls e
# sinal de importancia, nao motivo para duplicar o item.
EXTRACT_CONTRACT = (
    "EXTRAIR desta transcricao, alem de rotear: "
    "(1) compromissos -> escrever nas notas roteadas como "
    "'- [ ] (Dono) texto @YYYY-MM-DD' (sintaxe exata do dashboard; sem dono e "
    "sem data a linha e invisivel ao monitor); "
    "(2) oportunidades -> python agent/create_idea.py --title ... "
    "--status \"em analise\" --origin <transcricao> (curadoria do Kelvin); "
    "(3) antes de criar, cruzar com Action-Dashboard.md e o backlog - "
    "recorrencia consolida o item existente, nao duplica."
)


def rule_for(meeting: str) -> str:
    m = (meeting or "").lower()
    for keys, guidance in ROUTING_RULES:
        if any(k in m for k in keys):
            return guidance
    return ""


def listar(as_json=False):
    rows = []
    for p in _parked():
        j = _load(p)
        if not j:
            continue
        text = _transcript_text(j)
        rows.append({
            "id": _stem(p),
            "date": j.get("date", ""),
            "time": (j.get("time", "") or "").replace("-", ":"),
            "meeting": _meeting(j),
            "context": j.get("context", ""),
            "words": len(text.split()),
            "transcript": j.get("transcript", ""),
            "rule": rule_for(_meeting(j)),
            "extract": EXTRACT_CONTRACT,
        })
    # O aviso vai para stderr no caminho --json: o consumidor espera uma LISTA em
    # stdout, e embrulhar isso num objeto para caber um contador quebraria ele.
    held = _held()
    if held:
        aviso = (f"[HOLD] {len(held)} job(s) segurado(s) fora desta listagem "
                 f"(*.job.json.routing.hold). Motivo e como soltar: "
                 f"recordings/LEIA-ANTES-DE-ROTEAR.md")
    if as_json:
        if held:
            print(aviso, file=sys.stderr)
        print(json.dumps(rows, ensure_ascii=False))
        return 0
    if held:
        print(aviso + "\n")
    if not rows:
        print("nada transcrito aguardando destino."
              if not held else "nada aguardando destino ALEM dos segurados acima.")
        return 0
    print(f"{len(rows)} gravacao(oes) transcrita(s) aguardando destino:\n")
    for r in rows:
        print(f"  {r['id']}")
        print(f"     {r['date']} {r['time']}  {r['meeting']}  ({r['words']} palavras)")
        if r["context"]:
            print(f"     contexto: {r['context']}")
        if r["rule"]:
            print(f"     REGRA: {r['rule']}")
        print()
    print("EXTRACAO (para cada gravacao roteada):")
    print("   - compromissos -> '- [ ] (Dono) texto @YYYY-MM-DD' nas notas roteadas")
    print("   - oportunidades -> create_idea.py --status \"em analise\" --origin <transcricao>")
    print("   - cruzar antes com Action-Dashboard.md e o backlog (nao duplicar)")
    print()
    print("Para rotear:")
    print("   python route.py <trecho> --para person:Ana-Leite --assunto \"...\"")
    print("   python route.py <trecho> --descartar")
    return 0


def _match(fragment):
    hits = [p for p in _parked() if fragment in p.name]
    if not hits:
        raise SystemExit(f"nenhuma gravacao parqueada casa com '{fragment}'")
    if len(hits) > 1:
        raise SystemExit("ambiguo:\n  " + "\n  ".join(_stem(h) for h in hits))
    return hits[0]


def _seconds(v: str) -> float:
    """Accept 272, 4:32 or 1:02:30 — reading a transcript you think in mm:ss."""
    v = v.strip()
    try:
        parts = [float(x) for x in v.split(":")]
    except ValueError:
        raise SystemExit(f"tempo invalido: '{v}' (use 272, 4:32 ou 1:02:30)")
    total = 0.0
    for part in parts:
        total = total * 60 + part
    return total


def _pair_routes(argv):
    """Pair each --para with the --de/--ate/--assunto that follow it.

    argparse cannot express "these repeatable flags belong to that one", and
    zipping independent lists breaks the moment one destination omits a flag.
    """
    routes, i = [], 0
    while i < len(argv):
        if argv[i] != "--para":
            i += 1
            continue
        if i + 1 >= len(argv):
            raise SystemExit("--para sem valor")
        kind, _, target = argv[i + 1].partition(":")
        r = {"kind": kind, "target": target, "topic": "", "de": None, "ate": None}
        i += 2
        while i + 1 < len(argv) and argv[i] in ("--assunto", "--de", "--ate"):
            flag, val = argv[i], argv[i + 1]
            if flag == "--assunto":
                r["topic"] = val
            else:
                r[flag[2:]] = _seconds(val)
            i += 2
        routes.append(r)
    return routes


def aplicar(p: Path, routes, dry_run=False):
    import process as proc

    j = _load(p)
    if j is None:
        raise SystemExit(f"job ilegivel: {p.name}")
    transcript = _transcript_text(j)
    if not transcript.strip():
        raise SystemExit(f"transcricao vazia ou ausente: {j.get('transcript')}")

    date = j.get("date", "")
    lang = j.get("lang_detected") or j.get("lang", "pt")
    lang_word = "ingles" if lang == "en" else "portugues"
    context = j.get("context", "")

    for r in routes:
        kind, target, topic = r["kind"], r["target"], r["topic"]
        de, ate = r["de"], r["ate"]
        if kind in KINDS_WITH_TARGET and not target:
            raise SystemExit(f"kind '{kind}' exige alvo: use {kind}:Pasta-Da-Pessoa")
        if kind not in ("person", "manager", "note") and kind not in proc.CAPTURE_MODES:
            raise SystemExit(f"kind invalido '{kind}'")

        window = ""
        if de is not None or ate is not None:
            window = f"{_hms(de)}–{_hms(ate)}"
        label = f"{kind}:{target}" if target else kind
        print(f"\n=== {label}  [{topic or 'sem rotulo'}]"
              + (f"  {window}" if window else "  transcricao inteira"))
        if dry_run:
            continue

        if window:
            slice_text = proc.slice_by_time(transcript, de, ate)
            if not slice_text.strip():
                print(f"  [!] janela {window} nao tem nenhuma linha — destino pulado.")
                continue
            # Each destination reads a real transcript file, so the existing
            # writers work unchanged. The slice is kept next to the full
            # transcript instead of a temp dir: if a note later looks wrong, the
            # exact text that produced it is still on disk.
            spath = Path(j["transcript"]).with_name(
                Path(j["transcript"]).stem + "." + _slug(topic or window) + ".txt")
            spath.write_text(slice_text, encoding="utf-8")
            print(f"  recorte: {len(slice_text.splitlines())} linhas -> {spath.name}")
        else:
            spath = Path(j["transcript"])

        note = context
        if topic:
            note = (context + " | " if context else "") + f"recorte: {topic}"

        if kind == "person":
            proc.cmd_transcript(target, str(spath), date,
                                structured=j.get("structured", False), lang=lang)
        elif kind == "manager":
            proc.cmd_manager(target, str(spath), date, lang=lang)
        elif kind == "note":
            proc.cmd_note(str(spath), date, lang=lang, time_str=j.get("time"))
        else:
            proc.cmd_capture(kind, str(spath), date, lang=lang,
                             time_str=j.get("time"), context=note)

    if dry_run:
        print("\n(dry-run — nada escrito)")
        return 0

    j["routes"] = routes
    p.write_text(json.dumps(j, ensure_ascii=False), encoding="utf-8")
    p.rename(p.with_suffix(".routing.done"))
    print(f"\n[ok] {_stem(p)}: {len(routes)} destino(s) aplicado(s).")
    return 0


def _hms(s) -> str:
    if s is None:
        return ""
    s = int(s)
    return f"{s // 60}:{s % 60:02d}"


def _slug(s: str) -> str:
    keep = [c.lower() if c.isalnum() else "-" for c in s]
    out = "".join(keep)
    while "--" in out:
        out = out.replace("--", "-")
    return out.strip("-")[:40] or "recorte"


def descartar(p: Path):
    """'Nao interessa' has to be as cheap as filing it, or everything gets filed."""
    j = _load(p) or {}
    j["discarded"] = True
    p.write_text(json.dumps(j, ensure_ascii=False), encoding="utf-8")
    p.rename(p.with_suffix(".routing.discarded"))
    print(f"[ok] {_stem(p)}: descartado (audio e transcricao preservados).")
    return 0


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("fragmento", nargs="?")
    ap.add_argument("--para", action="append", default=[])
    ap.add_argument("--assunto", action="append", default=[])
    ap.add_argument("--de", action="append", default=[])
    ap.add_argument("--ate", action="append", default=[])
    ap.add_argument("--texto", action="store_true", help="imprime a transcricao")
    ap.add_argument("--descartar", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("-h", "--help", action="store_true")
    a, _ = ap.parse_known_args()

    if a.help:
        print(__doc__)
        return 0
    if a.json and not a.fragmento:
        return listar(as_json=True)
    if not a.fragmento:
        return listar()

    p = _match(a.fragmento)

    if a.texto:
        j = _load(p) or {}
        print(_transcript_text(j))
        return 0
    if a.descartar:
        return descartar(p)
    if not a.para:
        raise SystemExit("nada a fazer: use --para, --texto ou --descartar")

    return aplicar(p, _pair_routes(sys.argv[1:]), dry_run=a.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
