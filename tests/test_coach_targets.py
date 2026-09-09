"""Tests for call-recorder/coach_targets.py — the prescribe-then-verify loop.

The point of this module is that a suggestion survives the session it was made
in, so the tests run several sessions in a row against one ledger. A test that
only checks a single call would miss the only behaviour that matters.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "call-recorder"))

import coach_targets as ct  # noqa: E402


@pytest.fixture
def coach_dir(tmp_path):
    d = tmp_path / "English-Learning"
    d.mkdir()
    return d


def _ev(vocab=None, errors=None):
    return {"vocabulary_suggestions": vocab or [], "errors": errors or []}


# Palavras REAIS de proposito: desde 09/09 o modulo recusa alvo que nao pareca
# ingles, entao placeholder ("alt0") nao serve mais como fixture.
REAL_WORDS = ['leverage', 'outline', 'scope', 'insight', 'baseline', 'handover', 'rollout', 'tradeoff', 'backlog', 'milestone', 'workload', 'forecast', 'guidance', 'alignment', 'ownership', 'clarity', 'rationale', 'cadence', 'constraint', 'dependency', 'estimate', 'priority']
REAL_USED = ['issue', 'matter', 'topic', 'item', 'point', 'note', 'plan',
             'draft', 'review', 'update', 'change', 'request', 'answer',
             'result', 'target', 'effort', 'impact', 'risk', 'gap',
             'step', 'task', 'goal']
REAL_BAD = ['assist to', 'depend of', 'explain me', 'discuss about']
REAL_GOOD = ['attend', 'depend on', 'explain to me', 'discuss']
VOCAB = [{"used": "shelf solutions", "alternatives": ["off-the-shelf solutions"]}]
ERRORS = [{"type": "collocation", "original": "relating to",
           "corrected": "referring to", "explanation": "false friend"}]


# ── Matching ─────────────────────────────────────────────────────────────────

def test_occurrences_is_word_bounded():
    # "use" must not match "used", or every session would score a false hit.
    assert ct._occurrences("I used it", "use") == 0
    assert ct._occurrences("I use it", "use") == 1


def test_occurrences_matches_multiword_phrase_and_ignores_case():
    text = "we bought Off-the-shelf   solutions"
    assert ct._occurrences(text, "off-the-shelf solutions") == 1


# ── The loop ─────────────────────────────────────────────────────────────────

def test_first_session_only_prescribes(coach_dir):
    block = ct.run(coach_dir, "nothing relevant here", _ev(VOCAB, ERRORS),
                   "2026-09-01_10-00", "2026-09-01")
    data = ct.load(coach_dir)
    assert [t["kind"] for t in data["targets"]] == ["use", "avoid"]
    assert all(t["status"] == "active" for t in data["targets"])
    assert "For the next call" in "\n".join(block)


def test_use_target_retires_after_two_sessions_using_it(coach_dir):
    ct.run(coach_dir, "nothing", _ev(VOCAB), "s1", "2026-09-01")
    ct.run(coach_dir, "we went with off-the-shelf solutions", _ev(), "s2", "2026-09-02")
    assert ct.load(coach_dir)["targets"][0]["status"] == "active"   # one hit is luck

    ct.run(coach_dir, "again, off-the-shelf solutions", _ev(), "s3", "2026-09-03")
    t = ct.load(coach_dir)["targets"][0]
    assert t["status"] == "achieved" and t["achieved_on"] == "2026-09-03"


def test_quiet_session_does_not_reset_a_use_streak(coach_dir):
    """A call where the word did not come up is not a regression — only an
    'avoid' streak is about consecutive clean sessions."""
    ct.run(coach_dir, "nothing", _ev(VOCAB), "s1", "2026-09-01")
    ct.run(coach_dir, "off-the-shelf solutions", _ev(), "s2", "2026-09-02")
    ct.run(coach_dir, "unrelated call", _ev(), "s3", "2026-09-03")
    assert ct.load(coach_dir)["targets"][0]["streak"] == 1


def test_avoid_target_resets_on_a_slip(coach_dir):
    ct.run(coach_dir, "x", _ev(errors=ERRORS), "s1", "2026-09-01")
    ct.run(coach_dir, "clean call", _ev(), "s2", "2026-09-02")
    assert ct.load(coach_dir)["targets"][0]["streak"] == 1
    ct.run(coach_dir, "relating to the budget", _ev(), "s3", "2026-09-03")
    t = ct.load(coach_dir)["targets"][0]
    assert t["streak"] == 0 and t["status"] == "active"


def test_active_targets_are_capped(coach_dir):
    vocab = [{"used": REAL_USED[i], "alternatives": [REAL_WORDS[i]]} for i in range(20)]
    ct.run(coach_dir, "x", _ev(vocab), "s1", "2026-09-01")
    active = [t for t in ct.load(coach_dir)["targets"] if t["status"] == "active"]
    assert len(active) == ct.MAX_ACTIVE


def test_achieved_target_frees_a_slot_and_is_never_reassigned(coach_dir):
    ct.run(coach_dir, "x", _ev(VOCAB), "s1", "2026-09-01")
    ct.run(coach_dir, "off-the-shelf solutions", _ev(), "s2", "2026-09-02")
    ct.run(coach_dir, "off-the-shelf solutions", _ev(), "s3", "2026-09-03")
    # Same suggestion offered again after it retired: it must not come back.
    ct.run(coach_dir, "x", _ev(VOCAB), "s4", "2026-09-04")
    targets = ct.load(coach_dir)["targets"]
    assert sum(1 for t in targets if t["target"] == "off-the-shelf solutions") == 1


def test_target_with_no_progress_is_flagged_not_dropped(coach_dir):
    ct.run(coach_dir, "x", _ev(VOCAB), "s0", "2026-09-01")
    for i in range(ct.STUCK_AFTER):
        ct.run(coach_dir, "unrelated", _ev(), f"s{i+1}", "2026-09-02")
    t = ct.load(coach_dir)["targets"][0]
    assert t["status"] == "active" and t["stuck"] is True


def test_corrupt_ledger_does_not_raise(coach_dir):
    (coach_dir / "targets.json").write_text("{ not json", encoding="utf-8")
    ct.run(coach_dir, "x", _ev(VOCAB), "s1", "2026-09-01")
    assert ct.load(coach_dir)["targets"]


def test_reported_counts_reflect_the_transcript(coach_dir):
    ct.run(coach_dir, "x", _ev(VOCAB), "s1", "2026-09-01")
    data = ct.load(coach_dir)
    results = ct.check("off-the-shelf solutions and off-the-shelf solutions", data)
    assert results[0]["count"] == 2 and results[0]["good"] is True


def test_one_alternative_per_habit(coach_dir):
    """The model offers several ways to replace one phrase. Taking all of them
    spent 3 of 6 slots on a single habit on the first real run."""
    vocab = [{"used": "sell it out", "alternatives": ["sell it", "market it", "offer it"]}]
    ct.run(coach_dir, "x", _ev(vocab), "s1", "2026-09-01")
    targets = [t["target"] for t in ct.load(coach_dir)["targets"]]
    assert targets == ["sell it"]


def test_batch_mixes_use_and_avoid(coach_dir):
    """Six vocabulary suggestions used to fill every slot and push out every
    habit worth dropping."""
    vocab = [{"used": REAL_USED[i], "alternatives": [REAL_WORDS[i]]} for i in range(6)]
    errors = [{"type": "collocation", "original": REAL_BAD[i],
               "corrected": REAL_GOOD[i], "explanation": "x"} for i in range(3)]
    ct.run(coach_dir, "x", _ev(vocab, errors), "s1", "2026-09-01")
    kinds = {t["kind"] for t in ct.load(coach_dir)["targets"]}
    assert kinds == {"use", "avoid"}


def test_same_habit_reported_twice_takes_one_slot(coach_dir):
    """The model reports one habit as both a vocabulary upgrade and an error.
    Taking both spent two slots saying the same thing on the first real run."""
    vocab = [{"used": "shelf solutions", "alternatives": ["off-the-shelf solutions"]}]
    errors = [{"type": "collocation", "original": "shelf solutions",
               "corrected": "off-the-shelf solutions", "explanation": "truncated"}]
    ct.run(coach_dir, "x", _ev(vocab, errors), "s1", "2026-09-01")
    assert len(ct.load(coach_dir)["targets"]) == 1


def test_ruido_de_transcricao_nao_vira_alvo(coach_dir):
    """Em 02/09 um transcript degenerado gerou 'sino destra' e 'HP Kelvin
    (pronounced: Hel-po Kelvin)'. Nao sao frases; ocuparam slot por semanas."""
    vocab = [{"used": "side, you know, right", "alternatives": ["sino destra"]},
             {"used": "operation model", "alternatives": ["operating model"]}]
    ct.run(coach_dir, "x", _ev(vocab), "s1", "2026-09-02")
    alvos = [t["target"] for t in ct.load(coach_dir)["targets"]]
    assert alvos == ["operating model"]


def test_alvo_legitimo_multipalavra_passa(coach_dir):
    """A guarda nao pode barrar frase boa: 'off-the-shelf solutions' tem 4
    palavras, todas inglesas."""
    vocab = [{"used": "shelf solutions", "alternatives": ["off-the-shelf solutions"]}]
    ct.run(coach_dir, "x", _ev(vocab), "s1", "2026-09-02")
    assert [t["target"] for t in ct.load(coach_dir)["targets"]] == ["off-the-shelf solutions"]


# ── coach_grammar: refresh incremental ───────────────────────────────────────
# O gancho no coach.py roda a cada sessao. Se ele substituisse o arquivo em vez
# de mesclar, cada call apagaria o registro escrito, que custa varrer 275
# transcritos para reconstruir.

def test_refresh_speech_preserva_o_registro_escrito(tmp_path, monkeypatch):
    import json
    import coach_grammar as cg

    out = tmp_path / "grammar.json"
    out.write_text(json.dumps({
        "meta": {"gerado_em": "2026-09-09T00:00:00"},
        "registros": {
            "fala": {"registro": "fala", "palavras": 1, "hits": {}, "probes": {},
                     "exemplos": {}, "unidades": 1},
            "escrito-informal": {"registro": "escrito-informal", "palavras": 6637,
                                 "hits": {"x": 1}, "probes": {}, "exemplos": {},
                                 "unidades": 1044, "typos": {"pra": 1}},
        }}, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(cg, "OUT_FILE", out)
    monkeypatch.setattr(cg, "SESSIONS_DIR", tmp_path / "sessions")  # vazio
    cg.refresh_speech()

    depois = json.loads(out.read_text(encoding="utf-8"))
    escrito = depois["registros"]["escrito-informal"]
    assert escrito["palavras"] == 6637 and escrito["typos"] == {"pra": 1}
    assert depois["registros"]["fala"]["palavras"] == 0
