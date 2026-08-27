"""Personal error inventory for the English Coach — L1-interference detection.

Why this exists
---------------
The coach used to ask a 7B model "assess this person's English". That is an
open-ended judgement task, and the 26/08/2026 audit showed what it produces:
invented grammar rules ("'I don't know the details' is incorrect"), praise copied
out of the prompt, and a CEFR level that moved B1 -> C1 -> B1 on a whim.

For a speaker who is already fluent, that framing is useless anyway. What limits
a solid B2/C1 Brazilian professional is not grammar in general — it is a small,
stable set of Portuguese-shaped habits that survive fluency. Those are countable.

So the task is reframed from assessment to detection:
  - RULES here catch what can be decided with certainty. No LLM, no false rules.
  - PROBES hand the model a specific yes/no hypothesis about one quoted span,
    which small models answer far more reliably than open-ended grading.

The output is not a score. It is an inventory that persists across sessions, so
progress means "this pattern went from 4 per 1000 words to 0", which is something
Kelvin can actually act on.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Rule:
    pid: str
    pattern: str                 # regex, matched case-insensitively
    label: str
    fix: str
    why: str = ""
    _rx: re.Pattern = field(default=None, compare=False, repr=False)

    def compiled(self) -> re.Pattern:
        return re.compile(self.pattern, re.I)


# ── Certain: unambiguous in professional English. Safe to report as errors. ───
# Every entry is a documented Brazilian-Portuguese interference pattern. Nothing
# goes in here unless it is wrong in ALL contexts — the point is zero false
# positives, because one invented rule destroys trust in the whole report.

RULES: list[Rule] = [
    Rule("uncountable-plural",
         r"\b(informations|feedbacks|trainings|advices|equipments|softwares|knowledges|researches|staffs)\b",
         "substantivo incontável pluralizado",
         "information / feedback / training / advice (sem -s)",
         "em PT sao contaveis; em EN nao. Marca de falante brasileiro mesmo fluente."),
    Rule("explain-me",
         r"\bexplain\s+(me|us|him|her|them)\b",
         "'explain me' sem preposição",
         "explain TO me",
         "explain nao aceita objeto indireto direto, ao contrario de 'explicar-me'."),
    Rule("say-me",
         r"\bsay\s+(me|us|him|her|them)\b",
         "'say me' em vez de 'tell me'",
         "tell me / say to me",
         ""),
    Rule("depend-of",
         r"\bdepend(s|ed|ing)?\s+of\b",
         "'depend of'",
         "depend ON",
         "calco de 'depender de'."),
    Rule("responsible-of",
         r"\bresponsible\s+of\b",
         "'responsible of'",
         "responsible FOR",
         ""),
    Rule("discuss-about",
         r"\bdiscuss(ed|ing|es)?\s+about\b",
         "'discuss about'",
         "discuss (sem preposição)",
         "calco de 'discutir sobre'."),
    Rule("according-with",
         r"\baccording\s+with\b",
         "'according with'",
         "according TO",
         ""),
    Rule("arrive-to",
         r"\barrive[ds]?\s+to\b",
         "'arrive to'",
         "arrive AT / arrive IN",
         ""),
    Rule("do-a-mistake",
         r"\b(do|did|does|doing)\s+(a|the|some)?\s*mistakes?\b",
         "'do a mistake'",
         "MAKE a mistake",
         ""),
    Rule("make-a-question",
         r"\bmake\s+(a|the|some)?\s*questions?\b",
         "'make a question'",
         "ASK a question",
         "calco de 'fazer uma pergunta'."),
    Rule("i-am-agree",
         r"\b(i\s+am|i'm|we\s+are|we're)\s+agree\b",
         "'I am agree'",
         "I agree",
         "'agree' e verbo em EN, nao adjetivo."),
    Rule("people-is",
         r"\bpeople\s+(is|was|has)\b",
         "'people is'",
         "people ARE / WERE / HAVE",
         ""),
    Rule("have-doubt",
         r"\b(have|had|has)\s+(a|some|one)?\s*doubts?\b",
         "'I have a doubt'",
         "I have a question",
         "calco de 'tenho uma duvida'; 'doubt' em EN e descrenca, nao pergunta."),
    Rule("assist-to",
         r"\bassist(ed|ing)?\s+to\s+(the\s+)?(meeting|call|session|presentation)\b",
         "'assist to a meeting'",
         "ATTEND a meeting",
         "falso amigo de 'assistir'."),
    Rule("double-comparative",
         r"\bmore\s+(easy|cheap|big|small|fast|hard|simple|clear|strong|old|young)\b",
         "comparativo duplo",
         "easier / cheaper / bigger",
         ""),
    Rule("did-past",
         r"\b(didn't|did\s+not)\s+(went|saw|had|made|said|took|got|came|knew|thought)\b",
         "auxiliar 'did' com verbo no passado",
         "didn't + forma base (didn't go)",
         ""),
]


# ── Probes: real errors ONLY in a specific sense. The model gets one narrow
# yes/no question about one quoted span — never open-ended grading.

@dataclass(frozen=True)
class Probe:
    pid: str
    pattern: str
    question: str
    fix: str

    def compiled(self) -> re.Pattern:
        return re.compile(self.pattern, re.I)


PROBES: list[Probe] = [
    Probe("until-deadline", r"\buntil\s+(monday|tuesday|wednesday|thursday|friday|next\s+\w+|the\s+end\s+of\s+\w+|tomorrow)\b",
          "Neste trecho, 'until X' significa um PRAZO de entrega (ate X, entregando em X)? "
          "Se sim e erro: o correto seria 'by X'. Se significa duracao continua ate X, esta correto.",
          "by X (prazo) em vez de until X (duracao)"),
    Probe("actually-currently", r"\bactually\b",
          "Neste trecho, 'actually' foi usado com o sentido de 'atualmente/no momento'? "
          "Se sim e erro (o correto seria 'currently'). Se significa 'na verdade', esta correto.",
          "currently"),
    Probe("realize-carry-out", r"\brealiz(e|ed|ing|es)\b",
          "Neste trecho, 'realize' foi usado com o sentido de 'realizar/executar'? "
          "Se sim e erro (o correto seria 'carry out', 'run', 'hold'). "
          "Se significa 'perceber/dar-se conta', esta correto.",
          "carry out / run / hold"),
    Probe("pretend-intend", r"\bpretend(s|ed|ing)?\b",
          "Neste trecho, 'pretend' foi usado com o sentido de 'pretender/ter a intencao'? "
          "Se sim e erro (o correto seria 'intend' ou 'plan to'). "
          "Se significa 'fingir', esta correto.",
          "intend to / plan to"),
    Probe("support-tolerate", r"\bsupport(s|ed|ing)?\b",
          "Neste trecho, 'support' foi usado com o sentido de 'suportar/tolerar/aguentar'? "
          "Se sim e erro (o correto seria 'put up with', 'handle', 'bear'). "
          "Se significa 'apoiar/dar suporte', esta correto.",
          "handle / bear / put up with"),
    Probe("eventually-maybe", r"\beventually\b",
          "Neste trecho, 'eventually' foi usado com o sentido de 'eventualmente/talvez/as vezes'? "
          "Se sim e erro (o correto seria 'possibly', 'occasionally'). "
          "Se significa 'por fim/mais cedo ou mais tarde', esta correto.",
          "possibly / occasionally"),
]


# ── Detection ────────────────────────────────────────────────────────────────

def _speaker_lines(transcript: str, speaker: str = "Kelvin") -> str:
    """With dual-channel capture only our own side may be graded. Without labels
    the composition is unknown, so the caller is told by returning the text
    unchanged — the language gate and sample floor are the safety net there."""
    labelled = [ln for ln in transcript.splitlines() if f"{speaker}:" in ln]
    return "\n".join(labelled) if labelled else transcript


def _context(text: str, start: int, end: int, width: int = 60) -> str:
    return text[max(0, start - width):min(len(text), end + width)].replace("\n", " ").strip()


def detect(transcript: str, speaker: str = "Kelvin") -> dict:
    """Return {'certain': [...], 'probes': [...], 'words': int}.

    'certain' items are ready to report. 'probes' still need one narrow model call
    each; until answered they are hypotheses, not findings, and must not be shown
    to Kelvin as errors.
    """
    text = _speaker_lines(transcript, speaker)
    text = re.sub(r"\[\d+(?:\.\d+)?s\]", " ", text)
    words = len(re.findall(r"[\w']+", text))

    certain = []
    for rule in RULES:
        for m in rule.compiled().finditer(text):
            certain.append({"pid": rule.pid, "label": rule.label, "fix": rule.fix,
                            "why": rule.why, "quote": m.group(0),
                            "context": _context(text, m.start(), m.end())})

    probes = []
    for probe in PROBES:
        for m in probe.compiled().finditer(text):
            probes.append({"pid": probe.pid, "quote": m.group(0), "fix": probe.fix,
                           "question": probe.question,
                           "context": _context(text, m.start(), m.end())})

    return {"certain": certain, "probes": probes, "words": words}


def rate_per_1000(count: int, words: int) -> float:
    """Normalised so a 40-minute call and a 10-minute one are comparable — the
    only way 'am I improving' can be answered honestly across uneven sessions."""
    return round(count * 1000 / words, 2) if words else 0.0


def summarise(detection: dict) -> dict:
    """Collapse hits into per-pattern counts and rates for the inventory."""
    from collections import Counter
    words = detection["words"]
    counts = Counter(h["pid"] for h in detection["certain"])
    return {pid: {"count": n, "per_1000": rate_per_1000(n, words)}
            for pid, n in counts.most_common()}


# ── Self-test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ok = True

    def check(label, cond):
        global ok
        ok &= bool(cond)
        print(f"  [{'PASS' if cond else 'FAIL'}] {label}")

    print("deteccao certa (interferencia do portugues)")
    sample = (
        "[001.0s] Kelvin: I will send you the informations tomorrow.\n"
        "[002.0s] Kelvin: Can you explain me how this works?\n"
        "[003.0s] Kelvin: That depends of the customer.\n"
        "[004.0s] Kelvin: We need to discuss about the roadmap.\n"
        "[005.0s] Kelvin: I have a doubt about the deadline.\n"
        "[006.0s] Kelvin: The people is worried about it.\n"
    )
    d = detect(sample)
    pids = {h["pid"] for h in d["certain"]}
    for expected in ("uncountable-plural", "explain-me", "depend-of",
                     "discuss-about", "have-doubt", "people-is"):
        check(expected, expected in pids)

    print("sem falso positivo em ingles correto")
    clean = ("[001.0s] Kelvin: I will send you the information tomorrow, and I can "
             "explain to me... sorry, explain it to you then. That depends on the "
             "customer, so let us discuss the roadmap and I have a question.\n")
    dc = detect(clean)
    check("nenhum erro em texto correto", len(dc["certain"]) == 0)

    print("so o canal do Kelvin e avaliado")
    dual = ("[001.0s] Kelvin: We discussed the roadmap yesterday.\n"
            "[002.0s] Interlocutor: I have a doubt about the informations.\n")
    dd = detect(dual)
    check("erro do interlocutor ignorado", len(dd["certain"]) == 0)

    print("probes sao hipoteses, nao erros")
    amb = ("[001.0s] Kelvin: Actually I will send it until Friday, and we realize "
           "the workshop next month.\n")
    da = detect(amb)
    check("nada reportado como erro certo", len(da["certain"]) == 0)
    ppids = {p["pid"] for p in da["probes"]}
    for expected in ("until-deadline", "actually-currently", "realize-carry-out"):
        check(f"probe {expected}", expected in ppids)

    print("normalizacao por mil palavras")
    check("taxa comparavel entre sessoes", rate_per_1000(4, 2000) == 2.0)
    check("sessao vazia nao divide por zero", rate_per_1000(0, 0) == 0.0)

    print("\n" + ("TODOS OS TESTES PASSARAM" if ok else "FALHAS ACIMA"))
    raise SystemExit(0 if ok else 1)
