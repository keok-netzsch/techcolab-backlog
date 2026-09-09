"""Inventario de gramatica do Kelvin, com procedencia por registro.

Por que existe
--------------
`coach_patterns.detect()` ja roda em TODA sessao do coach (`coach.py`), mas o que
ele devolve so vira uma linha dentro do prompt ("ja detectei isto, nao repita") e
e descartado. `summarise()` nunca e chamado fora do self-test. Detector correto,
sem consumidor - o padrao 12 do ARCHITECTURE.md. Este modulo e o consumidor.

A regra do corpus, que nao e detalhe
------------------------------------
O `~/.claude/CLAUDE.md` do Kelvin diz, na regra do voice-gate: *"Corpus valido:
escrita pre-jun/2026 + transcript de call de qualquer data; escrita jun-set/2026
e contaminada por AI."* Boa parte do que ele "escreveu" de junho para ca foi
escrita ou polida por mim. Medir gramatica ali mede o MEU ingles e devolve uma
nota boa e falsa, que e pior que nao medir.

Por isso cada trecho entra com REGISTRO e o registro nunca e somado com outro:

| Registro          | Fonte                          | Contaminado? |
|-------------------|--------------------------------|--------------|
| `fala`            | transcript das calls           | nao, em qualquer data |
| `escrito-informal`| prompts dele nos transcritos do Claude | nao - e ele digitando |

Somar os dois apagaria a diferenca que interessa: um typo digitando para o Claude
nao custa nada; o mesmo typo no e-mail para o Stefan foi o que foi flagrado como
"AI generated" duas vezes. Registro profissional (e-mail, Teams) NAO entra aqui -
precisa de acesso que nao existe, e o periodo recente esta contaminado.

Uso:
    python coach_grammar.py            # reconstroi o tracker
    python coach_grammar.py --só-fala  # pula a varredura dos transcritos do Claude
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import coach_patterns as patterns  # noqa: E402

VAULT = os.environ.get(
    "TECHCOLAB_VAULT_ROOT",
    str(Path.home() / "OneDrive - NETZSCH" / "Documents" / "TechColab_D&A_KO"),
)
COACH_DIR = Path(VAULT) / "Areas" / "English-Learning"
SESSIONS_DIR = COACH_DIR / "sessions"
OUT_FILE = COACH_DIR / "grammar.json"
CLAUDE_PROJECTS = Path.home() / ".claude" / "projects"

# Prompt digitado por ele quase nunca passa disto. Acima e material colado - log,
# documento, transcricao. Medido em 09/09: 96% do volume dos transcritos esta em
# mensagens acima de 200 palavras, e nenhuma delas e escrita dele.
MAX_PROMPT_WORDS = 80

# O harness injeta texto com role=user. Sem este filtro o corpus deu 822 mil
# "palavras em ingles" que eram task-notification.
INJETADO = (
    "<system-reminder>", "<command-name>", "<command-message>", "<local-command",
    "<task-notification>", "<ci-monitor-event>", "<user-prompt-submit-hook>",
    "<function_results>", "<output-file>", "Contents of ", "[Request interrupted",
    "(Re-invocation of",
)

_PT = re.compile(r"\b(que|nao|não|para|com|uma|voce|você|isso|mas|por|como|está|"
                 r"fazer|então|também|preciso|quero|agora|ainda)\b", re.I)
_EN = re.compile(r"\b(the|and|that|with|this|have|from|what|which|should|would|"
                 r"there|about|because|need|want|please)\b", re.I)


def _is_english(text: str) -> bool:
    return len(_EN.findall(text)) > len(_PT.findall(text))


# ── Fonte 1: fala ────────────────────────────────────────────────────────────

def scan_speech() -> dict:
    """Transcripts das calls. Validos em qualquer data - e a voz dele."""
    hits, probes, exemplos = collections.Counter(), collections.Counter(), {}
    words = n_sessions = 0
    if not SESSIONS_DIR.exists():
        return _empty("fala")
    for f in sorted(SESSIONS_DIR.glob("*_english-coach.md")):
        try:
            md = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        m = re.search(r"## (?:Full transcript|Evaluated excerpt)\n(.*)", md, re.S)
        if not m:
            continue
        tr = m.group(1)
        own = patterns._speaker_lines(tr, "Kelvin") or tr
        if not own.strip():
            continue
        n_sessions += 1
        words += len(own.split())
        det = patterns.detect(tr)
        for h in det.get("certain", []):
            hits[h["label"]] += 1
            exemplos.setdefault(h["label"], {"fix": h["fix"], "casos": []})
            if len(exemplos[h["label"]]["casos"]) < 5:
                exemplos[h["label"]]["casos"].append(
                    {"data": f.stem[:10], "trecho": h["quote"]})
        for p in det.get("probes", []):
            probes[p.get("label") or p.get("pid", "?")] += 1
    return {"registro": "fala", "fonte": "call-recorder/transcripts via sessions/",
            "contaminado": False, "unidades": n_sessions, "palavras": words,
            "hits": dict(hits), "probes": dict(probes), "exemplos": exemplos}


# ── Fonte 2: o que ele digita para o Claude ──────────────────────────────────

def _own_prompt(msg: dict) -> str:
    if msg.get("type") != "user":
        return ""
    m = msg.get("message") or {}
    if m.get("role") != "user":
        return ""
    c = m.get("content")
    if isinstance(c, str):
        text = c
    elif isinstance(c, list):
        parts = []
        for b in c:
            if isinstance(b, dict) and b.get("type") == "tool_result":
                return ""
            if isinstance(b, dict) and b.get("type") == "text":
                parts.append(b.get("text", ""))
        text = "\n".join(parts)
    else:
        return ""
    text = text.strip()
    if not text or any(tag in text for tag in INJETADO):
        return ""
    if text.startswith(("C:\\", "/c/", "{", "[", "<", "PS C:")):
        return ""
    return text


def scan_chat() -> dict:
    """Prompts dele nos transcritos do Claude. E ele digitando, sem polimento."""
    hits, probes, exemplos = collections.Counter(), collections.Counter(), {}
    words = n_msgs = 0
    if not CLAUDE_PROJECTS.exists():
        return _empty("escrito-informal")
    for f in CLAUDE_PROJECTS.rglob("*.jsonl"):
        try:
            raw = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in raw.splitlines():
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            text = _own_prompt(msg)
            if not text:
                continue
            w = len(text.split())
            if w < 5 or w > MAX_PROMPT_WORDS or not _is_english(text):
                continue
            n_msgs += 1
            words += w
            # Sem prefixo de falante, `_speaker_lines` devolve o texto inteiro,
            # que e o que queremos: o prompt e todo dele.
            det = patterns.detect(text)
            for h in det.get("certain", []):
                hits[h["label"]] += 1
                exemplos.setdefault(h["label"], {"fix": h["fix"], "casos": []})
                if len(exemplos[h["label"]]["casos"]) < 5:
                    exemplos[h["label"]]["casos"].append(
                        {"data": (msg.get("timestamp") or "")[:10], "trecho": h["quote"]})
            for p in det.get("probes", []):
                probes[p.get("label") or p.get("pid", "?")] += 1
    return {"registro": "escrito-informal", "fonte": "~/.claude/projects/**/*.jsonl",
            "contaminado": False, "unidades": n_msgs, "palavras": words,
            "hits": dict(hits), "probes": dict(probes), "exemplos": exemplos}


def _empty(registro: str) -> dict:
    return {"registro": registro, "fonte": "", "contaminado": False, "unidades": 0,
            "palavras": 0, "hits": {}, "probes": {}, "exemplos": {}}


# ── Montagem ─────────────────────────────────────────────────────────────────

def build(so_fala: bool = False) -> dict:
    registros = [scan_speech()]
    if not so_fala:
        registros.append(scan_chat())

    for r in registros:
        p = r["palavras"] or 1
        r["taxa"] = {label: round(n / (p / 1000), 3) for label, n in r["hits"].items()}

    return {
        "meta": {
            "gerado_em": datetime.now().astimezone().isoformat(timespec="seconds"),
            "regras": len(patterns.RULES),
            "nota": ("Registros nunca sao somados. Escrito profissional (e-mail, "
                     "Teams, docs) fica de fora: sem acesso, e o periodo desde "
                     "jun/2026 esta contaminado por AI segundo a regra do voice-gate."),
            # Sem isto, "1 erro em 6.637 palavras" le-se como "escrita limpa", que
            # e falso: as regras nao olham ortografia. Numero confiante sobre o que
            # o detector nao mede e pior que numero nenhum (ARCHITECTURE.md, 5 e 6).
            "cobertura": {
                "mede": ("gramática de interferência do português: 16 regras "
                         "determinísticas + probes de falso cognato"),
                "nao_mede": [
                    "typo e erro de digitação — nenhum corretor ortográfico instalado",
                    "pontuação e uso de maiúscula",
                    "registro profissional (e-mail, Teams, documento): sem acesso, "
                    "e o período desde jun/2026 está contaminado por AI",
                ],
            },
        },
        "registros": {r["registro"]: r for r in registros},
    }


def save(data: dict) -> Path:
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return OUT_FILE


def main() -> int:
    ap = argparse.ArgumentParser(description="Inventario de gramatica por registro.")
    ap.add_argument("--so-fala", action="store_true",
                    help="Pula a varredura dos transcritos do Claude (mais rapido).")
    args = ap.parse_args()

    data = build(so_fala=args.so_fala)
    path = save(data)
    for nome, r in data["registros"].items():
        certos = sum(r["hits"].values())
        print(f"[grammar] {nome}: {r['unidades']} unidades, {r['palavras']:,} palavras, "
              f"{certos} erro(s) certo(s), {sum(r['probes'].values())} probe(s)")
    print(f"[grammar] {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
