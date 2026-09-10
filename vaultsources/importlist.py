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

Titulo nao vem no csv, so o id. Sem titulo nao ha ranking. Os titulos vem do
**oEmbed** do YouTube, nao do yt-dlp: e um endpoint publico que devolve titulo e
autor em ~1 s, sem chave e sem o custo do extrator completo. O `--dump-json` do
yt-dlp faz o trabalho de descobrir formatos de video, que aqui nao serve para nada,
e e o endpoint que fez o IP daqui ser bloqueado hoje. Video privado ou apagado
responde 401 no oEmbed, e isso e registrado em vez de virar falha muda.
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


def oembed(video_id: str, timeout: int = 20) -> tuple[str, str] | None:
    """Titulo e autor pelo oEmbed publico. None quando o video nao esta acessivel."""
    from vaultsources import governance, net
    governance.check_egress("feed-poll", "public")
    net.apply(strict=False)
    import requests
    r = requests.get("https://www.youtube.com/oembed",
                     params={"url": "https://www.youtube.com/watch?v=" + video_id,
                             "format": "json"},
                     timeout=timeout, headers={"User-Agent": "Mozilla/5.0 vaultsources"})
    if r.status_code != 200:
        return None
    d = r.json()
    return (str(d.get("title") or ""), str(d.get("author_name") or ""))


def import_list(path: Path, *, label: str = "watch-later", probe: int = 25,
                pause: float = 1.0) -> dict:
    """Poe os videos na fila de candidatos, com titulo quando der para buscar."""
    from vaultsources import note

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
                r = oembed(vid)
                if r is None:
                    falhas.append({"id": vid, "why": "indisponivel (privado ou apagado)"})
                else:
                    titulo, canal = r
            except Exception as exc:
                falhas.append({"id": vid, "why": "%s: %s" % (type(exc).__name__, str(exc)[:90])})
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


def fill_titles(limit: int = 25, pause: float = 1.0, save_every: int = 25) -> dict:
    """Busca titulo dos candidatos que entraram sem. Em lote, com pausa.

    Grava a fila a cada `save_every` itens. A primeira versao so gravava no fim, e
    com 778 videos isso e um quarto de hora de trabalho que uma interrupcao apaga
    inteiro. Trabalho longo sem ponto de gravacao intermediario nao e retomavel, e
    o que nao e retomavel acaba nao sendo refeito.
    """
    from vaultsources import questions

    q = feeds.load_queue()
    alvos = [c for c in q["candidates"]
             if c["state"] == "proposed" and not c.get("title")][:limit]
    qs = questions.collect()
    ok, falhas = 0, []
    for c in alvos:
        try:
            r = oembed(c["video_id"])
            if r is None:
                c["state"] = "failed"
                c["note"] = "indisponivel no YouTube (privado ou apagado)"
                falhas.append({"id": c["video_id"], "why": "indisponivel"})
            else:
                c["title"], c["channel"] = r
                c["score"], c["reason"] = feeds.score(c, qs, [])
                ok += 1
        except Exception as exc:
            falhas.append({"id": c["video_id"], "why": "%s: %s" % (type(exc).__name__, str(exc)[:90])})
        if pause:
            time.sleep(pause)
        if save_every and (ok + len(falhas)) % save_every == 0:
            feeds.save_queue(q)
    feeds.save_queue(q)
    restantes = sum(1 for c in q["candidates"]
                    if c["state"] == "proposed" and not c.get("title"))
    return {"preenchidos": ok, "falhas": falhas, "restantes": restantes}
