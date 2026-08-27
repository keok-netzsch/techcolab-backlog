"""Validation guards for the English Coach.

Every function here exists because of a specific failure found in the 26/08/2026
audit of the 15 logged sessions. Kept in its own module, pure and dependency-free,
so each guard can be tested on its own and re-run against the historical sessions.

Audit summary that motivated this:
  - 8 of 15 sessions were Portuguese, scored as English (Whisper's own language
    detection said "en"); one had a 0-word transcript and still received B1.
  - The same transcript (sha1 5f7c41b1) was evaluated five times on 2026-06-08 and
    produced B2/B2/B2/B2/C1 with overall 6.7-7.6. Same input, different verdict.
  - A "strength" was quoted straight out of the prompt's own rubric text.
Run `python coach_guards.py` for the self-test.
"""
from __future__ import annotations

import re
import unicodedata

# ── Language gate ────────────────────────────────────────────────────────────
# Deliberately NOT Whisper's detected language: that is the thing that failed.
# Function-word ratio is deterministic, dependency-free, and decisive at
# transcript length — the audited files scored either ~100% or ~0%, never
# ambiguous.

_EN_MARKERS = {
    "the", "and", "that", "have", "for", "not", "with", "you", "this", "but",
    "from", "they", "will", "would", "there", "their", "what", "about", "which",
    "when", "make", "can", "like", "just", "know", "take", "into", "your",
    "some", "because", "these", "them", "then", "than", "were", "been", "does",
}
_PT_MARKERS = {
    "que", "nao", "uma", "com", "para", "mais", "como", "mas", "por", "isso",
    "ele", "ela", "voce", "esta", "sao", "tem", "foi", "ser", "entao", "aqui",
    "muito", "gente", "assim", "vou", "eles", "porque", "tambem", "tudo",
    "sabe", "acho", "coisa", "fazer", "ja", "nos", "meu", "seu", "pela",
}

MIN_ENGLISH_RATIO = 0.70
MIN_WORDS = 300


def _fold(text: str) -> str:
    """Strip accents so 'você' matches 'voce' — the marker lists are unaccented."""
    return "".join(c for c in unicodedata.normalize("NFD", text.lower())
                   if unicodedata.category(c) != "Mn")


def strip_timestamps(text: str) -> str:
    return re.sub(r"\[\d+(?:\.\d+)?s\]", " ", text)


def english_ratio(text: str) -> tuple[float, int]:
    """Return (english share of marker words, total word count)."""
    words = re.findall(r"[a-z']+", _fold(strip_timestamps(text)))
    en = sum(w in _EN_MARKERS for w in words)
    pt = sum(w in _PT_MARKERS for w in words)
    return (en / (en + pt) if en + pt else 0.0), len(words)


def language_gate(text: str, whisper_lang: str | None = None) -> tuple[bool, str]:
    """Decide whether this transcript may be scored at all.

    Returns (ok, reason). A refusal must produce a session note WITHOUT a score —
    never a low score, which is how Portuguese calls ended up graded B1/B2.
    """
    ratio, words = english_ratio(text)
    if words < MIN_WORDS:
        return False, (f"amostra insuficiente: {words} palavras "
                       f"(minimo {MIN_WORDS}) - sessao registrada sem nota")
    if ratio < MIN_ENGLISH_RATIO:
        return False, (f"transcript {ratio*100:.0f}% ingles "
                       f"(minimo {MIN_ENGLISH_RATIO*100:.0f}%) - nao avaliado")
    if whisper_lang and whisper_lang != "en":
        return False, f"Whisper detectou '{whisper_lang}' - conflito, nao avaliado"
    return True, f"ok: {words} palavras, {ratio*100:.0f}% ingles"


# ── Transcription-artifact filter ────────────────────────────────────────────
# The live failure was "to do to do to the way to the way": 33 chars (over the
# old 30-char cap) repeating INSIDE one segment (the old filter only compared
# whole lines, and only in the last 20% of the file). Both limits are gone.

def repetition_coverage(line: str) -> float:
    """Fraction of a line consumed by consecutive n-gram repetition.

    Counting repeats is the obvious approach and it misses the real case:
    "to do to do to the way to the way" contains no n-gram repeated three times
    in a row — it is two separate doubles ("to do" x2, then "to the way" x2).
    What gives it away is that repetition covers 100% of the line. A genuine
    sentence covers ~0%.
    """
    words = re.findall(r"[\w']+", strip_timestamps(line).lower())
    if not words:
        return 0.0
    covered = [False] * len(words)
    for n in range(1, min(5, len(words) // 2 + 1)):
        i = 0
        while i + 2 * n <= len(words):
            gram = words[i:i + n]
            j, reps = i + n, 1
            while j + n <= len(words) and words[j:j + n] == gram:
                reps, j = reps + 1, j + n
            # A single word must repeat 3x to count; longer grams only need 2 —
            # "very very" is speech, "to the way to the way" is a decoder loop.
            if reps >= (3 if n == 1 else 2):
                for k in range(i, j):
                    covered[k] = True
                i = j
            else:
                i += 1
    return sum(covered) / len(words)


def has_internal_repetition(line: str, threshold: float = 0.6,
                            min_words: int = 5) -> bool:
    """True when repetition dominates the line. Short utterances are exempt:
    'Yeah, yeah.' is backchannel, handled separately, not a transcription bug."""
    words = re.findall(r"[\w']+", strip_timestamps(line))
    if len(words) < min_words:
        return False
    return repetition_coverage(line) >= threshold


def clean_transcript(text: str, min_repeats: int = 5) -> tuple[str, list[str]]:
    """Drop hallucination artifacts. Returns (cleaned, dropped_lines).

    Two passes: phrases repeated across the WHOLE transcript (the old code only
    looked at the tail), and lines that repeat internally.
    """
    from collections import Counter

    lines = text.splitlines()
    payload = [ln.split("] ", 1)[-1].strip() for ln in lines]
    counts = Counter(p for p in payload if p)
    spam = {p for p, n in counts.items() if n >= min_repeats and len(p) < 80}

    kept, dropped = [], []
    for line, body in zip(lines, payload):
        if (body and body in spam) or has_internal_repetition(line):
            dropped.append(line)
        else:
            kept.append(line)
    return "\n".join(kept), dropped


# ── Hallucination guards on the model's output ───────────────────────────────

_PROMPT_ECHOES = ("apis, kpis, data pipelines", "apis, kpis and data pipelines",
                  "apis, kpis, and data pipelines")

BACKCHANNEL = {"mm-hmm", "mhm", "uh-huh", "yeah", "yeah yeah", "right", "ok",
               "okay", "got it", "i see", "sure", "exactly", "entendi", "sim"}


def _norm(s: str) -> str:
    return re.sub(r"[^\w\s]", "", _fold(s)).strip()


def quote_is_grounded(quote: str, transcript: str) -> bool:
    """The cited fragment must actually appear in the transcript.

    Applied to strengths as well as errors: the audit found a 'strength' lifted
    verbatim from the prompt's own rubric.
    """
    q = _norm(quote)
    return bool(q) and q in _norm(strip_timestamps(transcript))


def is_prompt_echo(text: str) -> bool:
    t = _norm(text)
    return any(_norm(e) in t for e in _PROMPT_ECHOES)


def is_backchannel(quote: str) -> bool:
    return _norm(quote) in {_norm(b) for b in BACKCHANNEL}


def filter_findings(findings: list[dict], transcript: str,
                    quote_key: str = "quote") -> tuple[list[dict], list[str]]:
    """Drop findings that are ungrounded, prompt echoes, or backchannel nitpicks."""
    kept, rejected = [], []
    for f in findings:
        q = str(f.get(quote_key, ""))
        if not quote_is_grounded(q, transcript):
            rejected.append(f"nao existe no transcript: {q!r}")
        elif is_prompt_echo(q) or is_prompt_echo(str(f)):
            rejected.append(f"eco do prompt: {q!r}")
        elif is_backchannel(q):
            rejected.append(f"backchannel, nao e erro: {q!r}")
        else:
            kept.append(f)
    return kept, rejected


# ── CEFR stability ───────────────────────────────────────────────────────────

CEFR = ["A1", "A2", "B1", "B2", "C1", "C2"]


def clamp_level(proposed: str, previous: str | None, max_step: int = 1) -> tuple[str, str | None]:
    """Never let the level move more than one sub-level per session.

    Enforced in code, not requested in the prompt: the audit saw B1 -> C1 -> B1,
    and five runs over one identical transcript that disagreed by a full level.
    """
    if previous is None or proposed not in CEFR or previous not in CEFR:
        return proposed, None
    p, q = CEFR.index(proposed), CEFR.index(previous)
    if abs(p - q) <= max_step:
        return proposed, None
    capped = CEFR[q + max_step * (1 if p > q else -1)]
    return capped, f"nivel {proposed} limitado a {capped} (anterior {previous})"


def rolling_level(history: list[str], proposed: str, window: int = 5) -> str:
    """CEFR is a slow-moving estimate, not a per-session output: take the mode of
    the recent window (ties resolve downward — conservative)."""
    from collections import Counter
    sample = [l for l in ([*history, proposed])[-window:] if l in CEFR]
    if not sample:
        return proposed
    top = max(Counter(sample).values())
    return min((l for l in sample if Counter(sample)[l] == top), key=CEFR.index)


def summary_contradicts_score(summary: str, overall: float) -> bool:
    """Reject 'low fluency, limited vocabulary' sitting next to 7/10."""
    negatives = ("low fluency", "limited vocabulary", "poor ", "struggles",
                 "difficult to understand", "lacks clarity")
    s = summary.lower()
    return overall >= 7.0 and any(n in s for n in negatives)


# ── Self-test against the real audit findings ────────────────────────────────

if __name__ == "__main__":
    ok = True

    def check(label, cond):
        global ok
        ok &= bool(cond)
        print(f"  [{'PASS' if cond else 'FAIL'}] {label}")

    print("language_gate")
    pt = ("Entao eu acho que a gente pode fazer isso aqui, sabe? "
          "Mas nao sei se ele tem essa clareza toda. " * 20)
    check("portugues recusado", not language_gate(pt)[0])
    en = ("I think that we can make this work, but I would like to know "
          "what they expect from us on this project. " * 20)
    check("ingles aceito", language_gate(en)[0])
    check("amostra curta recusada", not language_gate("I think we can do this.")[0])
    check("conflito com Whisper recusado", not language_gate(en, whisper_lang="pt")[0])

    print("artefato de transcricao")
    check("caso real 'to do to do to the way to the way'",
          has_internal_repetition("[012.0s] to do to do to the way to the way"))
    check("fala normal nao e artefato",
          not has_internal_repetition("[012.0s] I would like to share the screen"))
    cleaned, dropped = clean_transcript(
        "[001.0s] Let us start the meeting now\n"
        "[002.0s] to do to do to the way to the way\n"
        "[003.0s] That makes sense to me\n")
    check("artefato removido, resto preservado", len(dropped) == 1 and len(cleaned.splitlines()) == 2)

    print("guardas de alucinacao")
    tr = "[001.0s] So let me just share this screenshot with everyone"
    check("citacao real aceita", quote_is_grounded("let me just share this screenshot", tr))
    check("citacao inventada rejeitada", not quote_is_grounded("I have went there", tr))
    check("eco do prompt detectado",
          is_prompt_echo("Strong technical vocabulary related to APIs, KPIs, and data pipelines."))
    check("backchannel detectado", is_backchannel("Mm-hmm"))
    kept, rej = filter_findings(
        [{"quote": "let me just share this screenshot"},
         {"quote": "something never said"},
         {"quote": "Mm-hmm"}], tr)
    check("filtro mantem 1 de 3", len(kept) == 1 and len(rej) == 2)

    print("estabilidade do nivel")
    check("B1->C1 limitado a B2", clamp_level("C1", "B1")[0] == "B2")
    check("B1->B2 permitido", clamp_level("B2", "B1")[0] == "B2")
    check("primeira sessao passa", clamp_level("C1", None)[0] == "C1")
    check("moda da janela (B2 domina o outlier C1)",
          rolling_level(["B2", "B2", "B2", "B2"], "C1") == "B2")
    check("resumo negativo com 7/10 rejeitado",
          summary_contradicts_score("The speaker exhibited low fluency and structure", 7.0))

    print("\n" + ("TODOS OS TESTES PASSARAM" if ok else "FALHAS ACIMA"))
    raise SystemExit(0 if ok else 1)
