"""vaultsources/qa.py — o QA que procura a inconsistencia, nao o bug.

Motivo de existir, em uma frase: em 2026-09-10 a revisao do segundo cerebro achou
que o braco de pesquisa inteiro (`/youtube`, `/research`, `/x-read`, `/x-pulse`)
estava desligado havia meses porque os comandos mandavam rodar de
`~/Projects/personal/obsidian-second-brain/`, um caminho que nao existe nesta
maquina. Nenhum teste pegaria isso: o codigo estava certo, a documentacao e que
apontava para o lugar errado.

Entao este QA nao testa funcao. Ele confere que o que os documentos afirmam
continua verdade:

    refs         caminho citado em doc/comando existe mesmo
    folders      pasta que o manual do vault descreve existe, e o que ele diz
                 sobre ela (vazia, ausente) bate com o disco
    deadloops    produtor declarado que nao produz ha N dias
    notes        nota de fonte com frontmatter completo e hash batendo
    placeholders `[data]`, `TODO`, `<!-- pending-analysis -->` esquecidos no registro
    deps         yt-dlp, legenda, whisper e a CA da rede corporativa funcionando
    governance   todo purpose usado no codigo esta declarado; pergunta sensivel
                 nao vaza para busca externa
    inbox        captura parada esperando triagem
    duplicates   dois arquivos com o mesmo nome (o Obsidian resolve [[X]] para um so)

Quem le o resultado (padrao 12 — detector sem consumidor nao protege nada):

    1. `scripts/notify.ps1 -Profile sources-qa`, silencioso quando nao ha erro
    2. a rotina Claude `fontes-semanal`, que abre o relatorio no chat
    3. `_reports/Sources-QA.md`, saida gerada, reescrita a cada execucao
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path

from vaultsources import governance, net, note, paths

REPO = Path(__file__).resolve().parent.parent
HOME = Path.home()

ERRO, AVISO, INFO = "erro", "aviso", "info"


@dataclass
class Finding:
    check: str
    severity: str
    title: str
    detail: str = ""
    where: str = ""
    fix: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


# ── 1. refs: caminho citado em documento existe? ──────────────────────────────

DOC_TARGETS = [
    HOME / ".claude" / "CLAUDE.md",
    REPO / "ARCHITECTURE.md",
    REPO / "CLAUDE.md",
    REPO / "docs" / "scheduled-automation.md",
]

_PATHY = re.compile(r"`([^`\n]{4,160})`")
_EXTS = (".py", ".ps1", ".md", ".json", ".bat", ".vbs", ".sqlite", ".txt",
         ".html", ".css", ".js", ".xlsx", ".docx", ".pptx", ".pem")
# Alem do obvio, descarta padrao de nome: `AI/sessions/YYYY-MM-DD.md` e um molde,
# nao um arquivo, e cobrar existencia dele so ensina o leitor a ignorar o relatorio.
_SKIP = re.compile(
    r"[*?{}<>|]|^https?:|^\$|^-{1,2}[a-z]|^[A-Z_]+=|\.\.\.|caminho/do|path/to"
    r"|YYYY|MM-DD|NNN|Wnn|HH:MM|<[^>]+>|\bNome\b|\bName\b")


def _doc_files() -> list[Path]:
    out = [p for p in DOC_TARGETS if p.exists()]
    cmds = HOME / ".claude" / "commands"
    if cmds.exists():
        out += sorted(cmds.glob("*.md"))
    vault_manual = paths.VAULT / "_CLAUDE.md"
    if vault_manual.exists():
        out.append(vault_manual)
    return out


_ANCHORED = re.compile(r"^(~/|[A-Za-z]:[/\\]|\{VAULT_ROOT\}|\.claude/|%[A-Z_]+%)")

# Raizes onde um fragmento de caminho pode legitimamente morar. Um documento que
# escreve `bin/tma_capture.py` depois de dizer "no TeamMemoryAgent" nao esta
# mentindo: esta abreviando. Fragmento so vira achado quando o nome do arquivo
# nao existe em lugar nenhum.
_FRAGMENT_ROOTS = [
    REPO,
    paths.VAULT,
    HOME / "TeamMemoryAgent",
    HOME / ".claude",
    HOME / "voice-dictate",
]

_BASENAMES: set[str] | None = None


def _basename_index() -> set[str]:
    global _BASENAMES
    if _BASENAMES is not None:
        return _BASENAMES
    names: set[str] = set()
    for root in _FRAGMENT_ROOTS:
        if not root.exists():
            continue
        for p in root.rglob("*"):
            parts = p.relative_to(root).parts
            if any(x in (".git", "node_modules", "__pycache__", ".venv") for x in parts):
                continue
            names.add(p.name.lower())
    _BASENAMES = names
    return names


def _looks_like_path(tok: str) -> bool:
    if _SKIP.search(tok):
        return False
    if " " in tok and not tok.lower().endswith(_EXTS):
        return False
    if tok.endswith("/"):
        return True
    return tok.lower().endswith(_EXTS) and ("/" in tok or "\\" in tok)


def _expand(raw: str) -> str:
    raw = raw.replace("{VAULT_ROOT}", str(paths.VAULT))
    return os.path.expandvars(raw)


def _resolve(tok: str) -> Path | None:
    raw = _expand(tok.strip().strip("`")).replace("\\", "/")
    if raw.startswith("~/"):
        cands = [HOME / raw[2:]]
    elif re.match(r"^[A-Za-z]:/", raw):
        cands = [Path(raw)]
    else:
        cands = [REPO / raw, paths.VAULT / raw, HOME / raw]
    for c in cands:
        try:
            if c.exists():
                return c
        except OSError:
            continue
    return None


def check_refs() -> list[Finding]:
    """Caminho ancorado que nao existe e erro; fragmento e so aviso, e so quando
    o nome do arquivo nao aparece em nenhuma raiz conhecida.

    A distincao nao e preciosismo. Sem ela o check devolveu 134 achados, quase
    todos fragmentos legitimos (`bin/tma_capture.py` embaixo de `~/TeamMemoryAgent`),
    e um relatorio assim ninguem le duas vezes.
    """
    out = []
    for doc in _doc_files():
        try:
            text = doc.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        where = (str(doc.relative_to(HOME)) if str(doc).startswith(str(HOME))
                 else str(doc))
        seen = set()
        for tok in _PATHY.findall(text):
            tok = tok.strip()
            if tok in seen or not _looks_like_path(tok):
                continue
            seen.add(tok)
            if _resolve(tok) is not None:
                continue
            anchored = bool(_ANCHORED.match(_expand(tok)))
            base = Path(_expand(tok).replace("\\", "/").rstrip("/")).name.lower()
            if not anchored and base in _basename_index():
                continue  # fragmento com base conhecida: abreviacao, nao mentira
            out.append(Finding(
                "refs", ERRO if anchored else AVISO,
                "caminho citado nao existe: %s" % tok,
                "o documento manda usar este caminho e ele nao resolve. Foi assim "
                "que /youtube, /research e /x-read ficaram meses quebrados apontando "
                "para ~/Projects/personal/obsidian-second-brain/."
                if anchored else
                "fragmento cujo nome de arquivo tambem nao aparece em nenhuma raiz "
                "conhecida — pode ser renomeacao esquecida",
                where=where,
                fix="corrija o caminho no documento ou crie o alvo",
            ))
    return out


# ── 2. folders: o manual descreve a realidade? ────────────────────────────────

def check_folders() -> list[Finding]:
    out = []
    manual = paths.VAULT / "_CLAUDE.md"
    if not manual.exists():
        return [Finding("folders", ERRO, "_CLAUDE.md do vault ausente",
                        where=str(paths.VAULT))]
    full = manual.read_text(encoding="utf-8", errors="replace")

    # So a secao Folder Map. Mais abaixo o manual tem a tabela de mapeamento das
    # skills genericas, cuja primeira coluna lista de proposito pastas que este
    # vault NAO usa (`raw/`, `wiki/entities/`, `Ideas/`). Checar aquela tabela
    # transformava uma explicacao correta em cinco erros.
    fm_start = full.find("## Folder Map")
    if fm_start == -1:
        return [Finding("folders", AVISO, "o manual nao tem secao `## Folder Map`",
                        where="_CLAUDE.md")]
    nxt = full.find("\n## ", fm_start + 5)
    text = full[fm_start: nxt if nxt != -1 else len(full)]

    for m in re.finditer(r"^\|\s*`([A-Za-z][\w &./-]*/)`", text, re.M):
        rel = m.group(1).rstrip("/")
        target = paths.VAULT / rel
        if not target.exists():
            out.append(Finding(
                "folders", ERRO,
                "o manual descreve `%s/` e a pasta nao existe" % rel,
                "quem le o manual acredita nele. Documento que mente custa mais "
                "que documento ausente (ARCHITECTURE.md).",
                where="_CLAUDE.md", fix="crie a pasta ou tire a linha do Folder Map"))

    # Afirmacoes de vacuidade que envelheceram. Varre o manual inteiro (`full`), nao
    # so o Folder Map: a frase que dizia "Daily/ esta vazia, nao confie nela" morava
    # na tabela de mapeamento das skills, mais abaixo, e ficou 17 dias escondendo a
    # fonte mais recente do vault.
    for m in re.finditer(r"`?([A-Z][\w-]*)/`?[^.\n]{0,80}\b(?:is|esta|está)\s+\*{0,2}empty\*{0,2}",
                         full, re.I):
        rel = m.group(1)
        target = paths.VAULT / rel
        if target.exists():
            n = len(list(target.rglob("*.md")))
            if n > 0:
                out.append(Finding(
                    "folders", ERRO,
                    "o manual diz que `%s/` esta vazia; ha %d notas la" % (rel, n),
                    "a instrucao seguinte costuma ser 'nao confie nesta pasta', o "
                    "que faz a proxima sessao ignorar a fonte mais recente que existe.",
                    where="_CLAUDE.md", fix="atualize a frase no _CLAUDE.md"))
    return out


# ── 3. deadloops: produtor declarado que nao produz ───────────────────────────

LOOPS = [
    # Cadencia decidida pelo Kelvin em 2026-09-10: "exporto o analytics do LinkedIn
    # toda sexta" (ledger P-117). O alvo mudou junto: ate entao o check media
    # `AI/sessions/linkedin-weekly-*.md`, um relatorio que nunca existiu, e por isso
    # acusava um loop que nao tinha como fechar. Agora mede o artefato real, que e o
    # metrics importado do .xlsx. 10 dias e uma sexta perdida mais folga.
    {"name": "LinkedIn — import do analytics",
     "declared_in": "Areas/LinkedIn/performance-log.md",
     "glob": "Areas/LinkedIn/_metrics.json", "max_age_days": 10,
     "why": "a cadencia acertada e sexta; sem o import a estrategia de conteudo "
            "volta a nao ter medicao nenhuma, que foi o estado de 01/06 a 10/09"},
    {"name": "Reviews semanais (/obsidian-review)",
     "declared_in": "_CLAUDE.md", "glob": "Reviews/*.md", "max_age_days": 21,
     "why": "o manual cita a pasta Reviews/ como destino e ela nunca existiu"},
    {"name": "Fontes externas ingeridas",
     "declared_in": "vault/decisions/2026-09-10-vaultsources-conhecimento-externo.md",
     "glob": "Sources/*.md", "max_age_days": 21,
     "why": "o cano existe para trazer conhecimento de fora; parado, o vault volta "
            "a ser um sistema fechado"},
    {"name": "Lint do vault",
     "declared_in": "docs/scheduled-automation.md",
     "glob": "_reports/Vault-Lint.md", "max_age_days": 4,
     "why": "a rotina TechColab Vault Index roda 18:00 e regenera o lint"},
]


def check_deadloops() -> list[Finding]:
    out = []
    now = datetime.now()
    for loop in LOOPS:
        hits = [p for p in paths.VAULT.glob(loop["glob"]) if p.is_file()]
        if not hits:
            out.append(Finding(
                "deadloops", ERRO,
                "loop morto: %s nunca produziu nada" % loop["name"],
                loop["why"], where=loop["declared_in"],
                fix="ligue o produtor ou remova a promessa do documento"))
            continue
        newest = max(hits, key=lambda p: p.stat().st_mtime)
        age = (now - datetime.fromtimestamp(newest.stat().st_mtime)).days
        if age > loop["max_age_days"]:
            out.append(Finding(
                "deadloops", AVISO,
                "loop parado: %s, ultima saida ha %d dias" % (loop["name"], age),
                loop["why"], where=str(newest.relative_to(paths.VAULT)),
                fix="rode o produtor ou reveja a cadencia declarada"))
    return out


# ── 4. notes: a nota de fonte esta integra? ───────────────────────────────────

REQUIRED_FM = ("type", "source-kind", "source-url", "source-title",
               "provenance", "retrieved", "text-sha256", "analysis")
PENDING_MAX_DAYS = 10


def check_notes() -> list[Finding]:
    out = []
    if not paths.SOURCES_DIR.exists():
        return out
    sys.path.insert(0, str(REPO)) if str(REPO) not in sys.path else None
    from vaultindex.corpus import split_frontmatter
    today = datetime.now().date()
    for p in sorted(paths.SOURCES_DIR.glob("*.md")):
        if p.name.startswith("_"):
            continue  # `_index.md` descreve a pasta, nao e fonte
        raw = p.read_text(encoding="utf-8", errors="replace")
        fm, _body, ok = split_frontmatter(raw)
        rel = str(p.relative_to(paths.VAULT))
        if not ok or not fm:
            out.append(Finding("notes", ERRO, "nota de fonte sem frontmatter",
                               where=rel, fix="regrave pelo CLI"))
            continue
        missing = [k for k in REQUIRED_FM if k not in fm]
        if missing:
            out.append(Finding("notes", ERRO,
                               "frontmatter incompleto: falta %s" % ", ".join(missing),
                               where=rel, fix="regrave pelo CLI"))
        if str(fm.get("source-kind")) not in note.KINDS:
            out.append(Finding("notes", ERRO,
                               "source-kind invalido: %r" % fm.get("source-kind"),
                               where=rel))
        if str(fm.get("provenance")) not in note.PROVENANCE:
            out.append(Finding("notes", ERRO,
                               "provenance invalida: %r" % fm.get("provenance"),
                               where=rel))
        if not str(fm.get("source-url", "")).startswith("http"):
            out.append(Finding("notes", ERRO, "fonte sem URL utilizavel",
                               "sem URL a afirmacao nao pode ser reverificada",
                               where=rel))
        try:
            doc = note.read_doc(p)
            if doc.text and doc.text_sha256 != str(fm.get("text-sha256", "")):
                out.append(Finding(
                    "notes", ERRO, "o texto bruto nao bate com o text-sha256",
                    "alguem editou a transcricao depois de gravada; a procedencia "
                    "deixou de valer", where=rel))
        except Exception as exc:
            out.append(Finding("notes", AVISO, "nao consegui reler a nota: %s"
                               % type(exc).__name__, where=rel))
        if str(fm.get("analysis")) == "pending":
            d = _fm_date(fm.get("date"))
            if d and (today - d).days > PENDING_MAX_DAYS:
                out.append(Finding(
                    "notes", AVISO,
                    "fonte sem analise ha %d dias" % (today - d).days,
                    "material bruto que ninguem processou e a mesma pilha de 'ler "
                    "depois' que o cano existe para evitar",
                    where=rel,
                    fix="python -m vaultsources analyse --list"))
    return out


def _fm_date(value) -> "datetime.date | None":
    try:
        if hasattr(value, "year"):
            return value if not hasattr(value, "date") else value.date()
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except Exception:
        return None


# ── 5. placeholders esquecidos no registro ────────────────────────────────────

PLACEHOLDER = re.compile(
    r"(\[data\]|\[nome\]|\[date\]|\[name\]|\bTBD\b|\bXXX\b|\{\{[^}]*\}\}|"
    r"lorem ipsum|<preencher>|<inserir>)", re.I)
SCAN_DIRS = ("Inbox", "Projects", "Areas", "Sources", "Concepts", "Daily")


def check_placeholders() -> list[Finding]:
    out = []
    for d in SCAN_DIRS:
        base = paths.VAULT / d
        if not base.exists():
            continue
        for p in base.rglob("*.md"):
            if any(part.startswith(("_", ".")) for part in p.relative_to(base).parts[:-1]):
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            hits = {m.group(0) for m in PLACEHOLDER.finditer(text)}
            if not hits:
                continue
            line = next((l.strip() for l in text.splitlines()
                         if PLACEHOLDER.search(l)), "")
            out.append(Finding(
                "placeholders", AVISO,
                "placeholder no registro: %s" % ", ".join(sorted(hits)[:3]),
                "linha: %s" % line[:160],
                where=str(p.relative_to(paths.VAULT)),
                fix="corrija a nota ou marque o trecho como nao processado"))
    return out[:40]


# ── 6. deps: o cano tem as pecas? ─────────────────────────────────────────────

def check_deps(online: bool = True) -> list[Finding]:
    out = []
    try:
        import yt_dlp  # noqa: F401
    except ImportError:
        out.append(Finding("deps", ERRO, "yt-dlp nao esta instalado como modulo",
                           "o .exe congelado ignora SSL_CERT_FILE e nao passa pela "
                           "CA da NETZSCH",
                           fix="python -m pip install -U yt-dlp"))
    try:
        import youtube_transcript_api as yta
        ver = getattr(yta, "__version__", "")
        del ver
    except ImportError:
        out.append(Finding("deps", ERRO, "youtube-transcript-api ausente",
                           fix="python -m pip install -U youtube-transcript-api"))
    try:
        import faster_whisper  # noqa: F401
    except ImportError:
        out.append(Finding("deps", AVISO, "faster-whisper ausente",
                           "video sem legenda deixa de ter caminho local",
                           fix="python -m pip install -U faster-whisper"))
    bundle = net.bundle_path()
    if not bundle.exists():
        out.append(Finding("deps", ERRO, "CA bundle da rede corporativa ausente",
                           "sem ele toda saida externa morre com "
                           "CERTIFICATE_VERIFY_FAILED",
                           where=str(bundle),
                           fix="pwsh -File scripts/build-ca-bundle.ps1"))
    elif online:
        net.apply(strict=False)
        ok, why = net.probe()
        if not ok:
            out.append(Finding("deps", ERRO, "o bundle existe mas a saida nao valida",
                               why, where=str(bundle),
                               fix="pwsh -File scripts/build-ca-bundle.ps1  "
                                   "(refazer depois de pip install -U certifi)"))
    return out


# ── 7. governance: o que pode sair, sai? ──────────────────────────────────────

def check_governance() -> list[Finding]:
    out = []
    src = (REPO / "vaultsources")
    used = set()
    for p in src.glob("*.py"):
        if p.name == "governance.py":
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        used |= set(re.findall(r'check_egress\(\s*"([^"]+)"', text))
    undeclared = sorted(used - set(governance.PURPOSES))
    for u in undeclared:
        out.append(Finding("governance", ERRO,
                           "purpose %r usado no codigo e nao declarado" % u,
                           where="vaultsources/governance.py",
                           fix="declare o purpose com o provedor explicito"))
    # Requisicao de rede sem guarda na mesma funcao.
    for p in src.glob("*.py"):
        if p.name in ("governance.py", "net.py", "qa.py"):
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"^def (\w+)\(.*?(?=^def |\Z)", text, re.S | re.M):
            body = m.group(0)
            touches_net = re.search(r"requests\.(get|post)|_ytdlp\(|subprocess\.run", body)
            if touches_net and "check_egress" not in body and "_run(" not in body:
                out.append(Finding(
                    "governance", AVISO,
                    "%s.%s faz rede sem declarar purpose" % (p.stem, m.group(1)),
                    "toda saida passa por check_egress antes do socket",
                    where="vaultsources/%s.py" % p.stem))
    # Pergunta sensivel nao pode virar query externa.
    try:
        from vaultsources import questions as Q
        leak = [q for q in Q.as_search_queries(50) if q.get("sensitive")]
        for q in leak:
            out.append(Finding("governance", ERRO,
                               "pergunta sensivel na fila de busca externa",
                               q["text"][:120], where=q.get("origin", "")))
    except Exception as exc:
        out.append(Finding("governance", AVISO,
                           "nao consegui checar o filtro de perguntas: %s" % exc))
    return out


# ── 8. inbox: captura parada ──────────────────────────────────────────────────

def check_inbox(max_age_days: int = 7) -> list[Finding]:
    inbox = paths.VAULT / "Inbox"
    if not inbox.exists():
        return []
    today = datetime.now().date()
    stale = []
    for p in inbox.glob("*.md"):
        head = p.read_text(encoding="utf-8", errors="replace")[:400]
        if "status: a-triar" not in head:
            continue
        m = re.search(r"^date:\s*(\d{4}-\d{2}-\d{2})", head, re.M)
        if not m:
            continue
        age = (today - datetime.strptime(m.group(1), "%Y-%m-%d").date()).days
        if age > max_age_days:
            stale.append((age, p.name))
    if not stale:
        return []
    stale.sort(reverse=True)
    return [Finding(
        "inbox", AVISO,
        "%d capturas esperando triagem ha mais de %d dias" % (len(stale), max_age_days),
        "mais antiga: %s (%d dias). A captura esta mais rapida que a triagem, "
        "entao o registro vai virando fila." % (stale[0][1], stale[0][0]),
        where="Inbox/", fix="rotina triagem-gravacoes (dias uteis 09:00)")]


# ── 9. duplicates ─────────────────────────────────────────────────────────────

# Nomes repetidos DE PROPOSITO. O padrao de 4 arquivos por pessoa
# (Overview/Playbook/Timeline/RiskMap) e o `charter.md` por OKR sao convencao
# declarada no `_CLAUDE.md`, nao descuido. Acusar os dois todo dia entrega um
# relatorio com 10 avisos que nunca vao ser resolvidos, e relatorio assim ensina
# a ignorar os outros oito.
CONVENTIONAL_NAMES = {
    "overview", "playbook", "timeline", "riskmap", "pdi", "okr", "1on1",
    "charter", "readme", "_index", "index",
}


def check_duplicates(threshold: int = 2) -> list[Finding]:
    """Nome repetido so vira achado quando alguem realmente escreveu `[[nome]]` sem
    caminho em algum lugar do vault.

    Sem esse filtro o check devolvia 10 avisos que nunca seriam resolvidos:
    `Overview`, `Playbook`, `RiskMap` e `Timeline` sao o padrao de 4 arquivos por
    pessoa, e `2026-08-22_semana-...` e a nota de timesheet de cada um dos 5 do
    time. Sao convencoes declaradas, nao colisoes. O problema real e outro e e
    especifico: o Kelvin escreveu `[[charter]]` e o link foi parar num dos 14.
    """
    from collections import defaultdict
    names = defaultdict(list)
    for p in paths.VAULT.rglob("*.md"):
        if any(part.startswith(".") for part in p.parts):
            continue
        if any(part in ("Archive", "rollback", "backup-notas-2026-09-02") for part in p.parts):
            continue  # copia arquivada duplica nome por definicao
        names[p.stem].append(p)

    dup = {s: h for s, h in names.items() if len(h) >= threshold}
    if not dup:
        return []

    # Quais desses stems aparecem como wikilink NU (sem barra) em algum lugar?
    # `_reports/` fica de fora ou o check se le: este proprio relatorio cita
    # `[[Overview]]` ao reportar que `[[Overview]]` e ambiguo. `Templates/` fica de
    # fora porque link nu ali e o token do modelo, nao uma referencia real. E a
    # mesma decisao que o lint do vault tomou em 2026-09-04.
    skip_scan = ("_reports", "Templates", "Archive", "rollback",
                 "backup-notas-2026-09-02")
    linked: dict[str, str] = {}
    for p in paths.VAULT.rglob("*.md"):
        if any(part.startswith(".") for part in p.parts):
            continue
        if any(part in skip_scan for part in p.parts):
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in re.finditer(r"\[\[([^\]|/\\#]+?)(?:\|[^\]]*)?\]\]", text):
            stem = m.group(1).strip()
            if stem in dup and stem not in linked:
                linked[stem] = str(p.relative_to(paths.VAULT))

    out = []
    for stem, where in sorted(linked.items(), key=lambda kv: -len(dup[kv[0]])):
        hits = dup[stem]
        out.append(Finding(
            "duplicates", AVISO,
            "`[[%s]]` e ambiguo: %d arquivos com esse nome" % (stem, len(hits)),
            "alguem escreveu o link sem caminho e o Obsidian resolve para um so; "
            "os outros %d ficam invisiveis a esse link" % (len(hits) - 1),
            where=where,
            fix="escreva o link com caminho ([[Pasta/%s]]) ou renomeie os arquivos" % stem))
    return out[:10]


# ── orquestracao ──────────────────────────────────────────────────────────────

CHECKS = {
    "refs": check_refs,
    "folders": check_folders,
    "deadloops": check_deadloops,
    "notes": check_notes,
    "placeholders": check_placeholders,
    "deps": check_deps,
    "governance": check_governance,
    "inbox": check_inbox,
    "duplicates": check_duplicates,
}


def run(only: list[str] | None = None, *, online: bool = True) -> list[Finding]:
    out: list[Finding] = []
    for name, fn in CHECKS.items():
        if only and name not in only:
            continue
        try:
            out += fn(online=online) if name == "deps" else fn()
        except Exception as exc:
            out.append(Finding(name, ERRO, "o proprio check quebrou: %s: %s"
                               % (type(exc).__name__, str(exc)[:200]),
                               "um check que estoura nao pode passar por 'nada a "
                               "reportar' (padrao 5)"))
    order = {ERRO: 0, AVISO: 1, INFO: 2}
    out.sort(key=lambda f: (order.get(f.severity, 3), f.check, f.title))
    return out


def render(findings: list[Finding]) -> str:
    now = datetime.now()
    erros = [f for f in findings if f.severity == ERRO]
    avisos = [f for f in findings if f.severity == AVISO]
    lines = [
        "---",
        "date: %s" % now.strftime("%Y-%m-%d"),
        "type: qa-report",
        "generated-by: python -m vaultsources qa",
        "tags: [sources-qa, generated]",
        "ai-first: true",
        "---",
        "",
        "# QA das fontes e da consistencia · %s" % now.strftime("%Y-%m-%d %H:%M"),
        "",
        "> Saida gerada. Rodar de novo sobrescreve. Nada aqui foi editado a mao.",
        "",
        "## For future Claude",
        "",
        "Relatorio deterministico sobre a coerencia entre o que os documentos deste "
        "ambiente afirmam e o que existe no disco. %d erro(s) e %d aviso(s) nesta "
        "execucao. Erro significa que alguma instrucao escrita esta mentindo ou que "
        "um dado gravado perdeu a procedencia." % (len(erros), len(avisos)),
        "",
        "| Severidade | Quantidade |",
        "|---|---|",
        "| erro | %d |" % len(erros),
        "| aviso | %d |" % len(avisos),
        "",
    ]
    for sev, group in ((ERRO, erros), (AVISO, avisos)):
        if not group:
            continue
        lines += ["## %s (%d)" % (sev.upper(), len(group)), ""]
        current = None
        for f in group:
            if f.check != current:
                current = f.check
                lines += ["### %s" % current, ""]
            lines.append("- **%s**" % f.title)
            if f.where:
                lines.append("  - onde: `%s`" % f.where)
            if f.detail:
                lines.append("  - %s" % f.detail)
            if f.fix:
                lines.append("  - conserto: `%s`" % f.fix)
        lines.append("")
    if not findings:
        lines += ["Nenhuma inconsistencia encontrada.", ""]
    return "\n".join(lines)


def write_report(findings: list[Finding]) -> Path:
    paths.ensure_dirs()
    paths.QA_REPORT.write_text(render(findings), encoding="utf-8")
    return paths.QA_REPORT


def summary(findings: list[Finding]) -> dict:
    by_check: dict[str, dict[str, int]] = {}
    for f in findings:
        by_check.setdefault(f.check, {}).setdefault(f.severity, 0)
        by_check[f.check][f.severity] += 1
    return {
        "erros": sum(1 for f in findings if f.severity == ERRO),
        "avisos": sum(1 for f in findings if f.severity == AVISO),
        "por_check": by_check,
        "gerado": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
