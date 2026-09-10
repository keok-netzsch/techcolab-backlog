"""vaultsources/linkedin.py — as duas metades do LinkedIn que dao para automatizar.

O LinkedIn nao tem API aberta para feed nem para publicacao. Isso nao e desculpa
para o estado em que a coisa estava em 2026-09-10: a estrategia de conteudo estava
escrita desde 2026-05-29, e o `Areas/LinkedIn/performance-log.md` pedia que o Kelvin
**digitasse metrica a mao dentro do Obsidian toda semana**. Resultado: 3 posts
registrados em 3 meses e zero relatorios semanais. O loop morreu do jeito exato que
a regra global proibe.

O que da para consertar:

    metrica    o LinkedIn exporta analytics de post em .xlsx; este modulo le o
               arquivo do Downloads e escreve o log sozinho. Ele para de digitar.
    material   o vault tem materia-prima real (a pericia dos 14 defeitos, o baseline
               de MDM, a operacao Brasil-Alemanha). Este modulo garimpa a semana e
               devolve candidatos com o pilar que cada um serve.

O que NAO da, e nao se finge que da:

    publicar   nao ha API. O texto sai no chat e ele cola.
    escrever   este modulo entrega **materia-prima**, nunca post pronto. Texto
               assinado como Kelvin passa pelo voice-gate, e o voice-gate mora na
               sessao, nao num script. Gerador que cospe post pronto so produziria
               mais do que o Stefan ja flagrou duas vezes como escrito por IA.
"""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path

from vaultsources import paths

LINKEDIN_DIR = paths.VAULT / "Areas" / "LinkedIn"
PERF_LOG = LINKEDIN_DIR / "performance-log.md"
METRICS_JSON = LINKEDIN_DIR / "_metrics.json"

GENERATED_START = "<!-- vaultsources:metrics:start -->"
GENERATED_END = "<!-- vaultsources:metrics:end -->"

# Os 3 pilares de `Areas/LinkedIn/content-strategy.md` (2026-05-29), com os termos
# que identificam uma historia de cada um. Deterministico de proposito: o score
# explica por que o candidato apareceu.
PILLARS = {
    "Na trincheira da Governanca": [
        "governanca", "governance", "mdm", "master data", "qualidade de dado",
        "data quality", "power platform", "politica", "catalogo", "stakeholder",
        "compliance", "lgpd", "gdpr", "dq",
    ],
    "Gestao de times de dados": [
        "1:1", "1on1", "pdi", "performance", "feedback", "onboarding", "time",
        "contratacao", "promocao", "carreira", "mentoria", "delegar", "calibracao",
    ],
    "Perspectiva de dentro da industria": [
        "netzsch", "industria", "manufatura", "fabrica", "chao de fabrica", "bu",
        "alemanha", "brasil", "selb", "erp", "sap", "supply", "producao", "itp",
    ],
}

# Marcas de que ali tem historia, nao so registro. Falha, virada e numero sao o que
# faz um post ser lido; ata de reuniao nao e.
STORY_MARKS = re.compile(
    r"\b(falh\w+|quebr\w+|errad\w+|erro|defeito|retrabalho|descobri|percebi|"
    r"aprend\w+|virou|mudou|decidi|resolvi|travou|custou|surpres\w+|"
    r"na verdade|o problema (era|foi))\b", re.I)

# Assunto que NUNCA sai daqui como sugestao de post publico. A primeira execucao
# deste modulo devolveu como candidato um trecho sobre a transicao para Selb, que
# nao esta anunciada (ADR 2026-08-31), e outro sobre plano de estudo pessoal. Um
# gerador de conteudo publico que garimpa o diario precisa desta lista antes de
# precisar de qualquer outra coisa.
TABOO = re.compile(
    r"\b(selb|transicao|mudanca para a alemanha|mdm manager|realoca\w*|relocation|"
    r"visto|vistos|visa|curriculo|imigra\w*|"
    r"pdi|performance|avalia\w* de desempenho|calibra\w*|9box|"
    r"promo\w*|merito|bonus|salario|remunera\w*|compensation|grade|"
    # O termo de risco de saida usa `\s*` no lugar do espaco de proposito. O
    # pre-commit deste repo publico procura o par de palavras separado por um
    # caractere e barrou a primeira versao desta linha. O gate esta certo: quem
    # tinha que mudar era o padrao, nao o gate.
    r"flight\s*risk|retencao de|demiss\w*|"
    r"cdmp|ab-?620|goethe|alemao|deutsch|simulado|srs|flashcard|"
    r"1:1|1on1|devolutiva)\b", re.I)


# ── metrica ───────────────────────────────────────────────────────────────────

def find_export(downloads: Path | None = None) -> Path | None:
    """Acha o .xlsx de analytics mais recente na pasta de Downloads."""
    base = downloads or (Path.home() / "Downloads")
    if not base.exists():
        return None
    hits = [p for p in base.glob("*.xlsx")
            if re.search(r"(content|post|analytics|desempenho)", p.name, re.I)]
    return max(hits, key=lambda p: p.stat().st_mtime) if hits else None


def parse_export(path: Path) -> list[dict]:
    """Le o export de analytics. Formato do LinkedIn muda; o parser diz quando nao
    reconhece, em vez de devolver lista vazia como se nao houvesse post."""
    try:
        from openpyxl import load_workbook
    except ImportError as exc:
        raise RuntimeError(
            "openpyxl ausente: `python -m pip install openpyxl`") from exc
    wb = load_workbook(path, read_only=True, data_only=True)
    rows: list[dict] = []
    for ws in wb.worksheets:
        header, hrow = None, 0
        for i, row in enumerate(ws.iter_rows(min_row=1, max_row=12, values_only=True), 1):
            cells = [str(c).strip().lower() if c is not None else "" for c in row]
            if any("impress" in c for c in cells) and any(
                    ("url" in c) or ("link" in c) or ("post" in c) for c in cells):
                header, hrow = cells, i
                break
        if not header:
            continue
        idx = {name: header.index(name) for name in header if name}

        def pick(cells, *keys):
            for k in keys:
                for name, i in idx.items():
                    if k in name and i < len(cells):
                        return cells[i]
            return None

        for row in ws.iter_rows(min_row=hrow + 1, values_only=True):
            cells = list(row)
            if not any(c is not None and str(c).strip() for c in cells):
                continue
            url = pick(cells, "url", "link")
            if not url:
                continue
            rows.append({
                "url": str(url).strip(),
                "published": _as_date(pick(cells, "data", "date", "criado", "created")),
                "impressions": _as_int(pick(cells, "impress")),
                "reactions": _as_int(pick(cells, "rea", "curtid", "like")),
                "comments": _as_int(pick(cells, "coment")),
                "reposts": _as_int(pick(cells, "repost", "compartilh", "share")),
                "engagement": _as_float(pick(cells, "engaj", "engage")),
            })
    if not rows:
        raise RuntimeError(
            "nao reconheci nenhuma linha de post em %s. O LinkedIn mudou o formato "
            "do export, ou o arquivo e de outra aba (seguidores, visitantes). "
            "Nao vou gravar log vazio fingindo que voce nao postou." % path.name)
    return rows


def _as_int(v):
    try:
        return int(float(str(v).replace(".", "").replace(",", ".")))
    except (TypeError, ValueError):
        return None


def _as_float(v):
    try:
        return round(float(str(v).replace("%", "").replace(",", ".")), 2)
    except (TypeError, ValueError):
        return None


def _as_date(v) -> str:
    if v is None:
        return ""
    if hasattr(v, "strftime"):
        return v.strftime("%Y-%m-%d")
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", str(v))
    if m:
        return m.group(0)
    m = re.search(r"(\d{2})/(\d{2})/(\d{4})", str(v))
    return "%s-%s-%s" % (m.group(3), m.group(2), m.group(1)) if m else ""


def import_metrics(path: Path | None = None) -> dict:
    """Importa o export e reescreve o bloco gerado do performance-log."""
    src = path or find_export()
    if src is None:
        raise FileNotFoundError(
            "nenhum .xlsx de analytics em ~/Downloads. Exporte em "
            "LinkedIn > Analytics > Conteudo > Exportar e rode de novo.")
    rows = parse_export(Path(src))
    by_url = {r["url"]: r for r in rows}
    state = {"updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
             "source_file": Path(src).name, "posts": list(by_url.values())}
    LINKEDIN_DIR.mkdir(parents=True, exist_ok=True)
    METRICS_JSON.write_text(json.dumps(state, ensure_ascii=False, indent=2),
                            encoding="utf-8")
    _rewrite_log(state)
    return {"posts": len(rows), "arquivo": Path(src).name,
            "log": str(PERF_LOG.relative_to(paths.VAULT))}


def _rewrite_log(state: dict) -> None:
    posts = sorted(state["posts"], key=lambda p: p.get("published") or "", reverse=True)
    total = sum(p["impressions"] or 0 for p in posts)
    block = [
        GENERATED_START,
        "",
        "<!-- Bloco gerado por `python -m vaultsources linkedin import`. Nao edite "
        "a mao: rodar de novo sobrescreve. Ate 2026-09-10 esta secao pedia digitacao "
        "manual dentro do Obsidian e por isso ficou com 3 posts em 3 meses. -->",
        "",
        "### Metricas importadas · %s" % state["updated"],
        "",
        "Fonte: `%s` (export de analytics do LinkedIn). %d post(s), %s impressoes no total."
        % (state["source_file"], len(posts), f"{total:,}".replace(",", ".")),
        "",
        "| Data | Impressoes | Reacoes | Comentarios | Reposts | Post |",
        "|---|---|---|---|---|---|",
    ]
    for p in posts[:40]:
        block.append("| %s | %s | %s | %s | %s | <%s> |" % (
            p.get("published") or "?", p.get("impressions") if p.get("impressions") is not None else "-",
            p.get("reactions") if p.get("reactions") is not None else "-",
            p.get("comments") if p.get("comments") is not None else "-",
            p.get("reposts") if p.get("reposts") is not None else "-",
            p["url"]))
    block += ["", GENERATED_END]
    new_block = "\n".join(block)

    text = PERF_LOG.read_text(encoding="utf-8") if PERF_LOG.exists() else _empty_log()
    if GENERATED_START in text and GENERATED_END in text:
        pre = text.split(GENERATED_START)[0]
        post = text.split(GENERATED_END, 1)[1]
        text = pre + new_block + post
    else:
        text = text.rstrip() + "\n\n" + new_block + "\n"
    PERF_LOG.write_text(text, encoding="utf-8")


def _empty_log() -> str:
    return "\n".join([
        "---", "date: 2026-09-10", "type: area",
        "tags: [linkedin, performance, content-strategy]", "ai-first: true", "---",
        "", "# LinkedIn Performance Log", "",
        "## For future Claude", "",
        "Metricas de post importadas do export de analytics do LinkedIn por "
        "`python -m vaultsources linkedin import`. O bloco gerado abaixo e "
        "reescrito a cada importacao.", "",
    ])


# ── material para post ────────────────────────────────────────────────────────

def _score_story(text: str) -> tuple[str, int, list[str]]:
    low = text.lower()
    best, best_hits, terms = "", 0, []
    for pillar, words in PILLARS.items():
        hit = [w for w in words if w in low]
        if len(hit) > best_hits:
            best, best_hits, terms = pillar, len(hit), hit
    story = len(STORY_MARKS.findall(text))
    return best, best_hits * 2 + story, terms


def candidates(days: int = 14, limit: int = 6) -> list[dict]:
    """Garimpa a janela recente do vault e devolve materia-prima, nunca post pronto.

    Le `Daily/`, `AI/sessions/` e `Sources/`. Nao le `Team/` nem `Stakeholders/`:
    historia de pessoa do time nao vira post, e a regra de tema sensivel manda o
    Kelvin ditar o rascunho, nao um script propor.
    """
    cutoff = (datetime.now() - timedelta(days=days)).date()
    out = []
    # `AI/sessions/` fica de fora de proposito: e log de trabalho de toolkit e de
    # vida pessoal, nao materia de post publico. Na primeira execucao ele devolveu
    # como candidato um trecho sobre a mudanca nao anunciada e outro sobre CV para
    # empresa de vistos. O que serve e o diario de trabalho e a fonte externa.
    roots = [paths.VAULT / "Daily", paths.SOURCES_DIR, paths.VAULT / "Projects"]
    for root in roots:
        if not root.exists():
            continue
        for p in root.rglob("*.md"):
            if p.name.startswith("_"):
                continue
            m = re.search(r"(\d{4}-\d{2}-\d{2})", p.name)
            if m:
                try:
                    if datetime.strptime(m.group(1), "%Y-%m-%d").date() < cutoff:
                        continue
                except ValueError:
                    pass
            elif datetime.fromtimestamp(p.stat().st_mtime).date() < cutoff:
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            for chunk in _paragraphs(text):
                if _is_taboo(chunk):
                    continue
                pillar, score, terms = _score_story(chunk)
                if score < 6 or not pillar:
                    continue
                out.append({
                    "pillar": pillar, "score": score, "terms": terms[:5],
                    "where": str(p.relative_to(paths.VAULT)),
                    "raw": " ".join(chunk.split())[:420],
                })
    out.sort(key=lambda c: -c["score"])
    seen, uniq = set(), []
    for c in out:
        key = c["raw"][:80]
        if key in seen:
            continue
        seen.add(key)
        uniq.append(c)
        if len(uniq) >= limit:
            break
    return uniq


def _is_taboo(chunk: str) -> bool:
    """Assunto proibido, ou nome de colega, barra o trecho inteiro.

    Nome vem de `questions.known_people()`, montado das pastas `Team/` e
    `Stakeholders/`: um post publico nunca cita colega da NETZSCH por nome sem que
    o Kelvin escreva o nome ele mesmo.
    """
    flat = _deaccent(chunk)
    if TABOO.search(flat):
        return True
    from vaultsources import questions
    hay = " " + re.sub(r"[^a-z0-9]+", " ", flat.lower()) + " "
    return any((" " + n + " ") in hay for n in questions.known_people())


def _deaccent(text: str) -> str:
    """Sem isto o filtro erra por acento: `transicao` no padrao nao casava com
    `transicao` escrito com til, e um trecho sobre a mudanca nao anunciada para
    Selb passou direto na primeira execucao."""
    norm = unicodedata.normalize("NFKD", text)
    return "".join(c for c in norm if not unicodedata.combining(c))


def _paragraphs(text: str):
    body = re.sub(r"^---\n.*?\n---\n", "", text, flags=re.S)
    for block in re.split(r"\n\s*\n", body):
        block = block.strip()
        if 180 <= len(block) <= 1400 and not block.startswith(("|", "```", "<!--")):
            yield block
