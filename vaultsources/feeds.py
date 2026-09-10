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

def add_feed(ref: str, *, label: str = "", topics: list[str] | None = None) -> dict:
    kind = "playlist" if ref.startswith(("PL", "UU", "LL", "FL")) else "channel"
    data = load_watchlist()
    if any(f["ref"] == ref for f in data["feeds"]):
        raise ValueError("feed %s ja esta na watchlist" % ref)
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


def poll(entry: dict, *, timeout: int = 30) -> list[dict]:
    governance.check_egress("feed-poll", "public")
    net.apply(strict=False)
    import requests
    resp = requests.get(feed_url(entry), timeout=timeout,
                        headers={"User-Agent": "Mozilla/5.0 vaultsources"})
    resp.raise_for_status()
    items = parse_feed(resp.text)
    for it in items:
        it["feed"] = entry["ref"]
        it["feed_label"] = entry["label"]
    return items


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
    hay = set(_norm(item.get("title", "")) + _norm(item.get("description", ""))[:200])
    best_q, best_hits = None, 0
    for q in questions:
        qwords = set(_norm(q.get("text", "")))
        hits = len(hay & qwords)
        if hits > best_hits:
            best_q, best_hits = q, hits
    topic_hits = len(hay & {t for tp in topics for t in _norm(tp)})
    total = best_hits * 2 + topic_hits
    if best_q and best_hits >= 2:
        reason = "casa com a pergunta aberta: %s" % best_q["text"][:110]
    elif topic_hits:
        reason = "bate com os topicos do feed (%d termo(s))" % topic_hits
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
