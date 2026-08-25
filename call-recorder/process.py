"""
process.py — Ollama (local LLM) integration for call-recorder.
No API key required. Runs entirely offline via Ollama.

Usage:
  python process.py agenda     --person   Ana-Leite
  python process.py transcript --person   Ana-Leite  --transcript path/to/file.txt --date 2026-05-14 [--structured]
  python process.py manager    --manager  Alberto-Reuters --transcript path/to/file.txt --date 2026-05-14

Requires:
  - Ollama running locally:  ollama serve   (default port 11434)
  - Model pulled:            ollama pull llama3.2:3b
  - pip install requests
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import requests

# Vault root — override with env var TECHCOLAB_VAULT_ROOT; fallback below.
VAULT = os.environ.get(
    "TECHCOLAB_VAULT_ROOT",
    os.path.join(os.path.expanduser("~"), "OneDrive - NETZSCH", "Documents", "TechColab_D&A_KO"),
)
OLLAMA_URL   = "http://localhost:11434/api/generate"
# qwen2.5-coder (7B) summarizes 1:1 transcripts far better than llama3.2:3b (3B),
# which produced thin/generic topics. Override with CALLREC_MODEL if needed.
OLLAMA_MODEL = os.environ.get("CALLREC_MODEL", "qwen2.5-coder:latest")
# On CPU, prompt-eval of a full transcript with a 7B+ model can take several
# minutes before the first token — 300s was too short and timed out. Configurable.
OLLAMA_TIMEOUT = int(os.environ.get("CALLREC_TIMEOUT", "1200"))

PEOPLE = {
    "Ana-Leite":     "Ana Leite",
    "Daniel-Lima":   "Daniel Lima",
    "Lucas-Shizuno": "Lucas Shizuno",
    "Pedro-Hennig":  "Pedro Hennig",
    "Pedro-Klein":   "Pedro Klein",
}

MANAGERS = {
    "Alberto-Reuters":       "Alberto Reuters",
    "Stefan-Lautenschlager": "Stefan Lautenschlager",
}

SECTION_MAP = {
    "1on1":     "1on1.md",
    "OKR":      "OKR.md",
    "PDI":      "PDI.md",
    "Overview": "Overview.md",
}

SECTION_MODE = {
    "1on1":     "prepend",
    "OKR":      "append",
    "PDI":      "append",
    "Overview": "append",
}

MANAGER_SECTION_MAP  = {"1on1": "1on1.md", "Overview": "Overview.md"}
MANAGER_SECTION_MODE = {"1on1": "prepend", "Overview": "append"}

# Standalone capture modes (idea-031) — sessions not tied to a person/stakeholder.
# Each records → transcribes → Ollama structures the transcript into an Inbox note
# for later triage. suffix is used for both the transcript and the output filename.
CAPTURE_MODES = {
    "project": {
        "suffix": "project-meeting",
        "type":   "project-meeting",
        "status": "a-triar",
        "label":  "reuniao de projeto",
        "instructions": (
            "Esta e uma REUNIAO DE PROJETO. Estruture em portugues com as secoes:\n"
            "## Decisoes\n## Riscos\n## Proximos passos\n"
            "Em 'Proximos passos' use o formato - [ ] (responsavel) acao. "
            "Se identificar o tema/projeto, coloque-o como titulo na primeira linha."
        ),
    },
    "retro": {
        "suffix": "retrospective",
        "type":   "retrospective",
        "status": "a-triar",
        "label":  "retrospectiva agil",
        "instructions": (
            "Esta e uma RETROSPECTIVA AGIL. Estruture em portugues com as secoes:\n"
            "## O que foi bem\n## O que nao foi bem\n## Acoes de melhoria\n"
            "Em 'Acoes de melhoria' use o formato - [ ] (responsavel) acao."
        ),
    },
    "idea": {
        "suffix": "idea-capture",
        "type":   "idea-capture",
        "status": "a-triar",
        "label":  "captura de ideia",
        "instructions": (
            "Esta e uma CAPTURA DE IDEIA (gravacao livre). Organize em portugues com as secoes:\n"
            "## Ideia\n## Problema ou oportunidade\n## Solucao proposta\n## Perguntas em aberto\n"
            "Em '## Ideia' resuma em 1-2 frases."
        ),
    },
    "requirements": {
        "suffix": "requirements",
        "type":   "requirements",
        "status": "a-triar",
        "label":  "sessao de requisitos",
        "instructions": (
            "Esta e uma SESSAO DE REQUISITOS. Estruture em portugues com as secoes:\n"
            "## User stories\n## Criterios de aceite\n## Perguntas em aberto\n"
            "Em '## User stories' use o formato: Como [persona], quero [acao], para [valor]."
        ),
    },
    "learning": {
        "suffix": "learning-capture",
        "type":   "learning-capture",
        "status": "a-triar",
        "label":  "registro de aprendizado",
        "instructions": (
            "Este e um REGISTRO DE APRENDIZADO (curso, leitura ou evento). Organize em portugues com as secoes:\n"
            "## Resumo\n## Principais aprendizados\n## Como aplicar\n## Referencia\n"
            "Em '## Como aplicar' use o formato - [ ] (responsavel) acao. "
            "Na triagem, este registro pode ser linkado ao PDI."
        ),
    },
}
# transcript/output filename suffix -> capture mode (for sweep reprocessing)
SUFFIX_TO_MODE = {cfg["suffix"]: mode for mode, cfg in CAPTURE_MODES.items()}


# ── Ollama ────────────────────────────────────────────────────────────────────

def _check_ollama():
    """Fail fast if Ollama is not reachable."""
    try:
        requests.get("http://localhost:11434/", timeout=3)
    except requests.exceptions.ConnectionError:
        print("[ERROR] Ollama nao encontrado em localhost:11434.")
        print("        Inicie com: ollama serve")
        sys.exit(1)


def _ollama_generate(prompt: str, stream: bool = True, model: str = OLLAMA_MODEL) -> str:
    """
    Call Ollama REST API.
    With stream=True  → prints tokens as they arrive, returns full text.
    With stream=False → waits for full response, returns it (silent).
    """
    # keep_alive=0 unloads the model from RAM right after the response, so a 5GB (7B)
    # model never lingers — important on a 16GB laptop shared with other work.
    # Override with CALLREC_KEEPALIVE (e.g. "5m") to keep it warm across a batch.
    payload = {
        "model": model, "prompt": prompt, "stream": stream,
        "keep_alive": os.environ.get("CALLREC_KEEPALIVE", "0"),
    }

    if stream:
        full = []
        with requests.post(OLLAMA_URL, json=payload, stream=True, timeout=OLLAMA_TIMEOUT) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line:
                    continue
                chunk = json.loads(line)
                token = chunk.get("response", "")
                print(token, end="", flush=True)
                full.append(token)
                if chunk.get("done"):
                    break
        print()  # newline after stream ends
        return "".join(full)
    else:
        r = requests.post(OLLAMA_URL, json=payload, timeout=OLLAMA_TIMEOUT)
        r.raise_for_status()
        return r.json()["response"]


# ── Vault helpers ─────────────────────────────────────────────────────────────

def read_file(path: str, max_chars: int = None) -> str:
    try:
        try:
            content = Path(path).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = Path(path).read_text(encoding="utf-8", errors="replace")
        return content[:max_chars] if max_chars else content
    except FileNotFoundError:
        return ""


def save_block(file_path: str, content: str, mode: str = "prepend"):
    """
    Save a content block into an existing Obsidian note.

    mode='prepend' (1on1.md): insert right after the YAML frontmatter (and any
      leading '>' callout), so the newest entry sits at the top of the body.
      Robust to how many '---' separators the body already contains.

    mode='append' (OKR / PDI / Overview): append at the end with a '---' separator.
    """
    p = Path(file_path)
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return

    try:
        existing = p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        existing = p.read_text(encoding="utf-8", errors="replace")

    if mode == "append":
        p.write_text(existing.rstrip() + "\n\n---\n\n" + content, encoding="utf-8")
        return

    # prepend: line-based, deterministic
    lines = existing.split("\n")
    insert_at = 0

    # 1) skip the YAML frontmatter block (--- ... ---)
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                insert_at = i + 1
                break

    # 2) keep a leading callout (> ...) and blank lines pinned at the top
    while insert_at < len(lines) and (
        lines[insert_at].strip() == "" or lines[insert_at].lstrip().startswith(">")
    ):
        insert_at += 1

    head = "\n".join(lines[:insert_at]).rstrip()
    tail = "\n".join(lines[insert_at:]).lstrip("\n")
    new = (head + "\n\n" + content.rstrip() + "\n\n---\n\n" + tail).rstrip() + "\n"

    p.write_text(new, encoding="utf-8")


def _parse_and_save(response: str, base_path: Path,
                    section_map: dict, section_mode: dict) -> int:
    """
    Parse BLOCO markers and save each block to the vault.

    Tries strict format first (### BLOCO xxx \\n ~~~markdown \\n ... \\n ~~~).
    Falls back to a looser split when the model skips ### or ~~~markdown fences.
    """
    # ── Strict: ### BLOCO xxx \n ~~~markdown \n content \n ~~~
    strict = re.findall(
        r"### BLOCO (\w+)[^\n]*\n~~~markdown\n(.*?)~~~",
        response, re.DOTALL
    )
    if strict:
        matches = strict
    else:
        # ── Loose: split on "BLOCO xxx" (with or without ###)
        # re.split with a capture group returns alternating [before, g1, between, g2, ...]
        parts = re.split(r"\n*(?:###\s+)?BLOCO\s+(\w+)[^\n]*\n", response)
        # parts[0] = preamble (ignore), [1]=type1, [2]=content1, [3]=type2, ...
        matches = []
        i = 1
        while i + 1 < len(parts):
            block_type = parts[i].strip()
            raw_content = parts[i + 1]
            # Strip trailing ~~~ if the model added closing fences anyway
            raw_content = re.sub(r'\n*~~~\s*$', '', raw_content).strip()
            matches.append((block_type, raw_content))
            i += 2

    saved = 0
    for block_type, content in matches:
        if block_type in section_map:
            fpath = str(base_path / section_map[block_type])
            save_block(fpath, content.strip(), mode=section_mode.get(block_type, "append"))
            print(f"  [OK] Atualizado: {section_map[block_type]}")
            saved += 1
    return saved


def _strip_dated_1on1(oneonone_path: Path, date: str) -> None:
    """Remove an existing `## {date}` 1:1 section (up to its trailing `---`) so a
    reprocess replaces it instead of stacking a duplicate. No-op if absent.
    Sections are `---`-separated by save_block, so we stop at the first `---`."""
    if not oneonone_path.exists():
        return
    text = oneonone_path.read_text(encoding="utf-8", errors="replace")
    # Remove EVERY section for this date (not just the first) so reprocessing is
    # fully idempotent even if a prior buggy run left duplicates. A section ends at
    # its trailing `---` separator OR at end-of-file (a section can be the last one,
    # with no trailing `---`).
    pattern = re.compile(rf"(?ms)^## {re.escape(date)}\b.*?(?:\n---\n|\Z)")
    new = pattern.sub("", text)
    if new != text:
        oneonone_path.write_text(re.sub(r"\n{3,}", "\n\n", new), encoding="utf-8")


def _fallback_1on1(oneonone_path: Path, date: str) -> None:
    """If the model didn't emit a parseable BLOCO, still record a dated section so
    the session shows up in the Team tab (the visible "last 1:1" / Topics). The full
    unstructured output remains in the standalone note."""
    block = (
        f"## {date}\n\n**Topics:**\n"
        f"- (auto) Modelo nao estruturou em blocos; ver nota completa em "
        f"1on1/{date}_1on1_*.md\n"
    )
    save_block(str(oneonone_path), block, mode="prepend")
    print("  [OK] 1on1.md atualizado (fallback — modelo sem BLOCO)")


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_agenda(person_folder: str):
    """Generate a 1:1 agenda suggestion for a team member (streamed to terminal)."""
    person_name = PEOPLE.get(person_folder, person_folder.replace("-", " "))
    today = datetime.now().strftime("%Y-%m-%d")
    ctx = read_file(str(Path(VAULT) / "Team" / person_folder / "1on1.md"), max_chars=3000)

    prompt = f"""Voce e um assistente de gestao de pessoas.
Contexto: Kelvin Okuda e Data & Analytics Team Lead na NETZSCH.
Hoje e {today}. Ele vai ter um 1:1 de 20 minutos com {person_name}.

Log da ultima reuniao (referencia):
---
{ctx}
---

Sugira uma pauta objetiva para 20 minutos:
- Retomar action items em aberto
- Espaco para o liderado falar (5 min)
- Topicos de PDI se relevante
- Maximo 4 topicos com tempo estimado

Formato: lista markdown com tempo por item. Responda em portugues."""

    print(f"\n  [Ollama] Sugestao de pauta para {person_name}:\n")
    print("  " + "-" * 50)
    _ollama_generate(prompt, stream=True)
    print("  " + "-" * 50)


# ── Speaker labeling (idea-031) — text-only, interim (no voice diarization) ─────

def label_speakers(transcript: str, participants=None, lang: str = "pt",
                   model: str = OLLAMA_MODEL) -> str:
    """Attribute each turn of a transcript to a speaker from TEXT CONTEXT alone.

    This is the interim, dependency-free stand-in for real (voice-based) speaker
    diarization: there is no audio signal here, so the model guesses who is
    speaking from conversational cues. Labels are HINTS, not ground truth — it
    cannot reliably tell two similar speakers apart. Timestamps and wording are
    preserved; only a `[Speaker]` tag is prepended to each line.

    participants: known names (e.g. ["Kelvin Okuda", "Ana Leite"]) the model must
    reuse verbatim; if omitted it falls back to SPEAKER_1/SPEAKER_2/... Returns the
    labeled transcript, or the original text unchanged when it is empty (no LLM call).
    """
    if not transcript or not transcript.strip():
        return transcript

    if participants:
        who = ", ".join(participants)
        roster = (f"Participantes conhecidos (use EXATAMENTE estes rotulos): {who}. "
                  f"Se algum trecho nao encaixar, use SPEAKER_?.")
    else:
        roster = ("Nao ha lista de participantes; rotule cada falante distinto como "
                  "SPEAKER_1, SPEAKER_2, ... de forma consistente ao longo do texto.")

    lang_line = "Mantenha o idioma original dos trechos." if lang == "pt" else \
                "Keep the original language of each turn."
    prompt = f"""Voce recebe a transcricao de uma conversa com marcas de tempo [SS.Ss].
Tarefa: identificar quem fala em cada trecho, APENAS pelo contexto do texto
(nao ha informacao de voz). {roster}

REGRAS:
- Preserve os timestamps e o texto EXATAMENTE como estao.
- Prefixe cada linha com o falante entre colchetes: [00.0s] [Kelvin Okuda] texto.
- Nao invente conteudo, nao resuma, nao traduza; apenas atribua falantes.
- Em duvida entre dois falantes, escolha o mais provavel pelo contexto.
{lang_line}

Transcricao:
---
{transcript[:12000]}
---

Responda APENAS com a transcricao rotulada, uma linha por trecho."""
    return _ollama_generate(prompt, stream=False, model=model)


def cmd_diarize(transcript_file: str, people: str = None, output: str = None) -> str:
    """CLI: label speakers in a transcript file. Writes `<name>.diarized.txt` next
    to the input (or --output) and returns the path. Standalone on purpose — it is
    a second LLM pass (~minutes on CPU), so it is not forced into every 1:1 flow."""
    transcript = read_file(transcript_file)
    if not transcript.strip():
        print(f"[ERROR] Transcricao vazia ou nao encontrada: {transcript_file}")
        sys.exit(1)

    participants = None
    if people:
        participants = [p.strip() for p in people.split(",") if p.strip()]

    print("\n  [Ollama] Atribuindo falantes (baseado em texto — aproximado)...\n")
    labeled = label_speakers(transcript, participants)

    if output:
        out_path = output
    else:
        base, ext = os.path.splitext(transcript_file)
        out_path = base + ".diarized" + (ext or ".txt")
    Path(out_path).write_text(labeled, encoding="utf-8")
    print(f"  [OK] Transcricao rotulada salva em: {out_path}")
    return out_path


# ── Cross-Session Memory (idea-031): context across a person's 1:1s and people ──

_MEM_SESSION_RE = re.compile(r"^## (\d{4}-\d{2}-\d{2})\b", re.MULTILINE)
_MEM_TOPIC_HDR  = re.compile(r"\*\*(T[oó]picos?|Topics?):?\*\*")
_MEM_ACTION_HDR = re.compile(r"\*\*(Action [Ii]tems?|A[cç][oõ]es?):?\*\*")


def _norm_text(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().casefold()


def build_session_memory(text: str) -> list:
    """Parse every dated `## YYYY-MM-DD` session from a 1on1.md body into
    [{date, topics:[str], actions:[{text,done}]}], newest date first. Pure — this
    generalizes team_agenda._parse_last_1on1 from the latest session to all of them."""
    if not text or not text.strip():
        return []
    parts = _MEM_SESSION_RE.split(text)  # [pre, date1, content1, date2, content2, ...]
    sessions = []
    for i in range(1, len(parts) - 1, 2):
        s_date, content = parts[i], parts[i + 1]
        topics, actions, in_t, in_a = [], [], False, False
        for line in content.splitlines():
            s = line.strip()
            if _MEM_TOPIC_HDR.match(s):
                in_t, in_a = True, False; continue
            if _MEM_ACTION_HDR.match(s):
                in_t, in_a = False, True; continue
            if s.startswith("**") or s.startswith("---"):
                in_t = in_a = False
            if in_t and s.startswith("- "):
                topics.append(s[2:].strip())
            if in_a and re.match(r"- \[[ x]\]", s):
                actions.append({"text": s[6:].strip(), "done": s[3] == "x"})
        sessions.append({"date": s_date, "topics": topics, "actions": actions})
    sessions.sort(key=lambda x: x["date"], reverse=True)
    return sessions


def summarize_person_memory(sessions: list) -> dict:
    """Cross-session aggregate for one person: open actions (deduped, newest kept),
    topics recurring in >=2 sessions, and the date span. Pure."""
    open_actions, seen = [], set()
    for s in sessions:  # newest first -> first occurrence keeps the most recent date
        for a in s["actions"]:
            if a["done"]:
                continue
            key = _norm_text(a["text"])
            if key and key not in seen:
                seen.add(key)
                open_actions.append({"text": a["text"], "since": s["date"]})

    topic_count, topic_display = {}, {}
    for s in sessions:
        for norm in {_norm_text(t) for t in s["topics"] if t.strip()}:
            topic_count[norm] = topic_count.get(norm, 0) + 1
    for s in sessions:  # newest first -> display uses the most recent phrasing
        for t in s["topics"]:
            norm = _norm_text(t)
            if norm:
                topic_display.setdefault(norm, t.strip())
    recurring = sorted(
        ({"topic": topic_display[k], "count": v} for k, v in topic_count.items() if v >= 2),
        key=lambda x: (-x["count"], x["topic"].lower()),
    )
    dates = [s["date"] for s in sessions]
    return {
        "session_count": len(sessions),
        "first_date": min(dates) if dates else None,
        "last_date": max(dates) if dates else None,
        "open_actions": open_actions,
        "recurring_topics": recurring,
    }


def cross_person_topics(person_sessions: dict) -> list:
    """Topics that appear for >=2 different people (a cross-person connection).
    person_sessions: {display_name: [sessions]}. Returns [{topic, people:[names]}]
    sorted by #people desc, then topic. Pure."""
    topic_people, topic_display = {}, {}
    for name, sessions in person_sessions.items():
        norms = set()
        for s in sessions:
            for t in s["topics"]:
                norm = _norm_text(t)
                if norm:
                    norms.add(norm)
                    topic_display.setdefault(norm, t.strip())
        for norm in norms:
            topic_people.setdefault(norm, set()).add(name)
    shared = [
        {"topic": topic_display[k], "people": sorted(v)}
        for k, v in topic_people.items() if len(v) >= 2
    ]
    shared.sort(key=lambda x: (-len(x["people"]), x["topic"].lower()))
    return shared


def _person_memory_md(name: str, mem: dict) -> str:
    gen = datetime.now().strftime("%Y-%m-%d")
    lines = [
        "---", "type: cross-session-memory", f"generated: {gen}",
        f"person: {name}", "tags: [memory, team, generated]", "ai-first: true", "---", "",
        "## For future Claude",
        (f"Cross-session memory for {name}, aggregated deterministically (no LLM) from "
         f"their 1on1.md across {mem['session_count']} session(s) "
         f"({mem['first_date']} .. {mem['last_date']}). Lists actions still open across "
         f"sessions and topics recurring in >=2 sessions. Regenerated by `process.py memory`."),
        "",
        f"# Cross-Session Memory - {name}", "",
        f"Sessions: {mem['session_count']} - Span: {mem['first_date']} .. {mem['last_date']}", "",
        "## Open actions (carried across sessions)", "",
    ]
    lines += ([f"- [ ] {a['text']} _(since {a['since']})_" for a in mem["open_actions"]]
              or ["_none_"])
    lines += ["", "## Recurring topics (>=2 sessions)", ""]
    lines += ([f"- {t['topic']} ({t['count']}x)" for t in mem["recurring_topics"]]
              or ["_none_"])
    return "\n".join(lines).rstrip() + "\n"


def _team_folders(team: Path) -> list:
    if not team.exists():
        return []
    return sorted(p.name for p in team.iterdir()
                  if p.is_dir() and p.name != "1on1" and not p.name.startswith("_"))


def cmd_memory(person_folder: str = None, output: str = None) -> str:
    """Generate cross-session memory digests (deterministic, no LLM).

    With --person: one team member -> Team/<folder>/memory.md.
    Without: every member's memory.md + a cross-person shared-topics digest at the
    vault root (Cross-Session-Memory.md). Returns the path written (the cross-person
    file in all-mode)."""
    root = Path(VAULT)
    team = root / "Team"

    if person_folder:
        name = PEOPLE.get(person_folder, person_folder.replace("-", " "))
        sessions = build_session_memory(read_file(str(team / person_folder / "1on1.md")))
        mem = summarize_person_memory(sessions)
        out_path = output or str(team / person_folder / "memory.md")
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text(_person_memory_md(name, mem), encoding="utf-8")
        print(f"  [OK] Memory: {out_path} ({mem['session_count']} sessoes, "
              f"{len(mem['open_actions'])} acoes abertas)")
        return out_path

    person_sessions = {}
    for folder in _team_folders(team):
        name = PEOPLE.get(folder, folder.replace("-", " "))
        sessions = build_session_memory(read_file(str(team / folder / "1on1.md")))
        person_sessions[name] = sessions
        (team / folder / "memory.md").write_text(
            _person_memory_md(name, summarize_person_memory(sessions)), encoding="utf-8")

    shared = cross_person_topics(person_sessions)
    gen = datetime.now().strftime("%Y-%m-%d")
    lines = [
        "---", "type: cross-session-memory", f"generated: {gen}",
        "tags: [memory, team, generated]", "ai-first: true", "---", "",
        "## For future Claude",
        ("Cross-person memory index: topics recurring across >=2 team members' 1:1s, "
         "aggregated deterministically (no LLM). Per-person digests live in "
         "Team/<person>/memory.md. Regenerated by `process.py memory`."),
        "",
        "# Cross-Session Memory - Team", "",
        f"People: {len(person_sessions)}", "",
        "## Shared topics across people", "",
    ]
    lines += ([f"- {t['topic']} - {', '.join(t['people'])}" for t in shared] or ["_none_"])
    out_path = output or str(root / "Cross-Session-Memory.md")
    Path(out_path).write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"  [OK] Cross-person memory: {out_path} "
          f"({len(shared)} shared topics, {len(person_sessions)} people)")
    return out_path


# ── Action Velocity (idea-031): how long action items take to close ─────────────

VELOCITY_STALE_DAYS = 30   # an open action older than this is flagged "stale"


def compute_action_velocity(sessions: list, today: str = None) -> dict:
    """Track each action's lifecycle across dated sessions to measure time-to-close.

    Actions are matched by normalized text across a person's 1:1 sessions. An action
    is 'closed' on the FIRST session it appears as [x]; 'open' if only ever [ ]. Days
    are counted from the first session it appeared. `today` (YYYY-MM-DD) ages still-
    open actions and defaults to the current date. Pure (inject `today` in tests)."""
    if today is None:
        today = datetime.now().strftime("%Y-%m-%d")

    chron = sorted(sessions, key=lambda s: s["date"])  # oldest first
    first_open, closed = {}, {}
    for s in chron:
        for a in s["actions"]:
            norm = _norm_text(a["text"])
            if not norm:
                continue
            first_open.setdefault(norm, {"text": a["text"], "opened": s["date"]})
            if a["done"] and norm not in closed:
                closed[norm] = s["date"]

    def _days(d1, d2):
        try:
            return (datetime.strptime(d2, "%Y-%m-%d") - datetime.strptime(d1, "%Y-%m-%d")).days
        except (ValueError, TypeError):
            return 0

    closed_list, open_list = [], []
    for norm, info in first_open.items():
        if norm in closed:
            closed_list.append({"text": info["text"], "opened": info["opened"],
                                "closed": closed[norm],
                                "days": max(0, _days(info["opened"], closed[norm]))})
        else:
            open_list.append({"text": info["text"], "opened": info["opened"],
                              "age_days": max(0, _days(info["opened"], today))})
    closed_list.sort(key=lambda x: (-x["days"], x["opened"]))
    open_list.sort(key=lambda x: (-x["age_days"], x["opened"]))

    vals = sorted(a["days"] for a in closed_list)
    def _median(v):
        if not v:
            return None
        n = len(v); m = n // 2
        return float(v[m]) if n % 2 else (v[m - 1] + v[m]) / 2
    stale = [a for a in open_list if a["age_days"] > VELOCITY_STALE_DAYS]
    return {
        "closed": closed_list,
        "open": open_list,
        "stale_open": stale,
        "count_closed": len(closed_list),
        "count_open": len(open_list),
        "avg_days_to_close": round(sum(vals) / len(vals), 1) if vals else None,
        "median_days_to_close": _median(vals),
    }


def _velocity_md(name: str, vel: dict) -> str:
    gen = datetime.now().strftime("%Y-%m-%d")
    avg = vel["avg_days_to_close"]
    med = vel["median_days_to_close"]
    lines = [
        "---", "type: action-velocity", f"generated: {gen}",
        f"person: {name}", "tags: [velocity, team, generated]", "ai-first: true", "---", "",
        "## For future Claude",
        (f"Action velocity for {name}, computed deterministically (no LLM) from their "
         f"1on1.md: how long action items take to go from [ ] to [x] across dated "
         f"sessions. {vel['count_closed']} closed, {vel['count_open']} open "
         f"({len(vel['stale_open'])} stale >{VELOCITY_STALE_DAYS}d). Regenerated by "
         f"`process.py velocity`."),
        "",
        f"# Action Velocity - {name}", "",
        (f"Closed: {vel['count_closed']} - Avg: {avg if avg is not None else 'n/a'}d - "
         f"Median: {med if med is not None else 'n/a'}d - Open: {vel['count_open']} "
         f"({len(vel['stale_open'])} stale)"),
        "", f"## Stale open actions (>{VELOCITY_STALE_DAYS}d)", "",
    ]
    lines += ([f"- [ ] {a['text']} _(open {a['age_days']}d, since {a['opened']})_"
               for a in vel["stale_open"]] or ["_none_"])
    lines += ["", "## Slowest closed actions", ""]
    lines += ([f"- {a['text']} — {a['days']}d ({a['opened']} -> {a['closed']})"
               for a in vel["closed"][:10]] or ["_none_"])
    return "\n".join(lines).rstrip() + "\n"


def cmd_velocity(person_folder: str = None, output: str = None) -> str:
    """Generate action-velocity digests (deterministic, no LLM).

    With --person: Team/<folder>/velocity.md. Without: every member + a team rollup
    at the vault root (Action-Velocity.md). Returns the path written."""
    root = Path(VAULT)
    team = root / "Team"

    if person_folder:
        name = PEOPLE.get(person_folder, person_folder.replace("-", " "))
        sessions = build_session_memory(read_file(str(team / person_folder / "1on1.md")))
        vel = compute_action_velocity(sessions)
        out_path = output or str(team / person_folder / "velocity.md")
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text(_velocity_md(name, vel), encoding="utf-8")
        print(f"  [OK] Velocity: {out_path} (closed={vel['count_closed']}, "
              f"open={vel['count_open']}, avg={vel['avg_days_to_close']}d)")
        return out_path

    rows, all_closed = [], []
    for folder in _team_folders(team):
        name = PEOPLE.get(folder, folder.replace("-", " "))
        vel = compute_action_velocity(
            build_session_memory(read_file(str(team / folder / "1on1.md"))))
        (team / folder / "velocity.md").write_text(_velocity_md(name, vel), encoding="utf-8")
        rows.append((name, vel))
        all_closed += vel["closed"]

    gen = datetime.now().strftime("%Y-%m-%d")
    team_vals = sorted(a["days"] for a in all_closed)
    team_avg = round(sum(team_vals) / len(team_vals), 1) if team_vals else "n/a"
    lines = [
        "---", "type: action-velocity", f"generated: {gen}",
        "tags: [velocity, team, generated]", "ai-first: true", "---", "",
        "## For future Claude",
        ("Team action-velocity rollup: time-to-close of action items per member, "
         "computed deterministically (no LLM). Per-person digests are in "
         "Team/<person>/velocity.md. Regenerated by `process.py velocity`."),
        "", "# Action Velocity - Team", "",
        f"Team avg time-to-close: {team_avg}d across {len(team_vals)} closed actions", "",
        "## By person", "",
        "| Person | Closed | Avg (d) | Open | Stale |",
        "|---|---|---|---|---|",
    ]
    for name, vel in sorted(rows, key=lambda r: r[0].lower()):
        avg = vel["avg_days_to_close"]
        lines.append(f"| {name} | {vel['count_closed']} | "
                     f"{avg if avg is not None else 'n/a'} | {vel['count_open']} | "
                     f"{len(vel['stale_open'])} |")
    out_path = output or str(root / "Action-Velocity.md")
    Path(out_path).write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"  [OK] Team velocity: {out_path} ({len(rows)} people, "
          f"team avg {team_avg}d)")
    return out_path


# ── PDI/OKR Alerts (idea-031): flag overdue deadlines and at-risk objectives ────

_DEADLINE_KEYS = ("deadline", "data de conclus", "data de entrega", "prazo")
# "concluíd" (concluído/concluída) marks done WITHOUT clashing with "conclusão"
# (a deadline keyword) — the latter has "conclus" but not "concluíd".
_DONE_MARKS    = ("✅", "completed", "concluíd", "[x]", " done", "status: done")
_OVERDUE_MARKS = ("overdue", "⚠️", "alerta", "alert", "vencid", "atrasad")


def _parse_any_date(s: str):
    """First date in `s` as a date, supporting YYYY-MM-DD and DD/MM/YYYY. None if none."""
    m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", s)
    if m:
        y, mo, d = m.group(1), m.group(2), m.group(3)
    else:
        m = re.search(r"\b(\d{2})/(\d{2})/(\d{4})\b", s)
        if not m:
            return None
        d, mo, y = m.group(1), m.group(2), m.group(3)
    try:
        return datetime(int(y), int(mo), int(d)).date()
    except ValueError:
        return None


def scan_pdi_okr_alerts(text: str, today=None) -> list:
    """Scan a PDI or OKR markdown for risk signals. Returns a deduped list of
    {kind, date, line}. kinds: 'overdue_deadline' (a deadline date in the past not
    marked done), 'explicit_overdue' (an OVERDUE/ALERTA marker), 'zero_progress'
    (Progress: 0%). Lines under a Completed/Concluídos section are ignored. Pure —
    `today` (date or 'YYYY-MM-DD') is injectable for tests."""
    if today is None:
        today = datetime.now().date()
    elif isinstance(today, str):
        today = datetime.strptime(today, "%Y-%m-%d").date()

    alerts, seen, section = [], set(), ""
    for raw in (text or "").splitlines():
        line = raw.strip()
        low = line.casefold()
        if line.startswith("## "):
            section = low
            continue
        if not line or ("completed" in section or "concluíd" in section):
            continue

        done = any(m in low for m in _DONE_MARKS)
        d = _parse_any_date(line)
        is_deadline = any(k in low for k in _DEADLINE_KEYS)

        kind, adate = None, (d.isoformat() if d else None)
        if any(m in low for m in _OVERDUE_MARKS) and not done:
            kind = "explicit_overdue"
        elif d and (is_deadline or line.startswith("|")) and d < today and not done:
            kind = "overdue_deadline"
        elif re.search(r"progr\w+[^0-9%]{0,10}0\s*%", low):
            # field form "Progress:** 0%" (progress -> 0% order), not prose like
            # "...with 0% progress..." in a preamble.
            kind, adate = "zero_progress", None

        if kind:
            key = (kind, adate, _norm_text(line)[:80])
            if key not in seen:
                seen.add(key)
                alerts.append({"kind": kind, "date": adate, "line": line})
    return alerts


def _alerts_md(name: str, okr: list, pdi: list) -> str:
    gen = datetime.now().strftime("%Y-%m-%d")
    total = len(okr) + len(pdi)
    lines = [
        "---", "type: pdi-okr-alerts", f"generated: {gen}",
        f"person: {name}", "tags: [alerts, team, generated]", "ai-first: true", "---", "",
        "## For future Claude",
        (f"PDI/OKR risk alerts for {name}, scanned deterministically (no LLM) from "
         f"OKR.md + PDI.md: {total} signal(s) (overdue deadlines, explicit OVERDUE "
         f"markers, 0% progress). Approximate — the source files mix formats and "
         f"repeated update blocks; verify before acting. Regenerated by `process.py alerts`."),
        "", f"# PDI/OKR Alerts - {name}", "",
        f"OKR: {len(okr)} - PDI: {len(pdi)}", "",
    ]
    for title, items in (("OKR alerts", okr), ("PDI alerts", pdi)):
        lines += [f"## {title}", ""]
        lines += ([f"- **[{a['kind']}]** {a['line']}" for a in items] or ["_none_"])
        lines += [""]
    return "\n".join(lines).rstrip() + "\n"


def cmd_alerts(person_folder: str = None, output: str = None) -> str:
    """Generate PDI/OKR risk-alert digests (deterministic, no LLM).

    With --person: Team/<folder>/alerts.md. Without: every member + a consolidated
    rollup at the vault root (PDI-OKR-Alerts.md). Returns the path written."""
    root = Path(VAULT)
    team = root / "Team"

    def _scan(folder):
        okr = scan_pdi_okr_alerts(read_file(str(team / folder / "OKR.md")))
        pdi = scan_pdi_okr_alerts(read_file(str(team / folder / "PDI.md")))
        return okr, pdi

    if person_folder:
        name = PEOPLE.get(person_folder, person_folder.replace("-", " "))
        okr, pdi = _scan(person_folder)
        out_path = output or str(team / person_folder / "alerts.md")
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text(_alerts_md(name, okr, pdi), encoding="utf-8")
        print(f"  [OK] Alerts: {out_path} ({len(okr) + len(pdi)} signals)")
        return out_path

    rows = []
    for folder in _team_folders(team):
        name = PEOPLE.get(folder, folder.replace("-", " "))
        okr, pdi = _scan(folder)
        (team / folder / "alerts.md").write_text(_alerts_md(name, okr, pdi), encoding="utf-8")
        rows.append((name, okr, pdi))

    gen = datetime.now().strftime("%Y-%m-%d")
    total = sum(len(o) + len(p) for _, o, p in rows)
    lines = [
        "---", "type: pdi-okr-alerts", f"generated: {gen}",
        "tags: [alerts, team, generated]", "ai-first: true", "---", "",
        "## For future Claude",
        ("Team PDI/OKR alert rollup: overdue deadlines / explicit OVERDUE markers / "
         "0% progress across every member's OKR.md + PDI.md, scanned deterministically "
         "(no LLM). Per-person digests live in Team/<person>/alerts.md. Approximate — "
         "verify before acting. Regenerated by `process.py alerts`."),
        "", "# PDI/OKR Alerts - Team", "",
        f"Total signals: {total} across {len(rows)} people", "",
    ]
    for name, okr, pdi in sorted(rows, key=lambda r: (-(len(r[1]) + len(r[2])), r[0].lower())):
        n = len(okr) + len(pdi)
        if not n:
            continue
        lines += [f"## {name} ({n})", ""]
        lines += [f"- **[{a['kind']}]** {a['line']}" for a in (okr + pdi)]
        lines += [""]
    out_path = output or str(root / "PDI-OKR-Alerts.md")
    Path(out_path).write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"  [OK] Team alerts: {out_path} ({total} signals, {len(rows)} people)")
    return out_path


# ── Team Health Metrics (idea-031): consolidate per-person signals into an index ─

def compute_person_health(mem: dict, velocity: dict, alert_count: int, today=None) -> dict:
    """Combine cross-session signals into a simple health record and score (0-100,
    higher = healthier). Penalizes stale contact (days since last 1:1), stale/backlogged
    open actions, and PDI/OKR alerts. Deterministic; `today` (date or 'YYYY-MM-DD')
    injectable. Composes summarize_person_memory + compute_action_velocity +
    scan_pdi_okr_alerts outputs — the 'consolidates signals from all 1:1s' feature."""
    if today is None:
        today = datetime.now().date()
    elif isinstance(today, str):
        today = datetime.strptime(today, "%Y-%m-%d").date()

    if mem.get("session_count", 0) == 0:
        return {"score": None, "status": "no-data", "days_since_last": None,
                "open": 0, "stale": 0, "alerts": alert_count,
                "signals": ["no 1:1 sessions on record"]}

    days_since = None
    last = mem.get("last_date")
    if last:
        try:
            days_since = (today - datetime.strptime(last, "%Y-%m-%d").date()).days
        except (ValueError, TypeError):
            days_since = None

    score, signals = 100, []
    if days_since is not None and days_since > 60:
        score -= 30; signals.append(f"last 1:1 was {days_since}d ago (>60d)")
    elif days_since is not None and days_since > 30:
        score -= 15; signals.append(f"last 1:1 was {days_since}d ago (>30d)")

    n_stale = len(velocity.get("stale_open", []))
    if n_stale:
        score -= min(25, 5 * n_stale); signals.append(f"{n_stale} stale open action(s)")

    n_open = velocity.get("count_open", 0)
    if n_open > 5:
        score -= min(15, 2 * (n_open - 5)); signals.append(f"{n_open} open actions (backlog)")

    if alert_count:
        score -= min(25, 5 * alert_count); signals.append(f"{alert_count} PDI/OKR alert(s)")

    score = max(0, min(100, score))
    status = "healthy" if score >= 75 else "watch" if score >= 50 else "at-risk"
    return {"score": score, "status": status, "days_since_last": days_since,
            "open": n_open, "stale": n_stale, "alerts": alert_count, "signals": signals}


def _health_md(name: str, h: dict) -> str:
    gen = datetime.now().strftime("%Y-%m-%d")
    sc = h["score"] if h["score"] is not None else "n/a"
    ds = h["days_since_last"] if h["days_since_last"] is not None else "n/a"
    lines = [
        "---", "type: team-health", f"generated: {gen}",
        f"person: {name}", "tags: [health, team, generated]", "ai-first: true", "---", "",
        "## For future Claude",
        (f"Team-health snapshot for {name}, computed deterministically (no LLM) by "
         f"consolidating 1:1 recency, open/stale action load and PDI/OKR alerts into a "
         f"0-100 score (higher = healthier). Score {sc}, status '{h['status']}'. A "
         f"management signal, not a verdict. Regenerated by `process.py health`."),
        "", f"# Team Health - {name}", "",
        f"Score: {sc}/100 - Status: {h['status']}", "",
        (f"Last 1:1: {ds}d ago - Open actions: {h['open']} - Stale: {h['stale']} - "
         f"PDI/OKR alerts: {h['alerts']}"), "",
        "## Contributing signals", "",
    ]
    lines += ([f"- {s}" for s in h["signals"]] or ["_none - looking healthy_"])
    return "\n".join(lines).rstrip() + "\n"


def cmd_health(person_folder: str = None, output: str = None) -> str:
    """Generate team-health digests (deterministic, no LLM) by consolidating the
    memory / velocity / alerts signals. With --person: Team/<folder>/health.md.
    Without: every member + a team rollup at the vault root (Team-Health.md)."""
    root = Path(VAULT)
    team = root / "Team"

    def _health(folder):
        sessions = build_session_memory(read_file(str(team / folder / "1on1.md")))
        mem = summarize_person_memory(sessions)
        vel = compute_action_velocity(sessions)
        n_alerts = (len(scan_pdi_okr_alerts(read_file(str(team / folder / "OKR.md")))) +
                    len(scan_pdi_okr_alerts(read_file(str(team / folder / "PDI.md")))))
        return compute_person_health(mem, vel, n_alerts)

    if person_folder:
        name = PEOPLE.get(person_folder, person_folder.replace("-", " "))
        h = _health(person_folder)
        out_path = output or str(team / person_folder / "health.md")
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text(_health_md(name, h), encoding="utf-8")
        print(f"  [OK] Health: {out_path} (score={h['score']}, status={h['status']})")
        return out_path

    rows = []
    for folder in _team_folders(team):
        name = PEOPLE.get(folder, folder.replace("-", " "))
        h = _health(folder)
        (team / folder / "health.md").write_text(_health_md(name, h), encoding="utf-8")
        rows.append((name, h))

    gen = datetime.now().strftime("%Y-%m-%d")
    # worst first: at-risk before watch before healthy; None scores (no-data) last
    rows.sort(key=lambda r: (r[1]["score"] is None, r[1]["score"] if r[1]["score"] is not None else 999, r[0].lower()))
    lines = [
        "---", "type: team-health", f"generated: {gen}",
        "tags: [health, team, generated]", "ai-first: true", "---", "",
        "## For future Claude",
        ("Team-health rollup: a 0-100 score per member (higher = healthier) consolidating "
         "1:1 recency, open/stale action load and PDI/OKR alerts, computed deterministically "
         "(no LLM). Sorted worst-first. Per-person digests live in Team/<person>/health.md. "
         "A management signal, not a verdict. Regenerated by `process.py health`."),
        "", "# Team Health", "",
        "| Person | Score | Status | Last 1:1 | Open | Stale | Alerts |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, h in rows:
        sc = h["score"] if h["score"] is not None else "n/a"
        ds = f"{h['days_since_last']}d" if h["days_since_last"] is not None else "n/a"
        lines.append(f"| {name} | {sc} | {h['status']} | {ds} | {h['open']} | "
                     f"{h['stale']} | {h['alerts']} |")
    out_path = output or str(root / "Team-Health.md")
    Path(out_path).write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    at_risk = sum(1 for _, h in rows if h["status"] == "at-risk")
    print(f"  [OK] Team health: {out_path} ({len(rows)} people, {at_risk} at-risk)")
    return out_path


# Structured monthly 1:1 questions (idea-020 — Just to Talk, 4 perguntas fixas)
_STRUCTURED_QUESTIONS = [
    "Como você tem se sentido em relação à sua carga de trabalho nas últimas semanas?",
    "Se você pudesse ajustar algo na forma como o trabalho é distribuído, o que mudaria?",
    "Como você percebe a colaboração entre as pessoas do time no dia a dia?",
    "O que poderia ser feito para o time se sentir mais conectado e alinhado como grupo?",
]


def cmd_transcript(person_folder: str, transcript_file: str, date: str,
                   structured: bool = False, lang: str = "pt"):
    """Process a 1:1 transcript and save structured blocks to the vault."""
    person_name = PEOPLE.get(person_folder, person_folder.replace("-", " "))
    first_name  = person_name.split()[0]
    team_path   = Path(VAULT) / "Team" / person_folder

    overview   = read_file(str(team_path / "Overview.md"),  max_chars=1500)
    okr        = read_file(str(team_path / "OKR.md"),       max_chars=1000)
    pdi        = read_file(str(team_path / "PDI.md"),       max_chars=1000)
    transcript = read_file(transcript_file)

    if not transcript.strip():
        print(f"[ERROR] Transcricao vazia ou nao encontrada: {transcript_file}")
        sys.exit(1)

    # Keep enough of the real conversation (a 1:1 is usually >4k chars; the first
    # 4k is often just the opening/audio-check). 12k chars is well within the model.
    transcript = transcript[:12000]

    # ── Build BLOCO 1on1 template and optional structured-meeting context ─────
    if structured:
        q_list = "\n".join(f"  P{i+1}. {q}" for i, q in enumerate(_STRUCTURED_QUESTIONS))
        structured_context = f"""
ATENCAO: Esta foi uma REUNIAO ESTRUTURADA MENSAL. As perguntas feitas foram:
{q_list}

Mapeie as respostas do liderado a cada pergunta. No BLOCO 1on1, inclua a secao
"Perguntas estruturadas" com o resumo de cada resposta."""

        bloco_1on1 = f"""### BLOCO 1on1
~~~markdown
## {date} — Reunião estruturada

**Perguntas estruturadas:**
- P1 — Carga de trabalho: [resposta resumida]
- P2 — Distribuição do trabalho: [resposta resumida]
- P3 — Colaboração no time: [resposta resumida]
- P4 — Conexão e alinhamento: [resposta resumida]

**Action items:**
- [ ] (Kelvin) [acao]
- [ ] ({first_name}) [acao]
~~~"""
    else:
        structured_context = ""
        bloco_1on1 = f"""### BLOCO 1on1
~~~markdown
## {date}

**Topics:**
- [topico 1]

**Action items:**
- [ ] (Kelvin) [acao]
- [ ] ({first_name}) [acao]
~~~"""

    prompt = f"""Voce e um assistente de gestao de pessoas. Analise a transcricao de um 1:1 e estruture para o Obsidian.

Pessoa: {person_name} | Data: {date}
{structured_context}
Contexto (apenas referencia de quem e a pessoa — NAO copie nada daqui):
Overview: {overview}
OKR: {okr}
PDI: {pdi}

REGRA CRITICA: Os Topics e Action items devem refletir EXCLUSIVAMENTE o que foi dito
na transcricao abaixo. NUNCA reutilize topicos de sessoes anteriores nem do contexto.
Se a transcricao for curta/inconclusiva, gere poucos topicos reais — nao invente.

Transcricao da conversa:
---
{transcript}
---

Classifique cada assunto em: 1on1 / OKR / PDI / Overview
Para cada categoria COM conteudo, gere um bloco usando EXATAMENTE este formato:

{bloco_1on1}

### BLOCO OKR
~~~markdown
## Atualizacao {date}
[resumo OKR]
~~~

### BLOCO PDI
~~~markdown
## Atualizacao {date}
[resumo PDI]
~~~

### BLOCO Overview
~~~markdown
## Atualizacao {date}
[contexto relevante]
~~~

Responda APENAS com os blocos gerados, sem texto adicional."""

    label = "reuniao estruturada" if structured else "transcricao"
    print(f"\n  [Ollama] Processando {label}...\n")
    response = _ollama_generate(prompt, stream=True)

    _strip_dated_1on1(team_path / "1on1.md", date)  # idempotent: replace, don't duplicate
    saved = _parse_and_save(response, team_path, SECTION_MAP, SECTION_MODE)
    if saved == 0:
        _fallback_1on1(team_path / "1on1.md", date)

    # Standalone session note
    standalone_dir  = team_path / "1on1"
    standalone_dir.mkdir(parents=True, exist_ok=True)
    standalone_file = standalone_dir / f"{date}_1on1_{person_folder}.md"
    header = (
        f"---\ndate: {date}\nperson: {person_name}\n"
        f"type: 1on1-session\nlang: {lang}\ntags: [1on1, team]\n---\n\n"
    )
    standalone_file.write_text(header + response, encoding="utf-8")
    print(f"  [OK] Nota standalone: {standalone_file.name}")
    print(f"\n  Concluido. {saved + 1} arquivo(s) atualizados.")


def cmd_manager(manager_folder: str, transcript_file: str, date: str, lang: str = "pt"):
    """Process a manager/stakeholder call transcript and save to vault."""
    manager_name = MANAGERS.get(manager_folder, manager_folder.replace("-", " "))
    first_name   = manager_name.split()[0]
    stk_path     = Path(VAULT) / "Stakeholders" / manager_folder

    overview   = read_file(str(stk_path / "Overview.md"), max_chars=1500)
    transcript = read_file(transcript_file)

    if not transcript.strip():
        print(f"[ERROR] Transcricao vazia ou nao encontrada: {transcript_file}")
        sys.exit(1)

    transcript = transcript[:12000]  # keep the real conversation, not just the opening

    prompt = f"""Voce e um assistente de gestao de pessoas. Analise a transcricao de uma reuniao com o gestor e estruture para o Obsidian.

Pessoa: {manager_name} (gestor/superior hierarquico) | Data: {date}

Contexto (apenas referencia — NAO copie nada daqui):
Visao geral: {overview}

REGRA CRITICA: Os Topics e Action items devem refletir EXCLUSIVAMENTE o que foi dito
na transcricao abaixo. NUNCA reutilize topicos de reunioes anteriores nem do contexto.

Transcricao da conversa:
---
{transcript}
---

Classifique cada assunto em: 1on1 / Overview
Para cada categoria COM conteudo, gere um bloco usando EXATAMENTE este formato:

### BLOCO 1on1
~~~markdown
## {date}

**Topics:**
- [topico 1]

**Action items:**
- [ ] (Kelvin) [acao]
- [ ] ({first_name}) [acao]
~~~

### BLOCO Overview
~~~markdown
## Atualizacao {date}
[contexto relevante sobre o relacionamento com o gestor, feedbacks recebidos, alinhamentos estrategicos, expectativas]
~~~

Responda APENAS com os blocos gerados, sem texto adicional."""

    print("\n  [Ollama] Processando transcricao do gestor...\n")
    response = _ollama_generate(prompt, stream=True)

    _strip_dated_1on1(stk_path / "1on1.md", date)  # idempotent: replace, don't duplicate
    saved = _parse_and_save(response, stk_path, MANAGER_SECTION_MAP, MANAGER_SECTION_MODE)
    if saved == 0:
        _fallback_1on1(stk_path / "1on1.md", date)

    # Standalone session note
    standalone_dir  = stk_path / "1on1"
    standalone_dir.mkdir(parents=True, exist_ok=True)
    standalone_file = standalone_dir / f"{date}_1on1_{manager_folder}.md"
    header = (
        f"---\ndate: {date}\nperson: {manager_name}\n"
        f"type: manager-call\nlang: {lang}\ntags: [manager, stakeholder]\n---\n\n"
    )
    standalone_file.write_text(header + response, encoding="utf-8")
    print(f"  [OK] Nota standalone: {standalone_file.name}")
    print(f"\n  Concluido. {saved + 1} arquivo(s) atualizados.")


def cmd_note(transcript_path: str, date: str, lang: str = "pt", time_str: str = None):
    """Save a standalone (loose) note to Inbox/ for later triage.

    Used by the 'Outro' category in the recorder: the conversation does not map to
    a team member or stakeholder, so it is captured + summarized and parked in the
    vault Inbox to be classified later (turn into a backlog idea, attach to a
    person, or discard)."""
    transcript = read_file(transcript_path)
    if not transcript.strip():
        print("[ERROR] Transcript vazio.")
        sys.exit(1)
    if not time_str:
        time_str = datetime.now().strftime("%H-%M")

    lang_word = "ingles" if lang == "en" else "portugues"
    prompt = (
        "Voce e um assistente que organiza notas avulsas para triagem posterior.\n"
        f"A transcricao abaixo (em {lang_word}) e uma nota solta sem dono definido.\n"
        "Resuma em 3 a 5 bullets objetivos, em portugues, capturando o assunto "
        "principal, qualquer decisao e qualquer acao mencionada. "
        "Responda APENAS com os bullets, sem preambulo.\n\n"
        f"=== TRANSCRICAO ===\n{transcript[:6000]}"
    )
    print("\n  [Ollama] Resumindo nota avulsa...\n")
    summary = _ollama_generate(prompt, stream=True).strip()

    inbox = Path(VAULT) / "Inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    fname = f"{date}_{time_str}_nota-avulsa.md"
    fpath = inbox / fname
    header = (
        "---\n"
        f"date: {date}\n"
        f"time: {time_str.replace('-', ':')}\n"
        "type: nota-avulsa\n"
        "status: a-triar\n"
        f"lang: {lang}\n"
        "tags: [inbox, triage]\n"
        "---\n\n"
    )
    body = "## Resumo\n\n" + summary + "\n\n## Transcricao\n\n" + transcript.strip() + "\n"
    fpath.write_text(header + body, encoding="utf-8")
    print(f"\n  [OK] Nota avulsa salva: Inbox/{fname}")
    print("  Status: a-triar (classifique depois no vault).")


def cmd_capture(mode: str, transcript_path: str, date: str,
                lang: str = "pt", time_str: str = None):
    """Structure a standalone session (project meeting / retrospective / idea
    capture) into an Inbox note for later triage. See CAPTURE_MODES (idea-031)."""
    cfg = CAPTURE_MODES.get(mode)
    if not cfg:
        print(f"[ERROR] Modo de captura desconhecido: {mode}")
        sys.exit(1)

    transcript = read_file(transcript_path)
    if not transcript.strip():
        print("[ERROR] Transcript vazio.")
        sys.exit(1)
    if not time_str:
        time_str = datetime.now().strftime("%H-%M")

    lang_word = "ingles" if lang == "en" else "portugues"
    prompt = (
        "Voce e um assistente que organiza transcricoes em notas estruturadas para o Obsidian.\n"
        f"A transcricao abaixo (em {lang_word}) e de uma {cfg['label']}.\n"
        f"{cfg['instructions']}\n"
        "Baseie-se EXCLUSIVAMENTE na transcricao; nao invente. "
        "Responda APENAS com o conteudo em markdown, sem preambulo.\n\n"
        f"=== TRANSCRICAO ===\n{transcript[:8000]}"
    )
    print(f"\n  [Ollama] Organizando {cfg['label']}...\n")
    summary = _ollama_generate(prompt, stream=True).strip()

    inbox = Path(VAULT) / "Inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    fname = f"{date}_{time_str}_{cfg['suffix']}.md"
    fpath = inbox / fname
    header = (
        "---\n"
        f"date: {date}\n"
        f"time: {time_str.replace('-', ':')}\n"
        f"type: {cfg['type']}\n"
        f"status: {cfg['status']}\n"
        f"lang: {lang}\n"
        "tags: [inbox, triage]\n"
        "---\n\n"
    )
    body = summary + "\n\n## Transcricao\n\n" + transcript.strip() + "\n"
    fpath.write_text(header + body, encoding="utf-8")
    print(f"\n  [OK] Nota salva: Inbox/{fname}")
    print(f"  Status: {cfg['status']} (classifique depois no vault).")


# ── Action Dashboard: consolidate open `- [ ]` across the vault (idea-031) ────

DASHBOARD_FILE = "Action-Dashboard.md"
DASHBOARD_EXCLUDE_DIRS = {
    ".obsidian", "_attachments", "Archive", "raw", "Clippings",
    ".git", ".trash", "node_modules",
    "agent-reports",  # daily generated snapshots that echo open actions — not a task source
}
_TASK_RE  = re.compile(r"^\s*[-*]\s+\[ \]\s+(.*\S)\s*$")
_OWNER_RE = re.compile(r"^\((?P<owner>[^)]{1,40})\)\s*(?P<rest>.*)$")
_DUE_RE   = re.compile(r"@(\d{4}-\d{2}-\d{2})")
_STATUS_RE = re.compile(r"^status:\s*['\"]?([^'\"\n]+?)['\"]?\s*$", re.MULTILINE)
# A note whose backlog status is closed contributes no live actions (its `- [ ]`
# sub-todos are stale). Covers accented/unaccented spellings.
_CLOSED_STATUSES = {"concluído", "concluido", "descartado"}


def _is_closed_note(text: str) -> bool:
    """True if the note's leading frontmatter marks it concluído/descartado."""
    if not text.startswith("---"):
        return False
    end = text.find("\n---", 3)
    fm = text[:end] if end != -1 else text
    m = _STATUS_RE.search(fm)
    return bool(m and m.group(1).strip().casefold() in _CLOSED_STATUSES)


def _collect_open_tasks(root: Path, output_name: str) -> list:
    """Walk the vault and return every open `- [ ]` task with owner/due/source."""
    tasks = []
    for md in root.rglob("*.md"):
        rel = md.relative_to(root)
        if any(part in DASHBOARD_EXCLUDE_DIRS for part in rel.parts):
            continue
        if md.name == output_name:
            continue
        try:
            text = md.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        if _is_closed_note(text):        # skip concluído/descartado notes wholesale
            continue
        for line in text.splitlines():
            m = _TASK_RE.match(line)
            if not m:
                continue
            body = m.group(1).strip()
            owner = None
            om = _OWNER_RE.match(body)
            if om:
                owner = om.group("owner").strip()
                body = om.group("rest").strip()
            dm = _DUE_RE.search(body)
            due = dm.group(1) if dm else None
            # Signal filter: a real action item has an owner (Name) OR a due @date.
            # Plain `- [ ]` lines (template checklists, study docs) are noise — skip.
            if owner is None and due is None:
                continue
            body = _DUE_RE.sub("", body).strip(" -·")  # drop the @date from display text
            tasks.append({"owner": owner or "sem dono", "text": body,
                          "due": due, "stem": md.stem})
    return tasks


# How many source backlinks to show inline before collapsing to "+N".
MAX_SOURCES = 5


def _norm(s: str) -> str:
    """Case/whitespace-insensitive key for matching the same action across files."""
    return re.sub(r"\s+", " ", s).strip().casefold()


def _dedup_tasks(tasks: list) -> list:
    """Collapse identical action items that appear in multiple source files.

    Vault cross-linking means the same 1:1 action lands in the cumulative
    `1on1.md`, the per-meeting note, a daily note AND every `agent-reports/
    report-*.md` that carried it forward. Without dedup the same action is
    counted many times (e.g. one Tailscale to-do appeared ~30x). Key is
    (owner, normalized text, due); the surviving entry keeps every distinct
    source stem so each origin can still be cleaned up. Insertion order is
    preserved so downstream sorting stays deterministic.
    """
    grouped: dict = {}
    order: list = []
    for t in tasks:
        key = (_norm(t["owner"]), _norm(t["text"]), t["due"] or "")
        g = grouped.get(key)
        if g is None:
            g = {"owner": t["owner"], "text": t["text"],
                 "due": t["due"], "stems": []}
            grouped[key] = g
            order.append(key)
        if t["stem"] not in g["stems"]:
            g["stems"].append(t["stem"])
    return [grouped[k] for k in order]


def cmd_dashboard(output_name: str = DASHBOARD_FILE) -> dict:
    """Generate a single markdown note consolidating all open action items in the
    vault, grouped by due status (overdue / today / upcoming / no date). Regenerated
    on each run. Returns counts."""
    root = Path(VAULT)
    tasks = _dedup_tasks(_collect_open_tasks(root, output_name))
    today = datetime.now().date()

    def _d(s):
        try:
            return datetime.strptime(s, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return None

    overdue, due_today, upcoming, undated = [], [], [], []
    for t in tasks:
        d = _d(t["due"])
        if d is None:
            undated.append(t)
        elif d < today:
            overdue.append(t)
        elif d == today:
            due_today.append(t)
        else:
            upcoming.append(t)
    for grp in (overdue, due_today, upcoming):
        grp.sort(key=lambda t: (t["due"] or "", t["owner"].lower()))
    undated.sort(key=lambda t: (t["owner"].lower(), t["stems"][0].lower()))

    # per-owner counts
    owners = {}
    for t in tasks:
        owners[t["owner"]] = owners.get(t["owner"], 0) + 1

    def _line(t):
        due = f" — `{t['due']}`" if t["due"] else ""
        stems = t["stems"]
        shown = " ".join(f"[[{s}]]" for s in stems[:MAX_SOURCES])
        if len(stems) > MAX_SOURCES:
            shown += f" +{len(stems) - MAX_SOURCES}"
        dup = f" ×{len(stems)}" if len(stems) > 1 else ""
        return f"- [ ] ({t['owner']}) {t['text']}{due}{dup} · {shown}"

    def _section(title, items):
        if not items:
            return ""
        return f"## {title} ({len(items)})\n\n" + "\n".join(_line(t) for t in items) + "\n\n"

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    owner_summary = " · ".join(
        f"{o}: {n}" for o, n in sorted(owners.items(), key=lambda kv: (-kv[1], kv[0].lower()))
    ) or "nenhuma"

    out = (
        "---\n"
        f"date: {datetime.now().strftime('%Y-%m-%d')}\n"
        "type: dashboard\n"
        "generated: true\n"
        "tags: [dashboard, actions, generated]\n"
        "---\n\n"
        "> **Gerado automaticamente** por `process.py dashboard`. Nao editar a mao "
        "(sobrescrito a cada execucao). Marque os itens no arquivo de origem.\n"
        "> Escopo: apenas itens de acao com **dono** `(Nome)` ou **prazo** `@data` "
        "(checklists de template sao ignorados).\n\n"
        f"# Action Dashboard\n\n"
        f"Atualizado: {now} · {len(tasks)} acoes abertas · por dono: {owner_summary}\n\n"
        + _section("Atrasadas", overdue)
        + _section("Hoje", due_today)
        + _section("Proximas", upcoming)
        + _section("Sem prazo", undated)
    ).rstrip() + "\n"

    (root / output_name).write_text(out, encoding="utf-8")
    counts = {"total": len(tasks), "overdue": len(overdue), "today": len(due_today),
              "upcoming": len(upcoming), "undated": len(undated)}
    print(f"[dashboard] {output_name}: total={counts['total']} overdue={counts['overdue']} "
          f"today={counts['today']} upcoming={counts['upcoming']} undated={counts['undated']}")
    return counts


# ── Sweep: reprocess failed/partial call processings ─────────────────────────

def _classify_transcript(name: str):
    """Map a transcript filename to (date, time, target, kind).
    kind ∈ {'person','manager','note','unknown'}. Returns None if not a transcript."""
    m = re.match(r"^(\d{4}-\d{2}-\d{2})_(\d{2}-\d{2})_(.+)\.txt$", name)
    if not m:
        return None
    d, t, rest = m.group(1), m.group(2), m.group(3)
    if rest == "nota-avulsa":
        return (d, t, None, "note")
    if rest in SUFFIX_TO_MODE:
        return (d, t, None, SUFFIX_TO_MODE[rest])
    if (Path(VAULT) / "Team" / rest).is_dir():
        return (d, t, rest, "person")
    if (Path(VAULT) / "Stakeholders" / rest).is_dir():
        return (d, t, rest, "manager")
    return (d, t, rest, "unknown")


def _is_processed(d: str, t: str, target, kind: str) -> bool:
    """A call is 'successfully processed' when its result is visible in the vault:
    for person/manager, a `## {date}` section exists in 1on1.md; for a loose note,
    the Inbox file exists."""
    if kind == "note":
        return (Path(VAULT) / "Inbox" / f"{d}_{t}_nota-avulsa.md").exists()
    if kind in CAPTURE_MODES:
        suffix = CAPTURE_MODES[kind]["suffix"]
        return (Path(VAULT) / "Inbox" / f"{d}_{t}_{suffix}.md").exists()
    base = "Team" if kind == "person" else "Stakeholders"
    oneonone = Path(VAULT) / base / target / "1on1.md"
    if not oneonone.exists():
        return False
    return f"## {d}" in oneonone.read_text(encoding="utf-8", errors="replace")


def cmd_sweep(transcripts_dir: str = None, min_age_min: int = 5,
              dry_run: bool = False, lang: str = "pt", max_age_days: int = 7) -> dict:
    """Scan transcripts/ and reprocess any whose vault note is missing (failed or
    partial processing). Only considers transcripts from the last `max_age_days`
    (older failures are left alone — likely abandoned, and a back-dated section
    would land out of order). Safe to run daily: already-processed calls are
    skipped, and the BLOCO fallback guarantees reprocessing lands a section.
    Returns {'reprocessed', 'ok', 'failed', 'skipped'} lists of filenames."""
    tdir = Path(transcripts_dir) if transcripts_dir else (Path(__file__).parent / "transcripts")
    result = {"reprocessed": [], "ok": [], "failed": [], "skipped": []}
    if not tdir.exists():
        print(f"[sweep] No transcripts dir: {tdir}")
        return result

    if not dry_run:
        try:
            requests.get("http://localhost:11434/", timeout=3)
        except Exception:
            print("[sweep] Ollama unreachable — skipping reprocessing.")
            return result

    now = datetime.now().timestamp()
    for f in sorted(tdir.glob("*.txt")):
        info = _classify_transcript(f.name)
        if not info:
            continue
        d, t, target, kind = info
        if kind == "unknown":
            result["skipped"].append(f.name); continue
        if _is_processed(d, t, target, kind):
            result["ok"].append(f.name); continue
        _age = now - f.stat().st_mtime
        if _age < min_age_min * 60:
            result["skipped"].append(f.name); continue  # may still be in-flight
        if _age > max_age_days * 86400:
            result["skipped"].append(f.name); continue  # too old — leave alone
        if dry_run:
            result["reprocessed"].append(f.name); continue
        # Language: prefer the per-transcript sidecar written by record.py at
        # transcription time (<name>.txt.lang) over this sweep's blanket default.
        # Without it the sweep stamped `lang: pt` on every note it recreated, even
        # when Whisper had detected English -- which is how the 2026-08-10 English
        # 1:1 ended up invisible to agent/english_coach.py (it filters `lang: en`).
        file_lang = lang
        sidecar = f.parent / (f.name + ".lang")
        try:
            if sidecar.exists():
                detected = sidecar.read_text(encoding="utf-8").strip().lower()
                if detected:
                    file_lang = detected
        except OSError:
            pass
        try:
            if kind == "person":
                cmd_transcript(target, str(f), d, structured=False, lang=file_lang)
            elif kind == "manager":
                cmd_manager(target, str(f), d, lang=file_lang)
            elif kind == "note":
                cmd_note(str(f), d, lang=file_lang, time_str=t)
            elif kind in CAPTURE_MODES:
                cmd_capture(kind, str(f), d, lang=file_lang, time_str=t)
            result["reprocessed"].append(f.name)
        except SystemExit:
            result["failed"].append(f.name)
        except Exception as e:
            result["failed"].append(f"{f.name}: {e}")

    print(f"[sweep] reprocessed={len(result['reprocessed'])} ok={len(result['ok'])} "
          f"failed={len(result['failed'])} skipped={len(result['skipped'])}")
    return result


def cmd_queue(recordings_dir: str = None, dry_run: bool = False) -> dict:
    """Process queued recordings produced by the decoupled recorder: a `<base>.wav`
    plus a `<base>.job.json` sidecar. Transcribes with Whisper, then routes to the
    right command (transcript/manager/note) and runs the English coach when flagged.
    Meant to run in the idle-time daily agent so Whisper+LLM stay off working hours."""
    rdir = Path(recordings_dir) if recordings_dir else (Path(__file__).parent / "recordings")
    result = {"processed": [], "failed": [], "skipped": []}
    jobs = sorted(rdir.glob("*.job.json")) if rdir.exists() else []
    if not jobs:
        return result

    if not dry_run:
        try:
            requests.get("http://localhost:11434/", timeout=3)
        except Exception:
            print("[queue] Ollama unreachable — skipping.")
            return result

    for jf in jobs:
        try:
            job = json.loads(jf.read_text(encoding="utf-8"))
        except Exception:
            result["failed"].append(jf.name)
            continue
        wav = Path(job.get("wav", ""))
        if not wav.is_absolute():
            wav = rdir / wav.name
        if not wav.exists():
            jf.unlink()  # orphan job (wav pruned/missing) — drop it
            result["skipped"].append(jf.name)
            continue
        if dry_run:
            result["processed"].append(jf.name)
            continue
        try:
            import record  # lazy: loads Whisper only when transcribing
            lang = job.get("lang", "pt")
            whisper_lang = None if lang == "auto" else lang
            transcript_text, detected_lang = record.transcribe(str(wav), language=whisper_lang)
            effective_lang = detected_lang if lang == "auto" else lang
            tpath = Path(job["transcript"])
            tpath.parent.mkdir(parents=True, exist_ok=True)
            tpath.write_text(transcript_text, encoding="utf-8")

            kind, date = job["kind"], job["date"]
            if kind == "person":
                cmd_transcript(job["target"], str(tpath), date,
                               structured=job.get("structured", False), lang=effective_lang)
            elif kind == "manager":
                cmd_manager(job["target"], str(tpath), date, lang=effective_lang)
            elif kind == "note":
                cmd_note(str(tpath), date, lang=effective_lang, time_str=job.get("time"))
            elif kind in CAPTURE_MODES:
                cmd_capture(kind, str(tpath), date, lang=effective_lang, time_str=job.get("time"))

            # Run coach if: explicit coach flag OR auto-detected English
            run_coach = job.get("coach") or (lang == "auto" and effective_lang == "en")
            if run_coach:
                coach_py = str(Path(__file__).parent / "coach.py")
                subprocess.run([sys.executable, coach_py, "--transcript", str(tpath)], check=False)

            jf.unlink()
            result["processed"].append(jf.name)
        except Exception as e:
            result["failed"].append(f"{jf.name}: {e}")

    print(f"[queue] processed={len(result['processed'])} "
          f"failed={len(result['failed'])} skipped={len(result['skipped'])}")
    return result


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Ollama LLM integration for call-recorder (no API key required)"
    )
    sub = parser.add_subparsers(dest="command")

    a = sub.add_parser("agenda", help="Suggest a 1:1 agenda")
    a.add_argument("--person", required=True, help="Team member folder, e.g. Ana-Leite")

    t = sub.add_parser("transcript", help="Process a 1:1 transcript")
    t.add_argument("--person",     required=True, help="Team member folder, e.g. Ana-Leite")
    t.add_argument("--transcript", required=True, help="Path to transcript .txt")
    t.add_argument("--date",       required=True, help="YYYY-MM-DD")
    t.add_argument("--structured", action="store_true", default=False,
                   help="Flag as monthly structured 1:1 — maps answers to the 5 template questions")
    t.add_argument("--lang",       default="pt", choices=["pt", "en"],
                   help="Recording language — pt (default) or en")

    m = sub.add_parser("manager", help="Process a manager/stakeholder call transcript")
    m.add_argument("--manager",    required=True, help="Manager folder, e.g. Alberto-Reuters")
    m.add_argument("--transcript", required=True, help="Path to transcript .txt")
    m.add_argument("--date",       required=True, help="YYYY-MM-DD")
    m.add_argument("--lang",       default="pt", choices=["pt", "en"],
                   help="Recording language — pt (default) or en")

    n = sub.add_parser("note", help="Save a standalone (loose) note to Inbox for later triage")
    n.add_argument("--transcript", required=True, help="Path to transcript .txt")
    n.add_argument("--date",       required=True, help="YYYY-MM-DD")
    n.add_argument("--time",       default=None, help="HH-MM (default: now)")
    n.add_argument("--lang",       default="pt", choices=["pt", "en"],
                   help="Recording language — pt (default) or en")

    cap = sub.add_parser("capture", help="Structure a project meeting / retrospective / idea capture into Inbox")
    cap.add_argument("--mode",       required=True, choices=list(CAPTURE_MODES.keys()),
                     help="project | retro | idea")
    cap.add_argument("--transcript", required=True, help="Path to transcript .txt")
    cap.add_argument("--date",       required=True, help="YYYY-MM-DD")
    cap.add_argument("--time",       default=None, help="HH-MM (default: now)")
    cap.add_argument("--lang",       default="pt", choices=["pt", "en"],
                     help="Recording language — pt (default) or en")

    sw = sub.add_parser("sweep", help="Reprocess transcripts whose vault note is missing (failed/partial)")
    sw.add_argument("--dir",         default=None, help="Transcripts dir (default: ./transcripts)")
    sw.add_argument("--min-age-min", type=int, default=5, help="Skip files newer than this (in-flight)")
    sw.add_argument("--max-age-days", type=int, default=7, help="Skip files older than this (abandoned)")
    sw.add_argument("--dry-run",     action="store_true", help="List what would be reprocessed, don't run")
    sw.add_argument("--lang",        default="pt", choices=["pt", "en"], help="Language for reprocessing")

    q = sub.add_parser("queue", help="Process queued recordings (record-only .wav + .job.json)")
    q.add_argument("--dir",     default=None, help="recordings dir (default: ./recordings)")
    q.add_argument("--dry-run", action="store_true", help="List pending jobs without processing")

    db = sub.add_parser("dashboard", help="Consolidate all open '- [ ]' tasks in the vault into Action-Dashboard.md")
    db.add_argument("--output", default=DASHBOARD_FILE, help=f"Output filename in vault root (default: {DASHBOARD_FILE})")

    dz = sub.add_parser("diarize", help="Rotula falantes numa transcricao (baseado em texto, aproximado — idea-031)")
    dz.add_argument("--transcript", required=True, help="Arquivo .txt da transcricao a rotular")
    dz.add_argument("--people", default=None, help="Nomes conhecidos, separados por virgula (ex: 'Kelvin Okuda,Ana Leite')")
    dz.add_argument("--output", default=None, help="Saida (padrao: <nome>.diarized.txt ao lado do input)")

    mm = sub.add_parser("memory", help="Cross-session memory (idea-031): acoes abertas + topicos recorrentes por pessoa e topicos compartilhados entre pessoas")
    mm.add_argument("--person", default=None, help="Folder do liderado (ex: Ana-Leite). Omitir = todos + cross-person")
    mm.add_argument("--output", default=None, help="Saida (padrao: Team/<folder>/memory.md ou Cross-Session-Memory.md)")

    vl = sub.add_parser("velocity", help="Action velocity (idea-031): tempo de fechamento de action items + gargalos/stale")
    vl.add_argument("--person", default=None, help="Folder do liderado (ex: Ana-Leite). Omitir = todos + rollup")
    vl.add_argument("--output", default=None, help="Saida (padrao: Team/<folder>/velocity.md ou Action-Velocity.md)")

    al = sub.add_parser("alerts", help="PDI/OKR alerts (idea-031): prazos vencidos, OVERDUE explicitos e progresso zero")
    al.add_argument("--person", default=None, help="Folder do liderado (ex: Ana-Leite). Omitir = todos + rollup")
    al.add_argument("--output", default=None, help="Saida (padrao: Team/<folder>/alerts.md ou PDI-OKR-Alerts.md)")

    hl = sub.add_parser("health", help="Team health (idea-031): indice consolidado (recencia 1:1 + acoes abertas/stale + alertas)")
    hl.add_argument("--person", default=None, help="Folder do liderado (ex: Ana-Leite). Omitir = todos + rollup")
    hl.add_argument("--output", default=None, help="Saida (padrao: Team/<folder>/health.md ou Team-Health.md)")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    # sweep/queue/dashboard do their own thing; the rest need Ollama up.
    if args.command not in ("sweep", "queue", "dashboard", "memory", "velocity", "alerts", "health"):
        _check_ollama()

    if args.command == "agenda":
        cmd_agenda(args.person)
    elif args.command == "transcript":
        cmd_transcript(args.person, args.transcript, args.date,
                       structured=args.structured, lang=args.lang)
    elif args.command == "manager":
        cmd_manager(args.manager, args.transcript, args.date, lang=args.lang)
    elif args.command == "note":
        cmd_note(args.transcript, args.date, lang=args.lang, time_str=args.time)
    elif args.command == "capture":
        cmd_capture(args.mode, args.transcript, args.date, lang=args.lang, time_str=args.time)
    elif args.command == "sweep":
        cmd_sweep(args.dir, args.min_age_min, args.dry_run, args.lang, args.max_age_days)
    elif args.command == "queue":
        cmd_queue(args.dir, args.dry_run)
    elif args.command == "dashboard":
        cmd_dashboard(args.output)
    elif args.command == "diarize":
        cmd_diarize(args.transcript, args.people, args.output)
    elif args.command == "memory":
        cmd_memory(args.person, args.output)
    elif args.command == "velocity":
        cmd_velocity(args.person, args.output)
    elif args.command == "alerts":
        cmd_alerts(args.person, args.output)
    elif args.command == "health":
        cmd_health(args.person, args.output)


if __name__ == "__main__":
    main()
