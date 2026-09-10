"""vaultsources/note.py — a nota de fonte, escrita por código.

Divisão de trabalho (padrão 4, determinismo onde a verdade importa):

* **Código escreve a procedência** — URL, autor, data de publicação, como o texto
  chegou aqui (legenda oficial? whisper local?), quando foi buscado, o hash do
  texto. Nada disso passa por modelo.
* **Modelo propõe a análise** — TL;DR, tese, afirmações datadas, o que muda no
  vault. Entra depois, por `complete()`, e fica marcado como proposta.

Uma nota recém-buscada nasce com `analysis: pending`. O QA acusa nota que ficou
pendente por mais de N dias, porque proposta que ninguém completa é loop morto —
foi assim que o `performance-log.md` do LinkedIn passou 3 meses com 3 posts.
"""

from __future__ import annotations

import hashlib
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from vaultsources import paths

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from vaultindex.corpus import split_frontmatter  # noqa: E402

KINDS = ("youtube", "video", "article", "post", "clip")
PROVENANCE = (
    "youtube-transcript-api",   # legenda publicada pelo canal
    "yt-dlp+whisper",           # áudio baixado, transcrito nesta máquina
    "web-fetch",                # texto da página
    "browser-clip",             # o Kelvin estava lendo e mandou clipar
    "manual",                   # digitado
)
ANALYSIS_STATES = ("pending", "proposed", "accepted")

MAX_INLINE_TRANSCRIPT = 4000  # acima disso o texto vai para o sidecar

PENDING_MARK = "<!-- pending-analysis -->"

# Sentinela do inicio do texto bruto no sidecar. Sem ela o parse quebrava: o
# separador de tres tracos que eu usava tambem fecha o frontmatter, entao o split
# pegava a primeira ocorrencia e devolvia o cabecalho junto com a transcricao — e
# o text-sha256 nunca mais batia com o proprio texto. O QA achou isto na primeira
# execucao, na unica nota que existia.
TRANSCRIPT_MARK = "<!-- transcript -->"


def slugify(text: str, max_len: int = 60) -> str:
    norm = unicodedata.normalize("NFKD", text or "")
    norm = "".join(c for c in norm if not unicodedata.combining(c))
    norm = re.sub(r"[^A-Za-z0-9]+", "-", norm).strip("-").lower()
    return (norm[:max_len].rstrip("-")) or "sem-titulo"


def _yaml_str(value) -> str:
    """Escapa string para YAML de uma linha. Título de vídeo tem de tudo."""
    if value is None:
        return '""'
    s = str(value).replace("\\", "\\\\").replace('"', '\\"')
    s = s.replace("\n", " ").replace("\r", " ")
    return '"' + s + '"'


@dataclass
class SourceDoc:
    """Tudo o que o código sabe sobre a fonte antes de qualquer modelo olhar."""

    kind: str
    url: str
    title: str
    author: str = ""
    published: str = ""           # YYYY-MM-DD, ou "" quando a origem não diz
    lang: str = ""
    duration_seconds: int | None = None
    provenance: str = "manual"
    text: str = ""                # transcrição ou corpo do artigo
    external_id: str = ""         # video id, post id
    pulled_by_question: str = ""  # a pergunta aberta que puxou esta fonte
    tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError("kind %r fora de %s" % (self.kind, KINDS))
        if self.provenance not in PROVENANCE:
            raise ValueError("provenance %r fora de %s" % (self.provenance, PROVENANCE))
        if not self.url:
            raise ValueError("fonte sem URL nao entra: sem URL nao da para reverificar")
        if not self.title:
            raise ValueError("fonte sem titulo nao entra")
        # Canonicaliza antes de qualquer hash. O sidecar grava `text.strip()`, e
        # sem isto o sha do objeto em memoria e o do texto relido divergiam por
        # um `\n` no fim — o campo de procedencia acusaria adulteracao que nunca
        # houve, que e a pior forma de alarme falso.
        self.text = (self.text or "").strip()

    @property
    def text_sha256(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()

    @property
    def slug(self) -> str:
        stamp = (self.published or datetime.now(timezone.utc).strftime("%Y-%m-%d"))[:10]
        return stamp + "-" + slugify(self.title)


def note_path(doc: SourceDoc) -> Path:
    return paths.SOURCES_DIR / (doc.slug + ".md")


def transcript_path(doc: SourceDoc) -> Path:
    return paths.SOURCES_DIR / "_transcripts" / (doc.slug + ".md")


def find_by_url(url: str) -> Path | None:
    """Ja ingerimos esta URL? Evita a segunda copia da mesma fonte."""
    if not paths.SOURCES_DIR.exists():
        return None
    needle = "source-url: " + url
    for p in paths.SOURCES_DIR.glob("*.md"):
        try:
            head = p.read_text(encoding="utf-8", errors="replace")[:2000]
        except OSError:
            continue
        if needle in head:
            return p
    return None


def render(doc: SourceDoc, *, analysis: dict | None = None) -> tuple[str, str | None]:
    """Devolve (markdown da nota, markdown do sidecar de transcricao ou None)."""
    now = datetime.now().astimezone()
    a = analysis or {}
    state = a.get("state", "pending")
    if state not in ANALYSIS_STATES:
        raise ValueError("analysis.state %r fora de %s" % (state, ANALYSIS_STATES))

    inline = len(doc.text) <= MAX_INLINE_TRANSCRIPT
    # Secao vazia com a analise ja aplicada nao pode reusar a marca de pendencia:
    # o frontmatter diria `analysis: proposed` e o corpo diria pendente, e o QA
    # (com razao) leria como analise esquecida.
    empty = PENDING_MARK if state == "pending" else "_Nada identificado._"
    sidecar_md = None
    tags = sorted({"source", doc.kind} | {t.lower() for t in doc.tags})
    dur = doc.duration_seconds if doc.duration_seconds is not None else "null"

    fm = [
        "---",
        "date: " + now.strftime("%Y-%m-%d"),
        "type: source",
        "source-kind: " + doc.kind,
        "source-url: " + doc.url,
        "source-title: " + _yaml_str(doc.title),
        "source-author: " + _yaml_str(doc.author),
        "source-published: " + (doc.published or "unknown"),
        "source-id: " + _yaml_str(doc.external_id),
        "provenance: " + doc.provenance,
        "retrieved: " + now.strftime("%Y-%m-%dT%H:%M%z"),
        "text-sha256: " + doc.text_sha256,
        "text-chars: " + str(len(doc.text)),
        "lang: " + (doc.lang or "unknown"),
        "duration-seconds: " + str(dur),
        "analysis: " + state,
        "pulled-by-question: " + _yaml_str(doc.pulled_by_question),
        "tags: [" + ", ".join(tags) + "]",
        "ai-first: true",
        "---",
        "",
    ]

    body = ["# " + doc.title, "", "## For future Claude", ""]
    if a.get("for_future_claude"):
        body += [a["for_future_claude"], ""]
    else:
        onde = "nesta nota" if inline else "no sidecar de transcricao"
        body += [
            "Fonte externa (" + doc.kind + ") trazida para o vault em "
            + now.strftime("%Y-%m-%d") + " e ainda **sem analise**. O texto bruto esta "
            + onde + ". Enquanto `analysis: pending`, trate o conteudo como material "
            "bruto: nada aqui foi verificado nem confrontado com o que o vault ja diz.",
            "",
        ]

    body += ["## Por que isto entrou", ""]
    body += [doc.pulled_by_question
             or "_Captura avulsa: nenhuma pergunta aberta puxou esta fonte._", ""]

    body += ["## Procedencia", ""]
    body += [
        "| Campo | Valor |",
        "|---|---|",
        "| URL | <" + doc.url + "> |",
        "| Autor | " + (doc.author or "nao informado") + " |",
        "| Publicado | " + (doc.published or "nao informado") + " |",
        "| Como o texto chegou | `" + doc.provenance + "` |",
        "| Buscado em | " + now.strftime("%Y-%m-%d %H:%M") + " |",
        "| Tamanho | " + str(len(doc.text)) + " caracteres |",
        "",
    ]

    body += ["## Tese central", "", a.get("thesis") or empty, ""]

    body += ["## Afirmacoes (com data e fonte)", ""]
    claims = a.get("claims") or []
    if claims:
        for c in claims:
            conf = c.get("confidence", "medium")
            as_of = c.get("as_of", doc.published or "unknown")
            src = c.get("source", doc.url)
            body.append("- " + c["text"] + " (as of " + as_of + ", <" + src + ">) "
                        + "`confidence: " + conf + "`")
    else:
        body.append(empty)
    body.append("")

    body += ["## O que isto muda no vault", ""]
    impacts = a.get("impacts") or []
    if impacts:
        for i in impacts:
            body.append("- `" + i.get("relation", "adiciona") + "` [[" + i["target"]
                        + "]] — " + i.get("note", ""))
    else:
        body.append(empty)
    body.append("")

    if inline and doc.text:
        body += ["## Texto bruto", "", "```text", doc.text.strip(), "```", ""]
    elif doc.text:
        body += [
            "## Texto bruto", "",
            "Sidecar: [[Sources/_transcripts/" + doc.slug + "]] ("
            + str(len(doc.text)) + " caracteres, acima do limite de "
            + str(MAX_INLINE_TRANSCRIPT) + " para nota inline).",
            "",
        ]
        sidecar_md = "\n".join([
            "---",
            "date: " + now.strftime("%Y-%m-%d"),
            "type: source-transcript",
            "source-url: " + doc.url,
            "source-note: " + _yaml_str(doc.slug),
            "provenance: " + doc.provenance,
            "text-sha256: " + doc.text_sha256,
            "lang: " + (doc.lang or "unknown"),
            "tags: [source, transcript]",
            "ai-first: true",
            "---",
            "",
            "# Transcricao — " + doc.title,
            "",
            "## For future Claude",
            "",
            "Texto bruto da fonte [[Sources/" + doc.slug + "]]. Nao foi editado nem "
            "resumido. Origem: `" + doc.provenance + "`. A analise mora na nota "
            "principal, nao aqui.",
            "",
            "---",
            "",
            TRANSCRIPT_MARK,
            "",
            doc.text.strip(),
            "",
        ])

    return "\n".join(fm + body), sidecar_md


def write(doc: SourceDoc, *, analysis: dict | None = None, overwrite: bool = False) -> Path:
    paths.ensure_dirs()
    (paths.SOURCES_DIR / "_transcripts").mkdir(parents=True, exist_ok=True)
    target = note_path(doc)
    if target.exists() and not overwrite:
        raise FileExistsError(str(target) + " ja existe (use overwrite=True)")
    md, sidecar = render(doc, analysis=analysis)
    target.write_text(md, encoding="utf-8")
    if sidecar:
        transcript_path(doc).write_text(sidecar, encoding="utf-8")
    return target


def read_doc(path: Path) -> SourceDoc:
    """Reconstroi o SourceDoc a partir da nota gravada."""
    raw = path.read_text(encoding="utf-8")
    fm, _body, _ = split_frontmatter(raw)
    text = ""
    m = re.search(r"## Texto bruto\n\n```text\n(.*?)\n```", raw, re.S)
    if m:
        text = m.group(1)
    else:
        sidecar = paths.SOURCES_DIR / "_transcripts" / (path.stem + ".md")
        if sidecar.exists():
            sraw = sidecar.read_text(encoding="utf-8")
            if TRANSCRIPT_MARK in sraw:
                text = sraw.split(TRANSCRIPT_MARK, 1)[1].strip()
            else:
                text = ""  # sidecar antigo, sem sentinela: nao adivinhe onde comeca
    dur = fm.get("duration-seconds")
    published = str(fm.get("source-published", "") or "")
    lang = str(fm.get("lang", "") or "")
    return SourceDoc(
        kind=str(fm.get("source-kind", "article")),
        url=str(fm.get("source-url", "")),
        title=str(fm.get("source-title", path.stem)),
        author=str(fm.get("source-author", "") or ""),
        published=("" if published == "unknown" else published),
        lang=("" if lang == "unknown" else lang),
        duration_seconds=(int(dur) if isinstance(dur, int) else None),
        provenance=str(fm.get("provenance", "manual")),
        text=text,
        external_id=str(fm.get("source-id", "") or ""),
        pulled_by_question=str(fm.get("pulled-by-question", "") or ""),
        tags=[t for t in (fm.get("tags") or []) if t != "source"],
    )


def complete(path: Path, analysis: dict) -> Path:
    """Preenche a analise de uma nota ja buscada, sem tocar na procedencia.

    Reconstroi o SourceDoc a partir do frontmatter e do texto guardado, de modo
    que o `text-sha256` continue batendo: se a analise pudesse reescrever o texto,
    o hash deixaria de valer alguma coisa.
    """
    doc = read_doc(path)
    before = doc.text_sha256
    analysis = dict(analysis)
    analysis.setdefault("state", "proposed")
    md, sidecar = render(doc, analysis=analysis)
    path.write_text(md, encoding="utf-8")
    if sidecar:
        transcript_path(doc).write_text(sidecar, encoding="utf-8")
    after = read_doc(path).text_sha256
    if before != after:
        raise RuntimeError(
            "complete() alterou o texto bruto (sha %s -> %s). "
            "A analise nao pode mexer na procedencia." % (before[:12], after[:12])
        )
    return path
