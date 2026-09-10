"""vaultsources/importlist.py — entrar com uma lista de videos que o feed nao alcanca.

Existe por causa do Watch Later. Ele e a playlist onde o Kelvin mais guarda video, e
e a unica que nao da para assinar: `WL` e `LL` (curtidos) sao playlists de sistema,
permanentemente privadas, sem opcao de tornar publicas. Verificado em 2026-09-10 —
o feed responde 404 e o yt-dlp responde "The playlist does not exist" nas duas.

O caminho oficial e o Google Takeout: exportar os dados do YouTube com "playlists"
marcado devolve um `.csv` por playlist, e o do Watch Later traz uma coluna de video
id. Este modulo le esse csv e poe os videos na mesma fila de candidatos que o poll
alimenta, entao o resto do fluxo (aprovar, ingerir) nao muda.

A alternativa seria ler os cookies do navegador dele e deixar o yt-dlp abrir o
Watch Later autenticado. Nao entra: dar a sessao logada dele a um script e um preco
alto para economizar um export de dois minutos, e o proprio YouTube adverte que
usar conta para automatizar leitura acaba em banimento.

Titulo nao vem no csv, so o id. Sem titulo nao ha ranking, entao `import_list`
busca os titulos em lotes, com pausa, e diz quantos ficaram sem. Buscar 300 de uma
vez e como o IP daqui foi bloqueado hoje.
"""

from __future__ import annotations

import csv
import io
import re
import time
from datetime import datetime
from pathlib import Path

from vaultsources import feeds

VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}")


def parse_source(path: Path) -> list[str]:
    """Ids de video de um csv do Takeout ou de um txt com uma URL por linha."""
    raw = path.read_text(encoding="utf-8-sig", errors="replace")
    ids: list[str] = []
    if path.suffix.lower() == ".csv":
        rows = list(csv.reader(io.StringIO(raw)))
        header = None
        for i, row in enumerate(rows[:5]):
            low = [c.strip().lower() for c in row]
            if any("video id" in c or c == "videoid" for c in low):
                header, start = low, i + 1
                break
        if header:
            col = next(i for i, c in enumerate(header)
                       if "video id" in c or c == "videoid")
            for row in rows[start:]:
                if len(row) > col and VIDEO_ID.fullmatch(row[col].strip()):
                    ids.append(row[col].strip())
    if not ids:
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = (re.search(r"(?:v=|youtu\.be/|shorts/)([A-Za-z0-9_-]{11})", line)
                 or (VIDEO_ID.fullmatch(line) and re.match(r"(.*)", line)))
            if m:
                ids.append(m.group(1))
    seen, out = set(), []
    for v in ids:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


def import_list(path: Path, *, label: str = "watch-later", probe: int = 25,
                pause: float = 1.0) -> dict:
    """Poe os videos na fila de candidatos, com titulo quando der para buscar."""
    from vaultsources import adapters, note

    ids = parse_source(Path(path))
    q = feeds.load_queue()
    ja_na_fila = {c["video_id"] for c in q["candidates"]}
    hoje = datetime.now().strftime("%Y-%m-%d")

    novos, ja_no_vault, sem_titulo, falhas = [], 0, 0, []
    buscados = 0
    for vid in ids:
        url = "https://www.youtube.com/watch?v=" + vid
        if vid in ja_na_fila:
            continue
        if note.find_by_url(url) is not None:
            ja_no_vault += 1
            continue
        titulo, canal = "", ""
        if buscados < probe:
            try:
                meta = adapters.probe(url)
                titulo = str(meta.get("title") or "")
                canal = str(meta.get("uploader") or meta.get("channel") or "")
            except Exception as exc:
                falhas.append({"id": vid, "why": str(exc)[:120]})
            buscados += 1
            if pause:
                time.sleep(pause)
        if not titulo:
            sem_titulo += 1
        novos.append({
            "video_id": vid, "title": titulo, "url": url, "channel": canal,
            "published": "", "description": "",
            "feed": label, "feed_label": label,
            "score": 0, "state": "proposed", "proposed_at": hoje,
            "reason": ("importado de %s; sem titulo ainda, rode "
                       "`queue --fill-titles` antes de decidir" % label) if not titulo
                      else "importado de %s" % label,
            "note": "",
        })

    q["candidates"].extend(novos)
    feeds.save_queue(q)
    return {"lidos": len(ids), "novos": len(novos), "ja_no_vault": ja_no_vault,
            "sem_titulo": sem_titulo, "falhas": falhas}


def fill_titles(limit: int = 25, pause: float = 1.0) -> dict:
    """Busca titulo dos candidatos que entraram sem. Em lote, com pausa."""
    from vaultsources import adapters, questions

    q = feeds.load_queue()
    alvos = [c for c in q["candidates"]
             if c["state"] == "proposed" and not c.get("title")][:limit]
    qs = questions.collect()
    ok, falhas = 0, []
    for c in alvos:
        try:
            meta = adapters.probe(c["url"])
            c["title"] = str(meta.get("title") or "")
            c["channel"] = str(meta.get("uploader") or meta.get("channel") or "")
            c["score"], c["reason"] = feeds.score(c, qs, [])
            ok += 1
        except Exception as exc:
            falhas.append({"id": c["video_id"], "why": str(exc)[:120]})
        if pause:
            time.sleep(pause)
    feeds.save_queue(q)
    restantes = sum(1 for c in q["candidates"]
                    if c["state"] == "proposed" and not c.get("title"))
    return {"preenchidos": ok, "falhas": falhas, "restantes": restantes}
