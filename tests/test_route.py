"""Slicing a call transcript by time window, and parsing the routes that ask for it.

A recording covers several subjects and each one belongs somewhere different, so a
route says *which slice goes where*. Both halves are load-bearing: a wrong window
files a confident note built on the wrong part of the call, and a misparsed route
sends it to the wrong person's folder. Neither failure is visible afterwards — the
note reads perfectly well in the wrong place.

The cut is deliberately deterministic. The first implementation asked the local
model which passages were about a subject and it answered "(nada)" for a window
that plainly discussed it, so boundaries now come from whoever read the transcript.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "call-recorder"))

import process  # noqa: E402
import route  # noqa: E402

TRANSCRIPT = "\n".join([
    "[000.0s] Kelvin: bom dia, vamos comecar pelo OKR",
    "[012.5s] Interlocutor: os artigos estao em tres de cinco",
    "[060.0s] Kelvin: e a D&A community?",
    "[125.9s] Interlocutor: abriu semana passada",
    "[300.0s] Kelvin: mudando de assunto, as entregas do sprint",
    "[420.1s] Interlocutor: o BIA-023 escorregou dois dias",
])


# ── slice_by_time ─────────────────────────────────────────────────────────────

def test_window_keeps_only_lines_inside_it():
    out = process.slice_by_time(TRANSCRIPT, 0, 130)
    assert "OKR" in out and "D&A community" in out
    assert "sprint" not in out and "BIA-023" not in out


def test_open_ended_start_and_end():
    assert len(process.slice_by_time(TRANSCRIPT, None, 60).splitlines()) == 3
    assert len(process.slice_by_time(TRANSCRIPT, 300, None).splitlines()) == 2


def test_no_bounds_returns_transcript_untouched():
    assert process.slice_by_time(TRANSCRIPT) == TRANSCRIPT


def test_adjacent_windows_neither_lose_nor_duplicate_a_line():
    """Two destinations splitting one call must together cover it exactly once."""
    first = process.slice_by_time(TRANSCRIPT, None, 299)
    second = process.slice_by_time(TRANSCRIPT, 299.001, None)
    assert (len(first.splitlines()) + len(second.splitlines())
            == len(TRANSCRIPT.splitlines()))
    assert set(first.splitlines()).isdisjoint(second.splitlines())


def test_bounds_are_inclusive_on_both_ends():
    out = process.slice_by_time(TRANSCRIPT, 12.5, 12.5)
    assert out.startswith("[012.5s]") and len(out.splitlines()) == 1


def test_window_past_the_end_returns_empty_rather_than_the_whole_call():
    # Silently falling back to "everything" would file the entire recording under
    # a destination that was meant to get one topic.
    assert process.slice_by_time(TRANSCRIPT, 9000, None) == ""


def test_unstamped_continuation_line_follows_the_line_above_it():
    text = "[000.0s] primeira\ncontinuacao sem stamp\n[300.0s] depois"
    out = process.slice_by_time(text, None, 100)
    assert "continuacao sem stamp" in out
    assert "depois" not in out


# ── route parsing ─────────────────────────────────────────────────────────────

def test_each_destination_keeps_its_own_window():
    routes = route._pair_routes([
        "id", "--para", "person:Daniel-Lima", "--de", "0", "--ate", "11:20",
        "--assunto", "OKR de artigos",
        "--para", "project", "--de", "11:20", "--assunto", "entregas",
    ])
    assert routes[0] == {"kind": "person", "target": "Daniel-Lima",
                         "topic": "OKR de artigos", "de": 0.0, "ate": 680.0}
    assert routes[1] == {"kind": "project", "target": "",
                         "topic": "entregas", "de": 680.0, "ate": None}


def test_destination_without_flags_takes_the_whole_call():
    assert route._pair_routes(["id", "--para", "project"]) == [
        {"kind": "project", "target": "", "topic": "", "de": None, "ate": None}]


def test_a_flagless_destination_does_not_steal_the_next_ones_window():
    """The bug that zipping two flag lists would introduce."""
    routes = route._pair_routes([
        "id", "--para", "person:Ana-Leite",
        "--para", "project", "--de", "60",
    ])
    assert routes[0]["de"] is None
    assert routes[1]["de"] == 60.0


def test_time_accepts_seconds_mmss_and_hmmss():
    assert route._seconds("272") == 272.0
    assert route._seconds("4:32") == 272.0
    assert route._seconds("1:02:30") == 3750.0


def test_unparseable_time_is_refused_not_coerced_to_zero():
    # Coercing to 0 would silently widen the window to the start of the call.
    try:
        route._seconds("meia hora")
    except SystemExit:
        return
    raise AssertionError("tempo invalido deveria ser recusado")


# ── Regras de roteamento por reuniao (decisao do Kelvin, 2026-08-29) ─────────
# Daily BIZ/PM sao territorio do Team Memory Agent; a listagem tem que carregar
# a regra junto, senao a sessao que roteia arquiva o mesmo fato duas vezes.


def test_rule_for_daily_biz_e_pm():
    assert "TMA" in route.rule_for("Ingresso na reuniao | Daily BIZ | Microsoft Teams")
    assert "TMA" in route.rule_for("Meeting join | Daily PM | Microsoft Teams")


def test_rule_for_nao_pega_outras_reunioes():
    assert route.rule_for("Jour Fixe KO <> AR | Microsoft Teams") == ""
    assert route.rule_for("BIA War Room") == ""
    assert route.rule_for("") == ""
