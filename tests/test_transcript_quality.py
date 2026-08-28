"""Transcript quality gate.

Every case here is a real line from a real recording, because the failure this
guards against was invisible to eyeballing: on 2026-08-28 the OKR 05 call passed
the existing words-per-minute check with 8209 words while its first 15 minutes
were 30 consecutive hallucinations, and Kelvin was about to forward it to Ana.

The false-positive cases matter as much as the true ones. A first version flagged
15 of 20 transcripts by treating ordinary Portuguese emphasis as degeneration; a
gate that cries wolf stops being read, which is the same as having no gate.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "call-recorder"))

import transcript_quality as q  # noqa: E402


# ── The 30-second window fingerprint ─────────────────────────────────────────

def test_consecutive_window_boundaries_are_flagged():
    """Whisper emits one invented line per silent 30 s window, so they land on
    0.0, 30.0, 60.0 ... Real speech does not start on round boundaries in a row."""
    texto = "\n".join(
        f"[{i*30:05.1f}s] Kelvin: This is the end of this video, I hope you enjoyed it."
        for i in range(6))
    runs = q.window_runs(q.parse(texto))
    assert len(runs) == 1 and len(runs[0]) == 6


def test_real_speech_timings_are_not_flagged():
    texto = "\n".join([
        "[012.4s] Kelvin: Vamos falar sobre a politica de export.",
        "[021.7s] Interlocutor: Concordo, mas precisamos definir o escopo.",
        "[034.9s] Kelvin: Exato, e por isso que eu queria a sua decisao.",
        "[047.2s] Interlocutor: Deixa eu ver os numeros primeiro.",
    ])
    assert q.window_runs(q.parse(texto)) == []


def test_two_boundary_hits_are_not_enough():
    """Coincidence happens; three in a row does not."""
    texto = "[030.0s] A: um\n[045.5s] A: dois\n[060.0s] A: tres"
    assert q.window_runs(q.parse(texto)) == []


def test_window_signal_works_without_any_phrase_list():
    """The structural signal must stand alone — it is the only one that survives
    a different language or a phrase the model has not been seen inventing yet."""
    texto = "\n".join(f"[{i*30:05.1f}s] Kelvin: Xyzzy plugh frobnicate."
                      for i in range(4))
    rep = q.scan(texto)
    assert len(rep["suspect"]) == 4
    assert all("janela vazia" in rep["motivos"][r[3]] for r in rep["suspect"])


# ── Human emphasis must survive ──────────────────────────────────────────────

def test_portuguese_emphasis_is_not_degeneration():
    """All six are real lines from real 1:1s. The first version flagged every one."""
    for linha in ("E, o VR, o VR.",
                  "Nao e o Cassio, nao e o Cassio.",
                  "Isso e legal, isso e legal.",
                  "de paises diferentes, de paises diferentes",
                  "que tem uma chance, que tem uma oportunidade, que tem uma oportunidade.",
                  "estoques. Nao, ele olha, ele olha."):
        assert not q.internal_repetition(linha), linha


def test_decoder_loop_is_degeneration():
    assert q.internal_repetition(
        "I'm sorry, I'm sorry, I'm sorry, I'm sorry, I'm sorry, I'm sorry, I'm sorry")


def test_short_utterances_are_never_flagged():
    for linha in ("Yeah, yeah.", "Entendi.", "Ok ok"):
        assert not q.internal_repetition(linha)


# ── Training-set phrases ─────────────────────────────────────────────────────

def test_training_phrases_are_caught_in_several_languages():
    for linha in ("[010.2s] K: thanks for watching, see you next time",
                  "[010.2s] K: obrigado por assistir, inscreva-se",
                  "[010.2s] K: legendas pela comunidade Amara.org"):
        assert len(q.scan(linha)["suspect"]) == 1, linha


def test_ordinary_business_talk_is_clean():
    texto = "\n".join([
        "[012.4s] Kelvin: The export policy needs a decision from you.",
        "[021.7s] Interlocutor: I understand the risk of a bottleneck.",
        "[039.1s] Kelvin: Governance as a facilitator, not as an umbrella.",
    ])
    assert q.scan(texto)["ok"]


# ── Cleaning ─────────────────────────────────────────────────────────────────

def test_cleaning_removes_only_the_suspect_lines():
    texto = "\n".join([
        "[000.0s] Kelvin: This is the end of this video, I hope you enjoyed it.",
        "[030.0s] Kelvin: This is the end of this video, I hope you enjoyed it.",
        "[060.0s] Kelvin: This is the end of this video, I hope you enjoyed it.",
        "[071.3s] Kelvin: Ok, entao vamos ao ponto da politica de export.",
        "[084.9s] Interlocutor: Certo, me mostra os numeros.",
    ])
    limpo, fora = q.clean(texto)
    assert len(fora) == 3
    assert "politica de export" in limpo and "numeros" in limpo
    assert "end of this video" not in limpo


def test_cleaned_output_passes_its_own_gate():
    """Whatever the gate hands back must itself be clean, or the report lies."""
    texto = "\n".join(
        [f"[{i*30:05.1f}s] K: hope you enjoyed it" for i in range(5)] +
        ["[171.3s] K: agora sim, conteudo de verdade sobre o projeto"])
    limpo, _ = q.clean(texto)
    assert q.scan(limpo)["ok"]


def test_per_speaker_breakdown_locates_the_damage():
    """The OKR 05 failure was one-sided: Kelvin's channel was dead while the
    other party's was fine. A file-level verdict would have hidden that."""
    texto = "\n".join(
        [f"[{i*30:05.1f}s] Kelvin: thanks for watching" for i in range(4)] +
        ["[131.0s] Interlocutor: entao a decisao fica com voce",
         "[145.2s] Interlocutor: eu preciso ver o documento antes"])
    rep = q.scan(texto)
    assert rep["speakers"]["Kelvin"]["suspeitas"] == 4
    assert rep["speakers"]["Interlocutor"]["suspeitas"] == 0


def test_empty_or_unparseable_input_is_not_called_ok():
    assert not q.scan("")["ok"]
    assert not q.scan("linha sem timestamp nenhum")["ok"]
