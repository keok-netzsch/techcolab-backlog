"""vaultsources/feeds.py — assinatura de canal e playlist, sem chave de API.

Todo canal do YouTube publica Atom em `feeds/videos.xml?channel_id=UC...`, e toda
playlist em `?playlist_id=PL...`. Isso resolve a porta que importa: o Kelvin salva
um video na playlist pelo celular, a rotina da noite ve o item novo e de manha
propoe no chat. Nada de "abrir o Obsidian e marcar" (padrao 1).

O ranking e deterministico e sem LLM de proposito. Codigo propoe candidato; quem
decide o que entra e o Kelvin, em uma linha no chat (padrao 3: silencio nao e
consentimento). Um score que dependesse de modelo escondia a razao da escolha.

Estado (um escritor: este modulo, chamado pelo CLI):
    Sources/_watchlist.json   canais e playlists assinados
    Sources/_queue.json       candidatos propostos e o que aconteceu com cada um
"""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

from vaultsources import governance, net, paths

ATOM = "{http://www.w3.org/2005/Atom}"
YT = "{http://www.youtube.com/xml/schemas/2015}"
MEDIA = "{http://search.yahoo.com/mrss/}"

CHANNEL_FEED = "https://www.youtube.com/feeds/videos.xml?channel_id=%s"
PLAYLIST_FEED = "https://www.youtube.com/feeds/videos.xml?playlist_id=%s"

STATES = ("proposed", "approved", "rejected", "ingested", "failed")


# ── estado ────────────────────────────────────────────────────────────────────

def _load(path: Path, default: dict) -> dict:
    if not path.exists():
        return dict(default)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError("%s esta corrompido (%s). Nao vou sobrescrever em cima: "
                           "conserte ou apague o arquivo." % (path, exc)) from exc


def _save(path: Path, data: dict) -> None:
    paths.ensure_dirs()
    data["updated"] = datetime.now().astimezone().isoformat(timespec="seconds")
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def load_watchlist() -> dict:
    return _load(paths.WATCHLIST, {"version": 1, "feeds": [], "seen": {}})


def save_watchlist(data: dict) -> None:
    _save(paths.WATCHLIST, data)


def load_queue() -> dict:
    return _load(paths.QUEUE, {"version": 1, "candidates": []})


def save_queue(data: dict) -> None:
    _save(paths.QUEUE, data)


# ── assinatura ────────────────────────────────────────────────────────────────

def add_feed(ref: str, *, label: str = "", topics: list[str] | None = None,
             validate: bool = True) -> dict:
    """Assina um feed. Valida ANTES de gravar, a nao ser que peca o contrario.

    Assinar sem validar cria um feed morto que so aparece como erro no poll da
    semana seguinte. O custo de errar aqui e uma requisicao; o de nao checar e uma
    semana de silencio parecendo normalidade.
    """
    kind = "playlist" if ref.startswith(("PL", "UU", "LL", "FL")) else "channel"
    data = load_watchlist()
    if any(f["ref"] == ref for f in data["feeds"]):
        raise ValueError("feed %s ja esta na watchlist" % ref)
    if validate:
        probe = {"ref": ref, "kind": kind, "label": label or ref, "topics": []}
        itens = poll(probe)   # levanta FeedUnavailable com o diagnostico
        if not itens:
            raise FeedUnavailable("feed %s respondeu vazio" % ref)
    entry = {
        "ref": ref,
        "kind": kind,
        "label": label or ref,
        "topics": [t.lower() for t in (topics or [])],
        "added": datetime.now().strftime("%Y-%m-%d"),
        "last_poll": "",
        "last_error": "",
    }
    data["feeds"].append(entry)
    save_watchlist(data)
    return entry


def remove_feed(ref: str) -> bool:
    data = load_watchlist()
    before = len(data["feeds"])
    data["feeds"] = [f for f in data["feeds"] if f["ref"] != ref]
    save_watchlist(data)
    return len(data["feeds"]) < before


def feed_url(entry: dict) -> str:
    return (PLAYLIST_FEED if entry["kind"] == "playlist" else CHANNEL_FEED) % entry["ref"]


def resolve_channel_id(url: str) -> str:
    """De uma URL de canal (@handle, /c/, /user/) para o UC... que o RSS quer."""
    governance.check_egress("feed-poll", "public")
    net.apply(strict=False)
    import requests
    m = re.search(r"(UC[A-Za-z0-9_-]{22})", url)
    if m:
        return m.group(1)
    resp = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0 vaultsources"})
    resp.raise_for_status()
    m = re.search(r'"(?:channelId|externalId)"\s*:\s*"(UC[A-Za-z0-9_-]{22})"', resp.text)
    if not m:
        m = re.search(r"(UC[A-Za-z0-9_-]{22})", resp.text)
    if not m:
        raise ValueError("nao achei channel_id em %s" % url)
    return m.group(1)


# ── poll ──────────────────────────────────────────────────────────────────────

def parse_feed(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    out = []
    for e in root.findall(ATOM + "entry"):
        vid = (e.findtext(YT + "videoId") or "").strip()
        if not vid:
            continue
        group = e.find(MEDIA + "group")
        desc = (group.findtext(MEDIA + "description") if group is not None else "") or ""
        out.append({
            "video_id": vid,
            "title": (e.findtext(ATOM + "title") or "").strip(),
            "url": "https://www.youtube.com/watch?v=" + vid,
            "channel": (e.findtext(ATOM + "author/" + ATOM + "name") or "").strip(),
            "published": (e.findtext(ATOM + "published") or "")[:10],
            "description": desc.strip(),
        })
    return out


class FeedUnavailable(RuntimeError):
    """O feed nao respondeu, e a mensagem diz o motivo provavel."""


def poll(entry: dict, *, timeout: int = 30) -> list[dict]:
    """Itens do feed. Tenta RSS; se falhar, tenta o yt-dlp antes de desistir.

    O RSS do YouTube so serve playlist publica ou nao listada. Playlist PRIVADA
    responde 404 no feed e "The playlist does not exist" no yt-dlp — que e a mesma
    resposta que um id errado, entao o erro precisa dizer as duas hipoteses em vez
    de acusar so uma. Foi o caso de 2026-09-10: o Kelvin mandou o link tres vezes,
    sempre com o mesmo id, e o id estava certo.
    """
    governance.check_egress("feed-poll", "public")
    net.apply(strict=False)
    import requests
    items: list[dict] = []
    rss_status = None
    try:
        resp = requests.get(feed_url(entry), timeout=timeout,
                            headers={"User-Agent": "Mozilla/5.0 vaultsources"})
        rss_status = resp.status_code
        if resp.status_code == 200:
            items = parse_feed(resp.text)
    except Exception as exc:
        rss_status = "%s: %s" % (type(exc).__name__, str(exc)[:120])

    if not items:
        items = _poll_ytdlp(entry, rss_status)

    for it in items:
        it["feed"] = entry["ref"]
        it["feed_label"] = entry["label"]
    return items


def _poll_ytdlp(entry: dict, rss_status) -> list[dict]:
    from vaultsources import adapters
    url = ("https://www.youtube.com/playlist?list=" + entry["ref"]
           if entry["kind"] == "playlist"
           else "https://www.youtube.com/channel/" + entry["ref"] + "/videos")
    proc = adapters._ytdlp(["--dump-json", "--skip-download", "--flat-playlist",
                            "--playlist-end", "25", url], timeout=180)
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
            "url": "https://www.youtube.com/watch?v=" + d["id"],
            "channel": (d.get("channel") or d.get("uploader") or "").strip(),
            "published": "",
            "description": (d.get("description") or "")[:400],
        })
    if out:
        return out

    err = (proc.stderr or "").strip()
    if "does not exist" in err or "Private" in err or "private" in err:
        raise FeedUnavailable(
            "o YouTube responde 'nao existe' para %s. Duas causas dao esta mesma "
            "resposta e nao da para distinguir de fora: (1) a playlist e PRIVADA, e "
            "o feed so serve publica ou nao listada; (2) o id esta errado. Se o link "
            "abre no seu navegador, e a primeira: mude para 'Nao listada' e o poll "
            "passa a funcionar sem expor a playlist em busca nem no seu canal."
            % entry["ref"])
    raise FeedUnavailable(
        "feed %s sem itens (RSS: %s; yt-dlp: %s)" % (entry["ref"], rss_status, err[:200]))


# ── relevancia ────────────────────────────────────────────────────────────────

_WORD = re.compile(r"[a-z0-9]+")
_STOP = {
    "de", "da", "do", "das", "dos", "que", "com", "para", "por", "uma", "the", "and",
    "for", "with", "you", "your", "how", "what", "why", "this", "that", "from", "are",
    "not", "was", "have", "has", "can", "will", "como", "sobre", "mais", "meu", "minha",
}


def _norm(text: str) -> list[str]:
    t = unicodedata.normalize("NFKD", (text or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return [w for w in _WORD.findall(t) if len(w) > 2 and w not in _STOP]


def score(item: dict, questions: list[dict], topics: list[str]) -> tuple[int, str]:
    """Pontua um candidato contra as perguntas abertas e os topicos do feed.

    Deterministico e explicavel: o `reason` diz qual pergunta puxou o item, para
    que uma proposta ruim seja discutivel em vez de misteriosa.
    """
    # Titulo para casar com PERGUNTA; descricao so para casar com TOPICO.
    # Descricao de video no YouTube e texto promocional: link de curso, hashtag,
    # nome de patrocinador. Deixando ela entrar no match de pergunta, um video de
    # troubleshooting do Copilot Studio foi anunciado como resposta a um risco de
    # governanca sobre dado exportado, porque as duas coisas compartilhavam
    # palavras de marketing.
    titulo = set(_norm(item.get("title", "")))
    hay = titulo | set(_norm(item.get("description", ""))[:200])
    best_q, best_hits = None, 0
    for q in questions:
        qwords = set(_norm(q.get("text", "")))
        hits = len(titulo & qwords)
        if hits > best_hits:
            best_q, best_hits = q, hits
    topic_terms = {t for tp in topics for t in _norm(tp)}
    topic_hits = len(hay & topic_terms)
    total = best_hits * 2 + topic_hits * 2

    # O limiar de 3 nao e cosmetico. Com 117 perguntas abertas, duas palavras em
    # comum acontecem por acaso o tempo todo: na primeira execucao real um video
    # chamado "Troubleshooting Copilot Studio State Management" foi anunciado como
    # resposta a um risco sobre "reuso nao governado de dado exportado". Motivo
    # errado e pior que motivo nenhum, porque convida a aprovar sem ler.
    if best_q and best_hits >= 3:
        reason = "casa com a pergunta aberta: %s" % best_q["text"][:110]
    elif topic_hits:
        reason = "bate com os topicos do feed: %s" % ", ".join(
            sorted(hay & topic_terms)[:4])
    elif best_q and best_hits == 2:
        reason = ("so 2 palavras em comum com uma pergunta aberta; "
                  "provavelmente coincidencia")
    else:
        reason = "nenhuma pergunta aberta pediu isto"
    return total, reason


def collect(*, questions: list[dict] | None = None, min_score: int = 1,
            limit_per_feed: int = 8) -> dict:
    """Varre a watchlist, pontua o que e novo e devolve o resumo do poll.

    Nada e ingerido aqui. O que sai daqui e proposta, e proposta espera aprovacao.
    """
    questions = questions or []
    wl = load_watchlist()
    q = load_queue()
    known = {c["video_id"] for c in q["candidates"]}
    seen = wl.setdefault("seen", {})
    today = datetime.now().strftime("%Y-%m-%d")
    added, errors, skipped = [], [], 0

    for entry in wl["feeds"]:
        try:
            items = poll(entry)
            entry["last_poll"], entry["last_error"] = today, ""
        except Exception as exc:
            entry["last_error"] = "%s: %s" % (type(exc).__name__, str(exc)[:200])
            errors.append({"feed": entry["ref"], "error": entry["last_error"]})
            continue
        for it in items[:limit_per_feed]:
            if it["video_id"] in known or it["video_id"] in seen:
                skipped += 1
                continue
            # Ja ingerido fora da fila (por `fetch` avulso) nao volta como proposta.
            # Sem isto o primeiro poll da playlist do Kelvin propos 3 videos que ele
            # ja tinha no vault, e uma fila que repete o que voce ja tem ensina a
            # ignorar a fila.
            from vaultsources import note as _note
            if _note.find_by_url(it["url"]) is not None:
                seen[it["video_id"]] = today
                skipped += 1
                continue
            s, reason = score(it, questions, entry.get("topics", []))
            if s < min_score:
                seen[it["video_id"]] = today  # visto e descartado: nao reaparece amanha
                skipped += 1
                continue
            cand = dict(it)
            cand.update({"score": s, "reason": reason, "state": "proposed",
                         "proposed_at": today, "note": ""})
            q["candidates"].append(cand)
            known.add(it["video_id"])
            added.append(cand)

    save_watchlist(wl)
    save_queue(q)
    added.sort(key=lambda c: -c["score"])
    return {"added": added, "errors": errors, "skipped": skipped,
            "feeds": len(wl["feeds"]), "date": today}


def set_state(video_id: str, state: str, *, note: str = "") -> dict:
    if state not in STATES:
        raise ValueError("state %r fora de %s" % (state, STATES))
    q = load_queue()
    for c in q["candidates"]:
        if c["video_id"] == video_id:
            c["state"] = state
            if note:
                c["note"] = note
            c["state_at"] = datetime.now().strftime("%Y-%m-%d")
            save_queue(q)
            return c
    raise KeyError("candidato %s nao esta na fila" % video_id)


def pending_candidates() -> list[dict]:
    q = load_queue()
    out = [c for c in q["candidates"] if c["state"] == "proposed"]
    out.sort(key=lambda c: (-c.get("score", 0), c.get("published", "")))
    return out


def pending_by_feed() -> list[dict]:
    """Candidatos agrupados por feed, do mais relevante para o menos.

    Assinar 10 feeds de uma vez produziu 57 propostas na primeira varredura, e 8
    delas eram as 8 partes do MESMO curso de Azure. Isso nao e uma fila de decisao,
    e outro backlog. Oito partes de um curso sao UMA decisao ("quero fazer este
    curso?"), nao oito.
    """
    grupos: dict[str, dict] = {}
    for c in pending_candidates():
        g = grupos.setdefault(c.get("feed", "?"), {
            "feed": c.get("feed", "?"), "label": c.get("feed_label", "?"),
            "itens": [], "score": 0})
        g["itens"].append(c)
        g["score"] = max(g["score"], c.get("score", 0))
    out = list(grupos.values())
    out.sort(key=lambda g: (-g["score"], -len(g["itens"])))
    return out


def set_state_feed(feed_ref: str, state: str, *, note: str = "") -> int:
    """Aplica o estado a todos os candidatos propostos de um feed."""
    if state not in STATES:
        raise ValueError("state %r fora de %s" % (state, STATES))
    q = load_queue()
    n = 0
    hoje = datetime.now().strftime("%Y-%m-%d")
    for c in q["candidates"]:
        if c.get("feed") == feed_ref and c["state"] == "proposed":
            c["state"], c["state_at"] = state, hoje
            if note:
                c["note"] = note
            n += 1
    if n:
        save_queue(q)
    return n
