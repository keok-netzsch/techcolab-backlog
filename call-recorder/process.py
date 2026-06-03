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
OLLAMA_MODEL = "llama3.2:3b"

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
    payload = {"model": model, "prompt": prompt, "stream": stream}

    if stream:
        full = []
        with requests.post(OLLAMA_URL, json=payload, stream=True, timeout=300) as r:
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
        r = requests.post(OLLAMA_URL, json=payload, timeout=300)
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
    oneonone   = read_file(str(team_path / "1on1.md"),      max_chars=2000)
    okr        = read_file(str(team_path / "OKR.md"),       max_chars=1000)
    pdi        = read_file(str(team_path / "PDI.md"),       max_chars=1000)
    transcript = read_file(transcript_file)

    if not transcript.strip():
        print(f"[ERROR] Transcricao vazia ou nao encontrada: {transcript_file}")
        sys.exit(1)

    transcript = transcript[:4000]  # cap at ~4k chars to stay within 3B model context

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
Contexto:
Overview: {overview}
Ultimo 1on1: {oneonone}
OKR: {okr}
PDI: {pdi}

Transcricao (apenas Kelvin falou):
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

    saved = _parse_and_save(response, team_path, SECTION_MAP, SECTION_MODE)

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
    oneonone   = read_file(str(stk_path / "1on1.md"),    max_chars=2000)
    transcript = read_file(transcript_file)

    if not transcript.strip():
        print(f"[ERROR] Transcricao vazia ou nao encontrada: {transcript_file}")
        sys.exit(1)

    transcript = transcript[:4000]  # cap at ~4k chars to stay within 3B model context

    prompt = f"""Voce e um assistente de gestao de pessoas. Analise a transcricao de uma reuniao com o gestor e estruture para o Obsidian.

Pessoa: {manager_name} (gestor/superior hierarquico) | Data: {date}

Contexto:
Historico de reunioes: {oneonone}
Visao geral: {overview}

Transcricao (apenas Kelvin falou):
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

    saved = _parse_and_save(response, stk_path, MANAGER_SECTION_MAP, MANAGER_SECTION_MODE)

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

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

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


if __name__ == "__main__":
    main()
