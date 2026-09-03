"""
coach.py — English coach: evaluates an English speech transcript with a local LLM.

Usage:
  python coach.py --transcript path/to/transcript.txt [--topic "optional topic"]

Requires: Ollama running locally (ollama serve) with qwen2.5-coder pulled.
Saves: per-session note + progress log in the Obsidian vault.
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import requests

# Vault root — override with env var TECHCOLAB_VAULT_ROOT; fallback below.
VAULT = os.environ.get(
    "TECHCOLAB_VAULT_ROOT",
    os.path.join(os.path.expanduser("~"), "OneDrive - NETZSCH", "Documents", "TechColab_D&A_KO"),
)
COACH_DIR = Path(VAULT) / "Areas" / "English-Learning"
SESSIONS_DIR = COACH_DIR / "sessions"
PROGRESS_FILE = COACH_DIR / "progress.md"


def _level_history(limit: int = 8) -> list:
    """CEFR levels of recent VALID sessions, oldest first.

    Until 26/08/2026 nothing read prior sessions at all, so the model re-guessed
    the level from scratch every run — which is why it went B1 -> C1 -> B1.
    Sessions marked assessment_valid: false are skipped so the audited garbage
    cannot anchor anything.
    """
    import re as _re
    levels = []
    for f in sorted(SESSIONS_DIR.glob("*_english-coach.md"))[-limit:]:
        try:
            head = f.read_text(encoding="utf-8", errors="replace")[:600]
        except OSError:
            continue
        if _re.search(r"^assessment_valid:\s*false", head, _re.M):
            continue
        m = _re.search(r"^level:\s*([ABC][12])", head, _re.M)
        if m:
            levels.append(m.group(1))
    return levels


def _last_level():
    hist = _level_history()
    return hist[-1] if hist else None

OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5-coder:latest"  # better structured/JSON output than llama3.2:3b

DIMENSIONS = ["grammar", "vocabulary", "fluency", "structure", "register"]
DIM_PT = {
    "grammar":    "Gramática",
    "vocabulary": "Vocabulário",
    "fluency":    "Fluência",
    "structure":  "Estrutura",
    "register":   "Registro",
}

TOPIC_TYPES = ["meeting", "presentation", "technical", "casual", "negotiation", "interview"]
TOPIC_TYPE_LABELS = {
    "meeting":      "Meeting",
    "presentation": "Presentation",
    "technical":    "Technical",
    "casual":       "Casual",
    "negotiation":  "Negotiation",
    "interview":    "Interview",
}

# Context-specific calibration injected into the evaluation prompt.
TOPIC_TYPE_GUIDANCE = {
    "meeting":      ("Multi-participant meeting. Fluency: short reactive turns are normal, not a deficiency. "
                     "Structure baseline = 5 (conversational). Vocabulary: domain terms show competence."),
    "presentation": ("Prepared presentation. Structure is critical: evaluate signposting, logical flow, opening/closing. "
                     "Fluency: complete sentences expected. Register: formal throughout."),
    "technical":    ("Technical discussion. Vocabulary: jargon (APIs, pipelines, metrics) = competence, not limited range; "
                     "evaluate the glue language between technical terms. Register: semi-formal OK."),
    "casual":       ("Casual conversation. Informal register, contractions, colloquialisms are appropriate — do not penalise. "
                     "Structure: minimal. Fluency: naturalness and idiomaticity are the focus."),
    "negotiation":  ("Negotiation. Register: formal and diplomatic — penalise casual slips. "
                     "Structure: reward hedging ('I understand your concern', 'what if we consider'), clear position-stating."),
    "interview":    ("Professional interview. Structure: STAR answers expected. Register: formal, no contractions. "
                     "Vocabulary: breadth and precision matter. Fluency: complete, coherent sentences expected."),
}


def _check_ollama():
    """Fail fast if Ollama is not reachable."""
    try:
        requests.get("http://localhost:11434/", timeout=3)
    except requests.exceptions.ConnectionError:
        print("[ERROR] Ollama not found at localhost:11434.")
        print("        Start with: ollama serve")
        sys.exit(1)


def _ensure_english(ev: dict) -> dict:
    """Post-process evaluation dict: translate any PT text fields to English via a fast Ollama call.

    Skipped entirely when the gateway produced the evaluation: a frontier model
    already honours the "answer in English" instruction, and this pass otherwise
    costs an extra Ollama round-trip (up to 120 s) on every single run for nothing.
    It stays for the local fallback path, where the 7B model does drift into PT.
    """
    try:
        import coach_llm
        if coach_llm.active_provider("coach") == "gateway" and not coach_llm.last_run_degraded():
            return ev
    except Exception:
        pass

    # Collect fields that may have been returned in Portuguese
    fields: dict[str, str] = {}
    if ev.get("summary"):
        fields["summary"] = ev["summary"]
    for i, e in enumerate(ev.get("errors", [])):
        if e.get("corrected"):
            fields[f"errors_{i}_corrected"] = e["corrected"]
        if e.get("explanation"):
            fields[f"errors_{i}_explanation"] = e["explanation"]
    for i, t in enumerate(ev.get("improvement_tips", [])):
        if t.get("tip"):
            fields[f"tips_{i}_tip"] = t["tip"]
        if t.get("example"):
            fields[f"tips_{i}_example"] = t["example"]
    for i, s in enumerate(ev.get("strengths", [])):
        fields[f"strength_{i}"] = s
    for i, v in enumerate(ev.get("vocabulary_suggestions", [])):
        for j, alt in enumerate(v.get("alternatives", [])):
            fields[f"vocab_{i}_alt_{j}"] = alt

    if not fields:
        return ev

    items_json = json.dumps(fields, ensure_ascii=False)
    prompt = (
        "Translate the following JSON values to English. "
        "Return ONLY a valid JSON object with the same keys and translated values. "
        "Do not add any explanation.\n\n" + items_json
    )
    try:
        r = requests.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False, "format": "json"},
            timeout=120,
        )
        r.raise_for_status()
        translated = json.loads(r.json()["response"].strip())
    except Exception:
        return ev  # silently fall back to original if translation fails

    # Write back translated values
    if "summary" in translated:
        ev["summary"] = translated["summary"]
    for i, e in enumerate(ev.get("errors", [])):
        k_c, k_e = f"errors_{i}_corrected", f"errors_{i}_explanation"
        if k_c in translated:
            e["corrected"] = translated[k_c]
        if k_e in translated:
            e["explanation"] = translated[k_e]
    for i, t in enumerate(ev.get("improvement_tips", [])):
        k_t, k_ex = f"tips_{i}_tip", f"tips_{i}_example"
        if k_t in translated:
            t["tip"] = translated[k_t]
        if k_ex in translated:
            t["example"] = translated[k_ex]
    for i in range(len(ev.get("strengths", []))):
        k = f"strength_{i}"
        if k in translated:
            ev["strengths"][i] = translated[k]
    for i, v in enumerate(ev.get("vocabulary_suggestions", [])):
        for j in range(len(v.get("alternatives", []))):
            k = f"vocab_{i}_alt_{j}"
            if k in translated:
                v["alternatives"][j] = translated[k]

    return ev


def _clean_transcript(transcript: str) -> str:
    """Remove Whisper hallucination loops at end of recording (e.g. repeated 'Let's go')."""
    lines = transcript.splitlines()
    if len(lines) < 10:
        return transcript
    # Find where trailing repeated short phrases start
    # A "spam block" = any phrase < 30 chars repeated 5+ times in the last 20% of lines
    tail_start = int(len(lines) * 0.8)
    tail = lines[tail_start:]
    from collections import Counter
    tail_texts = [ln.split("] ", 1)[-1].strip() for ln in tail if "] " in ln]
    if not tail_texts:
        return transcript
    counts = Counter(tail_texts)
    spam_phrases = {phrase for phrase, n in counts.items() if n >= 5 and len(phrase) < 30}
    if not spam_phrases:
        return transcript
    # Drop all lines (from any position) that match a spam phrase
    cleaned = [ln for ln in lines if ln.split("] ", 1)[-1].strip() not in spam_phrases]
    return "\n".join(cleaned)


def _transcript_stats(transcript: str) -> dict:
    """Extract duration and word count from a timestamped transcript."""
    import re as _re
    lines = [ln for ln in transcript.splitlines() if "] " in ln]
    word_count = sum(len(ln.split("] ", 1)[-1].split()) for ln in lines)
    duration_sec = 0
    if lines:
        last_ts = _re.search(r"\[(\d+\.?\d*)s\]", lines[-1])
        if last_ts:
            duration_sec = float(last_ts.group(1))
    return {"words": word_count, "duration_min": round(duration_sec / 60, 1), "lines": len(lines)}


def _ram_livre_mb() -> int:
    """RAM fisica livre, em MB. -1 quando nao da para medir."""
    try:
        import ctypes

        class _Mem(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong),
                        ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

        m = _Mem()
        m.dwLength = ctypes.sizeof(_Mem)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
            return -1
        return int(m.ullAvailPhys / (1024 * 1024))
    except Exception:  # noqa: BLE001
        return -1


def _ollama_pode_servir(timeout: int = 25) -> tuple[bool, str]:
    """Manda tres palavras ao Ollama e ve se volta. Nada mais indireto que isso.

    Tentei antes duas sondas baratas e as duas mentiram nesta maquina, em
    2026-09-02:

      - `/api/ps` listava `qwen2.5-coder` como carregado enquanto um prompt de
        tres palavras estourava 120 s. Modelo "carregado" com 629 MB de RAM livre
        esta paginado em disco, e o Ollama nao distingue os dois casos.
      - RAM livre contra o peso do modelo inverte o sinal quando o modelo esta
        mesmo residente: os 4,7 GB dele SAO a memoria ocupada, entao a maquina
        saudavel parece a maquina cheia.

    O custo do teste real e 25 s no pior caso. O que ele evita: 300 s por chamada
    (o timeout do resumo), duas vezes por call. Em 02/09 isso deixou o
    reprocessamento da call do Stefan 12 minutos parado, com 0,09 s de CPU, para
    no fim devolver string vazia — o resumo de contexto e opcional por design.

    Vies: so recusa com PROVA. Erro de rede ou sonda que nao decide deixa passar,
    senao um probe furado apagaria o contexto de todo relatorio em silencio.
    """
    try:
        import requests
        r = requests.post(
            "http://127.0.0.1:11434/api/generate",
            json={"model": os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:latest"),
                  "prompt": "Responda apenas: ok", "stream": False},
            timeout=timeout)
        r.raise_for_status()
        return True, ""
    except Exception as e:  # noqa: BLE001
        nome = type(e).__name__
        if "Timeout" in nome:
            return False, (f"nao respondeu a um prompt de 3 palavras em {timeout} s "
                           f"({_ram_livre_mb()} MB de RAM livre)")
        return True, ""


def _context_summary(full_transcript: str, max_chars: int = 12_000) -> str:
    """Duas frases dizendo do que era a call — geradas LOCALMENTE, no Ollama.

    Pedido do Kelvin (P-012): "gostaria de um resumo do contexto da call, no
    começo, para entender melhor o teor da conversa e colocações". A avaliação só
    vê a fala dele, então hoje o relatório julga frases sem dizer a que se
    respondia.

    Ele autorizou ampliar "a menos que haja algum risco ou problema" — e há. O
    resumo precisa do transcript COMPLETO, com a fala do interlocutor, e mandar
    isso ao gateway sairia da fronteira atual: hoje só a fala dele deixa a
    máquina. `maybe_run_coach` dispara por IDIOMA, nunca por tipo de call, e há
    1:1 com o time na fila — um 1:1 em inglês mandaria fala de PDI/carreira de
    outra pessoa para fora. Por isso `purpose="transcript"`: a allowlist do
    coach_llm força Ollama e uma edição futura que tente mandar isso para o
    gateway levanta ProviderError em vez de vazar em silêncio.

    Falha vira string vazia: o relatório sai sem contexto, nunca sem relatório.
    """
    if not full_transcript.strip():
        return ""

    pode, motivo = _ollama_pode_servir()
    if not pode:
        print(f"[coach] contexto pulado - Ollama sem memoria ({motivo}).")
        return ("(nao gerado - o modelo local nao coube na memoria da maquina no "
                f"momento do processamento: {motivo})")

    try:
        import coach_llm
        prompt = (
            "Abaixo esta a transcricao de uma reuniao de trabalho, com os dois "
            "lados da conversa. Em NO MAXIMO 2 frases, em portugues, diga do que "
            "tratava a conversa e qual era o papel do Kelvin nela (apresentou algo? "
            "pediu algo? decidiu? ouviu?). Nao avalie o ingles de ninguem, nao cite "
            "nomes de terceiros, nao liste topicos - so o contexto.\n\n"
            f"{full_transcript[:max_chars]}"
        )
        # 120 s, nao 300 (2026-09-02). Quando o Ollama esta saudavel nesta
        # maquina ele devolve 3 palavras em ~5 s; quando esta paginando, nao
        # devolve o resumo em 300 s tampouco — medido tres vezes seguidas na
        # mesma noite, sempre estourando o timeout cheio. Os 180 s a mais eram
        # espera pura, duas vezes por call, e o relatorio sai sem contexto de
        # qualquer jeito.
        txt = coach_llm.generate(prompt, purpose="transcript", expect_json=False,
                                 max_tokens=300, timeout=120)
        return " ".join((txt or "").split())[:600]
    except Exception as e:  # noqa: BLE001
        print(f"[coach] contexto nao gerado ({e}) - o relatorio segue sem ele.")
        return ""


def _budget_chars() -> int:
    """Quantos caracteres da fala do Kelvin vão para a avaliação.

    Decisão dele em 2026-08-31, ao ver que só ~20% de uma call longa era avaliada:
    **"sim. cubra 100%"**. O corte de 5.000 foi dimensionado quando o avaliador era
    o qwen2.5-coder local de 7B; com o `claude-sonnet-5` pelo gateway o orçamento é
    outra ordem de grandeza. Medida real: 24.339 caracteres no Jour Fixe com o
    Alberto — ~6k tokens, trivial para o Sonnet, inviável para o 7B.

    Por isso o orçamento segue o provedor, e não uma constante: cair para o Ollama
    (sem saldo, chave expirada, rede) com 120k caracteres transformaria degradação
    em travamento. O teto remoto existe só como para-quedas — e quando corta, diz.
    """
    try:
        import coach_llm
        return 120_000 if coach_llm.active_provider("coach") == "gateway" else 5_000
    except Exception:
        return 5_000


def _sample_excerpt(transcript: str, target_chars: int | None = None) -> str:
    """Return a representative sample: first half + middle half.

    Taking only the first N chars biases against speakers who warm up slowly
    and undersamples vocabulary used later in the conversation.
    For short transcripts the full text is returned unchanged.

    Com o gateway, o orçamento (`_budget_chars`) cobre a call inteira e este
    caminho de amostragem praticamente não roda — ele fica para o fallback local.
    """
    if target_chars is None:
        target_chars = _budget_chars()
    if len(transcript) <= target_chars:
        return transcript
    # Cortar tem que ser visível: 20 sessões foram avaliadas parcialmente sem que
    # nada além de um marcador no meio do texto dissesse isso.
    print(f"[coach] AVISO: transcricao com {len(transcript)} chars excede o "
          f"orcamento de {target_chars} — avaliando uma AMOSTRA (inicio + meio), "
          f"nao a call inteira.")
    half = target_chars // 2
    # Beginning slice
    beginning = transcript[:half]
    # Middle slice — start near the centre of the transcript
    mid_start = max(half + 1, len(transcript) // 2 - half // 2)
    middle_raw = transcript[mid_start: mid_start + half]
    # Drop partial first line of the middle slice to avoid cut-off timestamps
    mid_lines = middle_raw.splitlines()
    if len(mid_lines) > 1:
        mid_lines = mid_lines[1:]
    middle = "\n".join(mid_lines)
    return beginning + "\n\n[... middle of transcript ...]\n\n" + middle


def _evaluate(transcript: str, topic: str, topic_type: str = "") -> dict:
    """Send transcript to Ollama and return structured evaluation dict."""
    # ── Session header ────────────────────────────────────────────────────────
    if topic_type:
        type_label  = TOPIC_TYPE_LABELS.get(topic_type, topic_type.title())
        session_header = f"Session type: **{type_label}**" + (f" — {topic}" if topic else "")
    else:
        session_header = f"Topic / context: {topic}" if topic else "Session type: professional business meeting"

    # ── Sampling ──────────────────────────────────────────────────────────────
    excerpt         = _sample_excerpt(transcript)
    stats_full      = _transcript_stats(transcript)
    stats_excerpt   = _transcript_stats(excerpt)
    coverage_pct    = round(stats_excerpt["words"] / max(stats_full["words"], 1) * 100)
    evaluated_words = stats_excerpt["words"]

    # ── Confidence tier (for vocabulary/level reliability) ────────────────────
    if evaluated_words < 150:
        confidence_note = (
            "SAMPLE SIZE WARNING: fewer than 150 speaker words are visible. "
            "Vocabulary and CEFR level estimates have VERY LOW reliability. "
            "Set level_confidence to 'low'. Avoid penalising vocabulary range."
        )
    elif evaluated_words < 400:
        confidence_note = (
            "SAMPLE SIZE: 150–400 words visible. "
            "Vocabulary and CEFR level estimates have MEDIUM reliability. "
            "Set level_confidence to 'medium'. Be conservative on vocabulary scores."
        )
    else:
        confidence_note = (
            "SAMPLE SIZE: 400+ words visible. "
            "Vocabulary and CEFR level estimates have HIGH reliability. "
            "Set level_confidence to 'high'."
        )

    # ── Context-specific guidance ─────────────────────────────────────────────
    # Both this and `rubric` below were built and never injected into the prompt
    # until 2026-09-02: only `context_block` reached the f-string. The scoring
    # rules therefore never got to the model, which graded on the CRITICAL RULES
    # alone. Wired in below.
    type_guidance = TOPIC_TYPE_GUIDANCE.get(topic_type, "")
    type_block = (
        f"RECORDING TYPE ({topic_type}): {type_guidance}\n" if type_guidance else ""
    )

    context_block = (
        f"RECORDING CONTEXT:\n"
        f"- Total duration: {stats_full['duration_min']} min\n"
        f"- Total words in transcript: ~{stats_full['words']} "
        f"(multi-participant recording — NOT all words belong to the target speaker)\n"
        f"- Words in evaluated sample: ~{evaluated_words} ({coverage_pct}% of recording)\n"
        f"- Sample strategy: beginning + middle of transcript to maximise vocabulary coverage\n"
        f"- {confidence_note}"
    )

    # ── Per-dimension rubric (compact — keep prompt size manageable for CPU LLMs) ─
    rubric = (
        "SCORING RULES (apply strictly before grading):\n"
        "Grammar: evaluate patterns only — isolated slips and sentence fragments in reactive speech are NOT errors.\n"
        "Vocabulary: domain/technical terms (APIs, KPIs, data pipelines) signal expertise, NOT limited range. "
        "Evaluate variety and precision of the NON-technical vocabulary (connectors, hedging, explanations). "
        "Low word count due to short turns ≠ poor range.\n"
        "Fluency: you read TEXT, not audio — assess textual proxies only: sentence variety (simple vs. compound/complex), "
        "connector richness (beyond 'and/but/so'), idiomaticity. Do NOT penalise short reactive turns in meetings.\n"
        "Structure: in meetings the baseline is 5/10 — conversational by design. Score UP for signposting; "
        "score DOWN only for incoherent ideas. For presentations/interviews: evaluate seriously.\n"
        "Register: most reliable score — be confident even on short samples."
    )

    # Deterministic hits go INTO the prompt: the model should spend its effort on
    # nuance, not on re-finding "informations", which a regex already caught with
    # certainty. It is also told not to repeat them, so the report has no duplicates.
    import coach_patterns as patterns
    det = patterns.detect(transcript)
    known = chr(10).join(f'- "{h["quote"]}" -> {h["fix"]} ({h["label"]})'
                         for h in det["certain"][:15])
    known_block = (
        "ALREADY DETECTED deterministically (do NOT repeat these, they are "
        "already reported to the user):" + chr(10) + known + chr(10)
    ) if known else ""

    prompt = f"""You are an English coach for a Brazilian professional whose English is
already strong: solid C1 business English, Team Lead at a German multinational,
speaking in project meetings with German and international colleagues.

He does NOT make beginner mistakes and does not need basic grammar correction.
Telling him his English is "good" is useless. What actually limits him is a small
set of persistent Portuguese-shaped habits, imprecise word choice, and pragmatic
calibration with senior stakeholders.

CRITICAL RULES
1. Every quoted span MUST appear VERBATIM in the transcript. Never paraphrase a
   quote. If you cannot quote it exactly, do not report it.
2. Separate two different things, and never mix them:
   - "errors": objectively WRONG in professional English. If a competent native
     speaker could say it, it is NOT an error.
   - "refinements": correct, but a sharper or better-calibrated choice exists.
     Register, precision, collocation. These are choices, not mistakes.
   When in doubt, it is a refinement, not an error.
3. Do not invent grammar rules. Do not "fix" correct English.
4. Never report backchannel ("yeah", "mm-hmm", "right", "got it", "I see").
5. This transcript comes from automatic speech recognition, which silently repairs
   disfluency and normalises grammar. Therefore: do NOT assess pronunciation, and
   treat basic grammar as LOW signal. Weight vocabulary, collocation, register and
   discourse structure instead.

{rubric}

{type_block}
{session_header}

{context_block}

{known_block}
Transcript:
---
{excerpt}
---

Return this exact JSON:
{{
  "scores": {{"grammar": <0-10>, "vocabulary": <0-10>, "fluency": <0-10>,
              "structure": <0-10>, "register": <0-10>}},
  "overall": <0-10>,
  "level": "<A1|A2|B1|B2|C1|C2>",
  "level_confidence": "<low|medium|high>",
  "summary": "<2-3 sentences. No generic praise. Name the single highest-leverage change.>",
  "errors": [{{"type": "<category>", "original": "<verbatim quote>",
               "corrected": "<fix>", "explanation": "<why it is wrong>"}}],
  "refinements": [{{"original": "<verbatim quote>", "better": "<sharper version>",
                    "why": "<what it buys him>"}}],
  "strengths": ["<verbatim quote that genuinely works well>"],
  "improvement_tips": [{{"dimension": "<category>", "tip": "<concrete>",
                         "example": "<example>"}}],
  "vocabulary_suggestions": [{{"used": "<what he said>",
                               "alternatives": ["<sharper>", "<sharper>"]}}]
}}

Limits: errors max 6, refinements max 6, strengths max 3, improvement_tips max 3,
vocabulary_suggestions max 4. Order each by impact."""

    import coach_llm
    ev = coach_llm.generate_json(prompt, purpose="coach", max_tokens=8000)
    ev.setdefault("refinements", [])
    return _ensure_english(ev)


def _score_bar(score) -> str:
    """Accept int or float — always returns 10-char bar."""
    filled = int(round(float(score) / 10 * 10))
    filled = max(0, min(10, filled))   # clamp to [0,10]
    return "█" * filled + "░" * (10 - filled)


def _render_session(ev: dict, transcript: str, topic: str, session_dt: datetime, topic_type: str = "", contexto: str = "") -> str:
    stats = _transcript_stats(transcript)
    excerpt = _sample_excerpt(transcript)
    excerpt_stats = _transcript_stats(excerpt)
    coverage_pct = round(excerpt_stats["words"] / max(stats["words"], 1) * 100)

    lines = [
        "---",
        f"date: {session_dt.strftime('%Y-%m-%d')}",
        f"time: {session_dt.strftime('%H:%M')}",
        "type: english-coach-session",
        "lang: en",
        f"overall: {ev['overall']}",
        f"level: {ev['level']}",
        f"duration_min: {stats['duration_min']}",
        f"words_total: {stats['words']}",
        f"words_evaluated: {excerpt_stats['words']}",
        f"topic_type: {topic_type}" if topic_type else "topic_type: ''",
        "tags: [english-coach]",
        "---",
        "",
        f"# English Coach Session — {session_dt.strftime('%Y-%m-%d')}",
        "",
    ]
    # Aviso de contaminacao de canal (2026-09-02). O coach filtra "so as linhas do
    # Kelvin" — e isso so vale se o canal 0 tiver a voz dele sozinha. Com caixa de
    # som em vez de fone, o mic dele capta o outro lado e a avaliacao mistura os
    # dois. Medido na call do Stefan de 02/09: soma de 123%, e o relatorio B2 saiu
    # avaliando, em parte, o ingles do Stefan.
    #
    # O aviso vai DENTRO do relatorio, nao so no console: quem abre o arquivo
    # semanas depois nao viu o console, e um numero sem ressalva le como limpo.
    try:
        import transcript_quality as _tq
        _stem = Path(getattr(_render_session, "_fonte", "") or "").stem
        _nivel, _soma, _detalhe = _tq.contaminacao_de_canal(_stem) if _stem else ("", 0, "")
        if _nivel:
            lines += [
                f"> **Atencao — canal contaminado ({_detalhe}).** O microfone captou "
                f"tambem o outro lado, entao parte do que foi avaliado como fala do "
                f"Kelvin nao e dele. Trate a nota como indicativa, nao como medida.",
                "",
            ]
    except Exception:
        pass

    # Contexto ANTES da avaliacao: sem ele o relatorio julga frases sem dizer a
    # que se respondia (pedido do Kelvin, P-012). Gerado localmente no Ollama.
    if contexto:
        lines += [f"**Contexto da call:** {contexto}", ""]
    lines += [
        f"> {ev['summary']}",
        "",
        f"**Recording:** {stats['duration_min']} min · {stats['words']} words total · "
        f"{excerpt_stats['words']} words evaluated ({coverage_pct}% of transcript)",
        "",
        "## Scores",
        "",
        "| Dimension | Score | Bar |",
        "|-----------|-------|-----|",
    ]
    for dim in DIMENSIONS:
        s = ev["scores"].get(dim, 0)
        lines.append(f"| {DIM_PT[dim]} | {s}/10 | `{_score_bar(s)}` |")
    lines.append(f"| **Overall** | **{ev['overall']}/10** | `{_score_bar(int(round(ev['overall'])))}` |")
    lines.append("")
    _conf = ev.get("level_confidence", "")
    _conf_badge = {"low": " ⚠️ low confidence", "medium": " · medium confidence", "high": ""}.get(_conf, "")
    lines.append(f"**CEFR Level:** {ev['level']}{_conf_badge}")
    lines.append("")

    if ev.get("strengths"):
        lines += ["## Strengths", ""]
        for s in ev["strengths"]:
            lines.append(f"- {s}")
        lines.append("")

    if ev.get("errors"):
        lines += ["## Errors to Fix", ""]
        for e in ev["errors"]:
            original = e.get("original", "")
            corrected = e.get("corrected", "")
            explanation = e.get("explanation", "")
            label = f"**{e.get('type', 'Error').title()}**"
            lines.append(f"{label} — _{original}_" if original else label)
            if corrected:
                lines.append(f"→ **{corrected}**")
            if explanation:
                lines.append(f"  {explanation}")
            lines.append("")

    # Refinements are NOT errors and must never be rendered as if they were. For a
    # C1 speaker, mixing "this is wrong" with "this is a sharper choice" is what
    # turns the report into noise he stops reading.
    if ev.get("refinements"):
        lines += ["## Refinements — correct, but sharper options exist", ""]
        for r in ev["refinements"]:
            if r.get("original"):
                lines.append(f"_{r['original']}_")
            if r.get("better"):
                lines.append(f"→ **{r['better']}**")
            if r.get("why"):
                lines.append(f"  {r['why']}")
            lines.append("")

    if ev.get("improvement_tips"):
        lines += ["## Improvement Tips", ""]
        for t in ev["improvement_tips"]:
            lines.append(f"**{DIM_PT.get(t['dimension'], t['dimension'])}:** {t['tip']}")
            if t.get("example"):
                lines.append(f"> Example: _{t['example']}_")
            lines.append("")

    if ev.get("vocabulary_suggestions"):
        lines += ["## Vocabulary Upgrades", ""]
        for v in ev["vocabulary_suggestions"]:
            alts = " / ".join(f"_{a}_" for a in v["alternatives"])
            lines.append(f"- _{v['used']}_ → {alts}")
        lines.append("")

    if topic or topic_type:
        topic_display = topic or ""
        if topic_type:
            type_label = TOPIC_TYPE_LABELS.get(topic_type, topic_type.title())
            topic_display = f"**[{type_label}]** {topic_display}".strip()
        lines += ["## Topic", "", topic_display, ""]

    # Evaluated excerpt — sampled beginning + middle
    lines += [
        "## Evaluated excerpt",
        "",
        f"> {excerpt_stats['words']} words sampled ({coverage_pct}% of transcript) — beginning + middle.",
        "",
        "```",
        excerpt.strip(),
        "```",
        "",
    ]

    lines += ["## Full transcript", "", "```", transcript.strip(), "```", ""]

    return "\n".join(lines)


def _update_index(ev: dict, session_dt: datetime, topic: str, topic_type: str = ""):
    """Update Areas/English-Learning/_index.md Current Status section after each session."""
    import re as _re
    index_file = COACH_DIR / "_index.md"
    if not index_file.exists():
        return

    scores = ev.get("scores", {})
    if scores:
        best_dim  = max(scores, key=lambda d: scores.get(d, 0))
        worst_dim = min(scores, key=lambda d: scores.get(d, 0))
        best_label  = DIM_PT.get(best_dim, best_dim.title())
        worst_label = DIM_PT.get(worst_dim, worst_dim.title())
        best_score  = scores[best_dim]
        worst_score = scores[worst_dim]
    else:
        best_label = worst_label = "—"
        best_score = worst_score = 0

    date_str   = session_dt.strftime("%Y-%m-%d")
    level      = ev.get("level", "—")
    overall    = ev.get("overall", 0)

    topic_display = topic or "—"
    if topic_type:
        type_label    = TOPIC_TYPE_LABELS.get(topic_type, topic_type)
        topic_display = f"[{type_label}] {topic_display}" if topic else f"[{type_label}]"

    new_status = (
        f"## Current Status\n\n"
        f"- **Level:** {level} (as of {date_str})\n"
        f"- **Last session:** {date_str} — topic: {topic_display} — overall score: {overall}/10\n"
        f"- **Strongest dimension:** {best_label} ({best_score}/10)\n"
        f"- **Focus area:** {worst_label} ({worst_score}/10)\n"
    )

    content = index_file.read_text(encoding="utf-8")
    # Replace the Current Status block up to the next heading
    content = _re.sub(
        r"## Current Status\n[\s\S]*?(?=\n## |\Z)",
        new_status + "\n",
        content,
    )
    # Update inline level reference in the frontmatter quote
    content = _re.sub(
        r"Current level: [A-Z]\d[^\n]*",
        f"Current level: {level} (as of {date_str})",
        content,
    )
    index_file.write_text(content, encoding="utf-8")


def _append_progress(ev: dict, session_dt: datetime, topic: str, topic_type: str = ""):
    COACH_DIR.mkdir(parents=True, exist_ok=True)

    scores_inline = " | ".join(
        f"{DIM_PT[d]}: {ev['scores'].get(d, 0)}" for d in DIMENSIONS
    )
    topic_cell = topic or "—"
    if topic_type:
        type_label = TOPIC_TYPE_LABELS.get(topic_type, topic_type)
        topic_cell = f"[{type_label}] {topic_cell}" if topic else f"[{type_label}]"
    row = (
        f"| {session_dt.strftime('%Y-%m-%d')} | {ev['overall']}/10 | {ev['level']} "
        f"| {scores_inline} | {topic_cell} |\n"
    )

    if not PROGRESS_FILE.exists():
        header = (
            "# English Coach — Progress Log\n\n"
            "| Date | Overall | Level | Scores | Topic |\n"
            "|------|---------|-------|--------|-------|\n"
        )
        PROGRESS_FILE.write_text(header + row, encoding="utf-8")
        return

    # UMA linha por dia (2026-09-02). Antes era uma por call, e um dia com 4
    # calls em ingles enchia o log com 4 linhas da mesma data — o grafico de
    # evolucao passava a medir frequencia de reuniao, nao progresso.
    dia = session_dt.strftime("%Y-%m-%d")
    linhas = PROGRESS_FILE.read_text(encoding="utf-8").splitlines(keepends=True)
    for i, ln in enumerate(linhas):
        if ln.startswith(f"| {dia} |"):
            linhas[i] = row
            break
    else:
        linhas.append(row)
    PROGRESS_FILE.write_text("".join(linhas), encoding="utf-8")


# ── Um relatorio por DIA (2026-09-02) ────────────────────────────
# Ate hoje cada call virava um arquivo (`{data}_{hora}_english-coach.md`) e uma
# linha no progress. So em 02/09 foram 4 arquivos — o coach dispara por IDIOMA,
# entao toda call em ingles gera um. O Kelvin: "prefiro que o english coach gere
# um relatorio por dia ou semana, com tudo junto, ja que e assim".
#
# Agora e `{data}_english-coach.md`, com uma secao por call dentro. O progress
# ganha UMA linha por dia, substituida quando o dia recebe outra call.
SESSION_SUFFIX = "_english-coach.md"


def _hora_da_call(caminho: str):
    """Extrai a data e a hora da CALL do nome do arquivo de transcricao.

    O relatorio passou a ser por dia em 2026-09-02, e no primeiro reprocessamento
    a secao saiu como `## Call 1 - 21:53`: a hora em que o coach rodou, nao a hora
    em que a conversa aconteceu. Duas consequencias, nao uma:

      - a ordem das calls do dia vira a ordem da FILA. A call das 08:39 apareceu
        como Call 1 e a das 08:03 iria como Call 2.
      - a fila noturna roda as 20:00 e pode virar a meia-noite. Uma call de terca
        processada 00:10 de quarta abriria o relatorio de quarta.

    Nome esperado: `YYYY-MM-DD_HH-MM_...`. Fora desse formato devolve None e quem
    chama cai no relogio, que e o comportamento antigo.
    """
    import re
    m = re.search(r"(\d{4}-\d{2}-\d{2})_(\d{2})-(\d{2})", Path(caminho or "").name)
    if not m:
        return None
    try:
        from datetime import date as _d
        d = _d.fromisoformat(m.group(1))
        return datetime(d.year, d.month, d.day, int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _daily_session_file(session_dt) -> Path:
    return SESSIONS_DIR / f"{session_dt.strftime('%Y-%m-%d')}{SESSION_SUFFIX}"


def _consolidar_no_dia(caminho: Path, session_md: str, session_dt, ordem: int) -> str:
    """Devolve o conteudo do arquivo do dia com esta call acrescentada.

    A primeira call do dia escreve o arquivo inteiro. As seguintes viram uma
    secao `## Call N` e o frontmatter do dia passa a contar quantas foram — quem
    abre o arquivo precisa ver de cara que o dia teve mais de uma conversa, senao
    o cabecalho da primeira parece o dia todo.
    """
    hora = session_dt.strftime("%H:%M")
    if not caminho.exists():
        corpo = session_md.replace(
            f"# English Coach Session — {session_dt.strftime('%Y-%m-%d')}",
            f"# English Coach — {session_dt.strftime('%Y-%m-%d')}"
            + chr(10) + chr(10) + f"## Call 1 — {hora}", 1)
        return corpo.replace("calls: 1" + chr(10), "", 1)

    atual = caminho.read_text(encoding="utf-8", errors="replace")

    # O frontmatter que vale e o do dia: mantem o primeiro e atualiza a contagem.
    # `level` e `overall` do dia acompanham a avaliacao MAIS RECENTE, nao a
    # primeira. `_level_history` le so os primeiros 600 chars do arquivo, entao
    # sem isso o dia inteiro ficaria ancorado no nivel da primeira call e o clamp
    # de CEFR passaria a comparar contra um numero velho.
    novos = {}
    for ln in session_md.splitlines():
        for campo in ("level:", "overall:", "assessment_valid:"):
            if ln.startswith(campo):
                novos[campo] = ln
    linhas = atual.splitlines()
    tem_calls = False
    for i, ln in enumerate(linhas):
        if ln.startswith("calls: "):
            linhas[i] = f"calls: {ordem}"
            tem_calls = True
        for campo, valor in novos.items():
            if ln.startswith(campo):
                linhas[i] = valor
    if not tem_calls:
        for i, ln in enumerate(linhas):
            if ln.startswith("type: english-coach"):
                linhas.insert(i + 1, f"calls: {ordem}")
                break
    atual = chr(10).join(linhas)

    # Do bloco novo aproveita so o corpo, sem o frontmatter e sem o H1 do dia.
    novo = session_md
    if novo.startswith("---"):
        novo = novo.split("---", 2)[-1]
    novo = chr(10).join(ln for ln in novo.splitlines()
                        if not ln.startswith("# English Coach"))

    return _montar_dia(atual, f"## Call X — {hora}" + chr(10) + novo.strip(), hora)


def _montar_dia(atual: str, secao_nova: str, hora_nova: str) -> str:
    """Reordena as calls do dia por horario e renumera de 1 a N.

    A numeracao antiga vinha de `_calls_no_dia`, que CONTA secoes. Contagem e
    ordem de chegada, e a ordem de chegada e a da fila: em 2026-09-02 a call das
    08:39 foi processada primeiro e virou Call 1, com a das 08:03 entrando como
    Call 2 depois. Quem le o relatorio do dia le a conversa da tarde antes da
    manha.

    Corrigir o horario do cabecalho (feito antes) nao resolvia isto sozinho: o
    rotulo passou a estar certo e a posicao continuava errada.
    """
    marcador = chr(10) + "## Call "
    i = atual.find(marcador)
    if i < 0:
        return atual.rstrip() + chr(10) * 2 + "---" + chr(10) * 2 +             secao_nova.replace("## Call X", "## Call 2") + chr(10)

    cabecalho = atual[:i]
    corpo = atual[i + 1:]

    secoes = []
    for pedaco in corpo.split(chr(10) * 2 + "---" + chr(10) * 2):
        pedaco = pedaco.strip()
        if not pedaco:
            continue
        primeira = pedaco.splitlines()[0]
        hora = primeira.split("—")[-1].strip() if "—" in primeira else "99:99"
        secoes.append((hora, pedaco))
    secoes.append((hora_nova, secao_nova.strip()))
    secoes.sort(key=lambda p: p[0])

    saida = []
    for n, (hora, texto) in enumerate(secoes, 1):
        linhas = texto.splitlines()
        linhas[0] = f"## Call {n} — {hora}"
        saida.append(chr(10).join(linhas))

    return (cabecalho.rstrip() + chr(10) * 2
            + (chr(10) * 2 + "---" + chr(10) * 2).join(saida) + chr(10))


def _calls_no_dia(session_dt) -> int:
    """Quantas calls o dia ja teve, contando esta."""
    caminho = _daily_session_file(session_dt)
    if not caminho.exists():
        return 1
    texto = caminho.read_text(encoding="utf-8", errors="replace")
    return texto.count(chr(10) + "## Call ") + 1


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="English coach — evaluate transcript")
    parser.add_argument("--transcript", required=True, help="Path to .txt transcript")
    parser.add_argument("--topic", default="", help="Optional topic/context hint (free text)")
    parser.add_argument(
        "--topic-type",
        default="",
        choices=TOPIC_TYPES + [""],
        dest="topic_type",
        help=f"Structured session type: {', '.join(TOPIC_TYPES)}",
    )
    parser.add_argument(
        "--date",
        default="",
        help="Override session date (YYYY-MM-DD). Useful when processing a recording made on a previous day.",
    )
    parser.add_argument(
        "--model",
        default="",
        help="Override Ollama model (default: qwen2.5-coder:latest). Useful for benchmarking alternatives.",
    )
    args = parser.parse_args()

    if args.model:
        global OLLAMA_MODEL
        OLLAMA_MODEL = args.model

    _check_ollama()

    transcript_path = Path(args.transcript)
    if not transcript_path.exists():
        print(f"[ERROR] Transcript not found: {transcript_path}")
        sys.exit(1)

    transcript = transcript_path.read_text(encoding="utf-8").strip()
    if not transcript:
        print("[ERROR] Transcript is empty.")
        sys.exit(1)

    # ── Input integrity (coach_guards) ───────────────────────────────────────
    # Order matters: isolate the speaker, strip transcription artifacts, and only
    # then decide whether this is even scoreable. The 26/08 audit found 8 of 15
    # sessions were Portuguese scored as English, one scored B1 on a transcript
    # that is 3 words long once artifacts are removed.
    import coach_guards as guards
    import coach_llm

    contexto = ""
    if "Kelvin:" in transcript:          # dual-channel capture: keep only our side
        # O resumo de contexto sai daqui, do transcript COMPLETO, e e gerado
        # LOCALMENTE — ver _context_summary. Depois desta linha o outro lado nao
        # existe mais para o resto do coach.
        contexto = _context_summary(transcript)
        own = [ln for ln in transcript.splitlines() if "Kelvin:" in ln]
        print(f"[coach] Dual-channel transcript: evaluating {len(own)} of "
              f"{len(transcript.splitlines())} lines (Kelvin only).")
        transcript = "\n".join(own)

    original_lines = len(transcript.splitlines())
    transcript, dropped = guards.clean_transcript(transcript)
    if dropped:
        print(f"[coach] Removed {len(dropped)} transcription artifacts "
              f"(of {original_lines} lines).")

    sidecar = Path(str(transcript_path) + ".lang")
    whisper_lang = sidecar.read_text(encoding="utf-8").strip() if sidecar.exists() else None

    scoreable, gate_reason = guards.language_gate(transcript, whisper_lang)
    print(f"[coach] Portao de idioma: {gate_reason}")
    if not scoreable:
        # Refusing must never look like a bad score — that is exactly how
        # Portuguese calls ended up recorded as B1/B2 in progress.md.
        print("[coach] Sessao NAO avaliada. Nenhuma nota ou nivel sera gravado.")
        sys.exit(0)

    now = _hora_da_call(getattr(args, "transcript", "")) or datetime.now()
    if args.date:
        try:
            from datetime import date as _date_cls
            override_date = _date_cls.fromisoformat(args.date)
            now = datetime.combine(override_date, now.time())
            print(f"[coach] Date override: {args.date}")
        except ValueError:
            print(f"[ERROR] Invalid --date format '{args.date}'. Expected YYYY-MM-DD.")
            sys.exit(1)

    session_dt = now.strftime("%Y-%m-%d_%H-%M")
    session_display = now.strftime("%Y-%m-%d %H:%M")

    stats = _transcript_stats(transcript)
    sample = _sample_excerpt(transcript)
    sample_stats = _transcript_stats(sample)
    print(f"\n[coach] Recording: {stats['duration_min']} min · {stats['words']} words total · "
          f"{sample_stats['words']} words sampled for evaluation")
    if args.topic_type:
        print(f"[coach] Session type: {TOPIC_TYPE_LABELS.get(args.topic_type, args.topic_type)}")
    try:
        ev = _evaluate(transcript, args.topic, args.topic_type)
    except json.JSONDecodeError as e:
        print(f"[ERROR] Ollama returned invalid JSON: {e}")
        sys.exit(1)

    # ── Output guards (coach_guards) ─────────────────────────────────────────
    # The model invents. Audited examples: a grammar rule that does not exist
    # ("'I don't know the details' is incorrect"), a strength quoted verbatim out
    # of this file's own rubric, and the same transcript graded B2 four times and
    # C1 once. Everything it claims is checked against the transcript before it
    # reaches the vault.
    ev["errors"], rejected_e = guards.filter_findings(
        ev.get("errors", []), transcript, quote_key="original")
    ev["strengths"], rejected_s = guards.filter_findings(
        [{"original": s} for s in ev.get("strengths", [])], transcript,
        quote_key="original")
    ev["strengths"] = [s["original"] for s in ev["strengths"]]
    for r in rejected_e + rejected_s:
        print(f"[coach] descartado - {r}")

    if guards.summary_contradicts_score(ev.get("summary", ""), float(ev.get("overall", 0))):
        print("[coach] AVISO: resumo contradiz a nota — marcando confianca baixa.")
        ev["level_confidence"] = "low"

    # A degraded run means the 7B local model answered. In the benchmark it
    # returned level=None on a transcript the gateway rated C1 — writing that into
    # progress.md would poison the very history the anchoring now depends on.
    if coach_llm.last_run_degraded():
        # NENHUMA nota vinda do modelo local e gravada (2026-09-02). O guarda
        # antigo so recusava quando o `level` vinha invalido, e passar nesse
        # teste nao significa nada: em 02/09 o gateway devolveu 504 tres vezes
        # na call das 08:03, o `qwen2.5-coder` respondeu no lugar dele com
        # `level: A2` — formato perfeito — e o texto dizia "Kelvin's Italian is
        # generally understandable", com "Top issue: Pronunciation - moin, moin
        # -> bonjour, bonjour". A transcricao e 100% ingles e o portao de idioma
        # tinha aprovado. Formato valido, conteudo inventado.
        #
        # Mesmo principio da recusa por idioma, 20 linhas acima: recusar nunca
        # pode parecer nota baixa. Um B1 falso em progress.md envenena a
        # ancoragem de nivel de todas as sessoes seguintes, e o Kelvin le o
        # grafico como progresso.
        print("[coach] Sessao NAO avaliada: o gateway falhou e quem respondeu foi "
              "o modelo local, que inventa avaliacao de ingles.")
        print("[coach] Nada gravado. Rodar de novo com o gateway de pe:")
        print(f"        python coach.py --transcript {args.transcript}")
        sys.exit(0)

    prev_level = _last_level()
    ev["level"], capped = guards.clamp_level(ev.get("level", ""), prev_level)
    if capped:
        print(f"[coach] {capped}")

    # Print summary to terminal
    print(f"\n{'='*60}")
    print(f"  ENGLISH COACH REPORT — {session_display}")
    print(f"{'='*60}")
    print(f"  Overall: {ev['overall']}/10  ({ev['level']})")
    print(f"  {_score_bar(int(round(ev['overall'])))} ")
    print("")
    for dim in DIMENSIONS:
        s = ev["scores"].get(dim, 0)
        print(f"  {DIM_PT[dim]:<12} {s:>2}/10  {_score_bar(s)}")
    print("")
    print(f"  {ev['summary']}")
    if ev.get("errors"):
        print(f"\n  Top issue: {ev['errors'][0]['type'].title()} — {ev['errors'][0]['original']}")
        print(f"  → {ev['errors'][0]['corrected']}")
    print(f"{'='*60}\n")

    # Save session note
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    ordem = _calls_no_dia(now)
    session_file = _daily_session_file(now)
    _render_session._fonte = args.transcript      # para o aviso de canal
    session_md = _render_session(ev, transcript, args.topic, now, args.topic_type, contexto)

    # Targets: carry the suggestion forward and measure it next time. Inserted
    # here rather than inside _render_session so the ledger is written once, from
    # the same place that decides the session is worth recording at all.
    # `transcript` is already Kelvin-only at this point.
    try:
        import coach_targets
        _tblock = coach_targets.run(COACH_DIR, transcript, ev, session_dt,
                                    now.date().isoformat())
        if _tblock:
            _marker = "## Evaluated excerpt"
            _text = chr(10).join(_tblock) + chr(10)
            if _marker in session_md:
                session_md = session_md.replace(_marker, _text + _marker, 1)
            else:
                session_md = session_md.rstrip() + chr(10) * 2 + _text
    except Exception as _e:  # noqa: BLE001 - never lose a session over the ledger
        print(f"[targets] skipped: {_e}")

    session_file.write_text(_consolidar_no_dia(session_file, session_md, now, ordem),
                            encoding="utf-8")
    print(f"[coach] Relatorio do dia atualizado (call {ordem}): {session_file}")

    # Append to progress log
    _append_progress(ev, now, args.topic, args.topic_type)
    print(f"[coach] Progress log updated: {PROGRESS_FILE}")

    # Update English-Learning index with latest status
    _update_index(ev, now, args.topic, args.topic_type)
    print(f"[coach] Index updated: {COACH_DIR / '_index.md'}")

    print(f"\nSESSION_FILE:{session_file}")


if __name__ == "__main__":
    main()
