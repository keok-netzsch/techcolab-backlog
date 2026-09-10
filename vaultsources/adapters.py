"""vaultsources/adapters.py — um cano, quatro entradas.

A ideia inteira do pacote cabe nesta frase: **não são três integrações, é um cano
com adaptadores**. As duas peças caras já estavam na máquina antes de 2026-09-10
(`yt-dlp` em `~/.local/bin` e o Whisper local do call-recorder), então qualquer URL
de vídeo vira transcrição sem chave de API e sem o áudio sair do computador.

    youtube   legenda oficial via youtube-transcript-api; sem legenda, cai no vídeo
    video     yt-dlp baixa o áudio, faster-whisper transcreve aqui (TikTok, LinkedIn,
              Instagram, Vimeo — o que o yt-dlp resolver)
    article   página pública, texto extraído por regex conservadora
    clip      o Kelvin estava lendo algo no navegador e mandou clipar; o texto vem
              da sessão, não de um fetch nosso

Metadado de vídeo vem do próprio `yt-dlp --dump-json`, nunca da YouTube Data API:
o comando antigo pedia `YOUTUBE_API_KEY` e degradava em silêncio sem ela.

Toda função de rede declara `purpose` e passa por `governance.check_egress` antes
de tocar o socket.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from vaultsources import governance, net, paths
from vaultsources.note import SourceDoc

_CALL_RECORDER = Path(__file__).resolve().parent.parent / "call-recorder"

YOUTUBE_ID_RE = re.compile(
    r"(?:youtu\.be/|youtube\.com/(?:watch\?(?:.*&)?v=|shorts/|embed/|live/))([A-Za-z0-9_-]{11})"
)


class FetchError(RuntimeError):
    """A fonte não pôde ser buscada. Sempre com o motivo real, nunca genérico."""


# ── infra ─────────────────────────────────────────────────────────────────────

def ytdlp_bin() -> str:
    """Mantido so para diagnostico. O caminho de execucao usa net.ytdlp_argv()."""
    found = shutil.which("yt-dlp")
    if found:
        return found
    local = Path.home() / ".local" / "bin" / "yt-dlp"
    for candidate in (local, local.with_suffix(".exe")):
        if candidate.exists():
            return str(candidate)
    raise FetchError(
        "yt-dlp nao encontrado no PATH nem em ~/.local/bin. "
        "Instale com `python -m pip install -U yt-dlp` (o modulo, nao o .exe: o "
        "executavel congelado ignora SSL_CERT_FILE e nao passa pela CA da NETZSCH)."
    )


def _ytdlp(args: list[str], *, timeout: int = 600) -> subprocess.CompletedProcess:
    net.apply(strict=True)
    return _run(net.ytdlp_argv(args), timeout=timeout)


def _run(cmd: list[str], *, timeout: int = 600) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


def probe(url: str) -> dict:
    """Metadado público do vídeo pelo próprio yt-dlp. Sem API key, sem degradar mudo."""
    governance.check_egress("media-download", "public")
    proc = _ytdlp(["--dump-json", "--no-playlist", "--skip-download", url], timeout=120)
    if proc.returncode != 0 or not proc.stdout.strip():
        raise FetchError("yt-dlp nao leu o metadado de %s: %s"
                         % (url, (proc.stderr or "").strip()[:400]))
    return json.loads(proc.stdout.splitlines()[0])


def search_youtube(query: str, n: int = 3) -> list[dict]:
    """Busca no YouTube pelo proprio yt-dlp (`ytsearch`), sem Data API key.

    E o que permite o tester ir buscar material real a partir de uma pergunta
    aberta do Kelvin, em vez de ensaiar com fixture inventada.
    """
    governance.check_egress("feed-poll", "public")
    proc = _ytdlp(["--dump-json", "--skip-download", "--flat-playlist",
                   "ytsearch%d:%s" % (n, query)], timeout=180)
    out = []
    for line in (proc.stdout or "").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not d.get("id"):
            continue
        out.append({
            "video_id": d["id"],
            "title": (d.get("title") or "").strip(),
            "channel": (d.get("channel") or d.get("uploader") or "").strip(),
            "url": "https://www.youtube.com/watch?v=" + d["id"],
            "duration": d.get("duration"),
            "description": (d.get("description") or "")[:400],
            "published": "",
        })
    if not out and proc.returncode != 0:
        raise FetchError("busca no YouTube falhou: %s"
                         % (proc.stderr or "").strip()[:300])
    return out


def _upload_date(meta: dict) -> str:
    raw = str(meta.get("upload_date") or "")
    if len(raw) == 8 and raw.isdigit():
        return "%s-%s-%s" % (raw[0:4], raw[4:6], raw[6:8])
    return ""


def _whisper(audio: Path, language: str | None = None) -> tuple[str, str]:
    """Transcreve local reusando a função do call-recorder (padrão 7: fonte única)."""
    governance.check_egress("media-transcribe", "public")
    if str(_CALL_RECORDER) not in sys.path:
        sys.path.insert(0, str(_CALL_RECORDER))
    try:
        import record  # noqa: PLC0415
    except Exception as exc:  # pragma: no cover - ambiente sem call-recorder
        raise FetchError("nao consegui importar call-recorder/record.py: %s" % exc) from exc
    return record.transcribe(str(audio), language=language)


# ── youtube ───────────────────────────────────────────────────────────────────

def youtube_id(url_or_id: str) -> str:
    s = (url_or_id or "").strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", s):
        return s
    m = YOUTUBE_ID_RE.search(s)
    if not m:
        raise FetchError("nao achei um video id de 11 caracteres em %r" % url_or_id)
    return m.group(1)


def youtube_captions(video_id: str, langs=("pt", "pt-BR", "en", "de")) -> tuple[str, str] | None:
    """Legenda publicada pelo canal. Devolve (texto, idioma) ou None se não houver."""
    governance.check_egress("transcript-fetch", "public")
    net.apply(strict=False)
    try:
        from youtube_transcript_api import YouTubeTranscriptApi  # noqa: PLC0415
    except ImportError:
        return None
    try:
        api = YouTubeTranscriptApi()
        fetched = api.fetch(video_id, languages=list(langs))
        snippets = getattr(fetched, "snippets", fetched)
        lang = getattr(fetched, "language_code", "") or ""
    except Exception as exc:
        try:  # API antiga (<= 0.6): função de classe, lista de dicts, sem idioma
            rows = YouTubeTranscriptApi.get_transcript(video_id, languages=list(langs))
            snippets, lang = rows, ""
        except Exception as exc2:
            # "este video nao tem legenda" e uma resposta. Qualquer outra coisa e
            # falha nossa e nao pode virar um fallback silencioso de 15 min de
            # Whisper (padrao 5: erro tem que parecer erro). Foi o que aconteceu
            # em 2026-09-10: a lib 1.0.3 devolvia ParseError e o codigo lia como
            # "sem legenda".
            name = type(exc2).__name__
            if name in ("NoTranscriptFound", "TranscriptsDisabled",
                        "VideoUnavailable", "NotTranslatable"):
                return None
            raise FetchError(
                "a busca de legenda de %s falhou por motivo tecnico (%s: %s). "
                "Nao vou cair no Whisper em silencio: conserte a causa ou peca "
                "--force-whisper explicitamente."
                % (video_id, name, str(exc2)[:200])
            ) from exc
    lines = []
    for s in snippets:
        start = getattr(s, "start", None)
        text = getattr(s, "text", None)
        if start is None and isinstance(s, dict):
            start, text = s.get("start", 0.0), s.get("text", "")
        text = (text or "").strip()
        if not text:
            continue  # legenda tem linha vazia de sobra; timestamp sozinho nao e conteudo
        lines.append("[%05.1fs] %s" % (float(start or 0.0), text))
    body = "\n".join(lines)
    return (body, lang) if body.strip() else None


def from_youtube(url_or_id: str, *, question: str = "", force_whisper: bool = False) -> SourceDoc:
    vid = youtube_id(url_or_id)
    url = "https://www.youtube.com/watch?v=" + vid
    meta = probe(url)
    text, lang, prov = "", "", "yt-dlp+whisper"
    if not force_whisper:
        cap = youtube_captions(vid)
        if cap:
            text, lang = cap
            prov = "youtube-transcript-api"
    if not text:
        audio = download_audio(url, vid)
        text, lang = _whisper(audio)
        prov = "yt-dlp+whisper"
    return SourceDoc(
        kind="youtube",
        url=url,
        title=str(meta.get("title") or vid),
        author=str(meta.get("uploader") or meta.get("channel") or ""),
        published=_upload_date(meta),
        lang=lang or str(meta.get("language") or ""),
        duration_seconds=int(meta["duration"]) if meta.get("duration") else None,
        provenance=prov,
        text=text,
        external_id=vid,
        pulled_by_question=question,
        tags=[t.lower() for t in (meta.get("tags") or [])[:6]],
    )


# ── vídeo genérico (TikTok, LinkedIn, Instagram, Vimeo…) ──────────────────────

def download_audio(url: str, stem: str) -> Path:
    governance.check_egress("media-download", "public")
    outdir = paths.media_cache()
    outdir.mkdir(parents=True, exist_ok=True)
    template = str(outdir / (stem + ".%(ext)s"))
    proc = _ytdlp(["-f", "bestaudio/best", "-x", "--audio-format", "m4a",
                   "--no-playlist", "-o", template, url], timeout=900)
    hits = sorted(outdir.glob(stem + ".*"))
    if proc.returncode != 0 and not hits:
        raise FetchError("yt-dlp falhou ao baixar audio de %s: %s"
                         % (url, (proc.stderr or "").strip()[:400]))
    if not hits:
        raise FetchError("yt-dlp terminou sem erro mas nao produziu arquivo para %s" % url)
    return hits[0]


def from_video(url: str, *, question: str = "") -> SourceDoc:
    """Qualquer vídeo que o yt-dlp resolva. TikTok entra por aqui."""
    meta = probe(url)
    vid = str(meta.get("id") or re.sub(r"\W+", "-", url)[-40:])
    audio = download_audio(url, vid)
    text, lang = _whisper(audio)
    desc = str(meta.get("description") or "").strip()
    if desc:
        text = "[descricao do post]\n" + desc + "\n\n[transcricao do audio]\n" + text
    return SourceDoc(
        kind="video",
        url=str(meta.get("webpage_url") or url),
        title=str(meta.get("title") or meta.get("fulltitle") or vid),
        author=str(meta.get("uploader") or meta.get("channel") or ""),
        published=_upload_date(meta),
        lang=lang,
        duration_seconds=int(meta["duration"]) if meta.get("duration") else None,
        provenance="yt-dlp+whisper",
        text=text,
        external_id=vid,
        pulled_by_question=question,
        tags=[str(meta.get("extractor_key") or "").lower()],
    )


# ── artigo web ────────────────────────────────────────────────────────────────

_TAG_STRIP = re.compile(r"<(script|style|nav|footer|header|aside)[^>]*>.*?</\1>", re.S | re.I)
_TAGS = re.compile(r"<[^>]+>")
_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)
_META_AUTHOR = re.compile(r'<meta[^>]+name=["\']author["\'][^>]+content=["\']([^"\']+)', re.I)
_META_DATE = re.compile(r'<meta[^>]+(?:property|name)=["\'][^"\']*(?:published_time|date)["\']'
                        r'[^>]+content=["\'](\d{4}-\d{2}-\d{2})', re.I)


def from_web(url: str, *, question: str = "") -> SourceDoc:
    governance.check_egress("web-fetch", "public")
    net.apply(strict=False)
    import requests  # noqa: PLC0415
    resp = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0 vaultsources"})
    resp.raise_for_status()
    html = resp.text
    title_m = _TITLE.search(html)
    body = _TAG_STRIP.sub(" ", html)
    body = _TAGS.sub(" ", body)
    body = re.sub(r"&nbsp;?", " ", body)
    body = re.sub(r"[ \t]+", " ", body)
    body = re.sub(r"\n\s*\n\s*\n+", "\n\n", body).strip()
    author_m = _META_AUTHOR.search(html)
    date_m = _META_DATE.search(html)
    return SourceDoc(
        kind="article",
        url=url,
        title=(title_m.group(1).strip() if title_m else url)[:200],
        author=(author_m.group(1).strip() if author_m else ""),
        published=(date_m.group(1) if date_m else ""),
        lang="",
        provenance="web-fetch",
        text=body,
        external_id="",
        pulled_by_question=question,
    )


# ── clip de navegador (LinkedIn, qualquer página logada) ──────────────────────

def from_clip(*, url: str, title: str, text: str, author: str = "",
              published: str = "", question: str = "", kind: str = "post") -> SourceDoc:
    """O texto vem da sessão que estava lendo a página, não de um fetch nosso.

    É o único caminho para LinkedIn: não há API aberta para post e feed, e raspar
    página logada por script quebra a cada release deles. O navegador já está
    autenticado e o Kelvin já está lendo — a nota nasce dali.
    """
    if not text.strip():
        raise FetchError("clip sem texto: nao adianta gravar a casca")
    return SourceDoc(
        kind=kind,
        url=url,
        title=title or url,
        author=author,
        published=published,
        lang="",
        provenance="browser-clip",
        text=text.strip(),
        external_id="",
        pulled_by_question=question,
    )


# ── despacho por URL ──────────────────────────────────────────────────────────

def fetch(url: str, *, question: str = "") -> SourceDoc:
    """Escolhe o adaptador pela URL. É o que o `/source` chama."""
    u = url.strip()
    if YOUTUBE_ID_RE.search(u) or re.fullmatch(r"[A-Za-z0-9_-]{11}", u):
        return from_youtube(u, question=question)
    if re.search(r"(tiktok\.com|instagram\.com/(reel|p)/|vimeo\.com|twitter\.com/\w+/status|x\.com/\w+/status)", u, re.I):
        return from_video(u, question=question)
    if re.search(r"linkedin\.com", u, re.I):
        raise FetchError(
            "LinkedIn nao tem caminho de fetch: nao ha API aberta e raspar pagina "
            "logada quebra a cada release deles. Use o clip do navegador "
            "(`python -m vaultsources clip --url ... --title ... --text-file ...`), "
            "que e como o post entra sem fingir que foi buscado."
        )
    return from_web(u, question=question)
