"""Routing of auto-captured calls into the vault (classify).

This module decides which person's file a recording is written into, so a wrong
match is not a cosmetic bug — it puts a 1:1 in someone else's folder. The tests
therefore lean on the refusal cases as much as the happy path.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "call-recorder"))

import classify  # noqa: E402

TEAM = ["Ana-Leite", "Daniel-Lima", "Lucas-Shizuno", "Pedro-Hennig", "Pedro-Klein"]
STAKE = ["Alberto-Reuters", "Hernan-Morales", "Stefan-Lautenschlager"]


def _title(t):
    return {"window_title": t}


def test_teams_chrome_is_stripped():
    assert classify._title_core("Chat | Leite, Ana | Microsoft Teams") == "Leite, Ana"
    assert classify._title_core(
        "Ingresso na reunião | Daily BIZ | Microsoft Teams") == "Daily BIZ"


def test_direct_report_goes_to_team():
    v = classify.classify(_title("Chat | Leite, Ana | Microsoft Teams"), TEAM, STAKE)
    assert (v["kind"], v["target"]) == ("person", "Ana-Leite")


def test_stakeholder_goes_to_stakeholders():
    v = classify.classify(_title("Chat | Morales, Hernan | Microsoft Teams"), TEAM, STAKE)
    assert (v["kind"], v["target"]) == ("manager", "Hernan-Morales")


def test_shared_first_name_never_cross_matches():
    """Pedro-Hennig and Pedro-Klein share a first name. Matching on 'Pedro'
    alone would file one person's 1:1 under the other."""
    v = classify.classify(_title("Chat | Klein, Pedro | Microsoft Teams"), TEAM, STAKE)
    assert v["target"] == "Pedro-Klein"
    v2 = classify.classify(_title("Chat | Hennig, Pedro | Microsoft Teams"), TEAM, STAKE)
    assert v2["target"] == "Pedro-Hennig"


def test_first_name_alone_is_not_enough():
    v = classify.classify(_title("Chat | Pedro | Microsoft Teams"), TEAM, STAKE)
    assert v["target"] == ""          # ambiguous — must not pick either Pedro


def test_unknown_person_becomes_a_loose_note_not_a_guess():
    v = classify.classify(_title("Chat | Toshio Shiki, Fabio | Microsoft Teams"),
                          TEAM, STAKE)
    assert v["kind"] == "note" and v["target"] == ""


def test_project_meeting_is_recognised():
    for t in ("Meeting join | Daily BIZ | Microsoft Teams",
              "Meeting join | BIA War Room | Microsoft Teams",
              "Meeting join | Power BI Data Export | Microsoft Teams"):
        assert classify.classify(_title(t), TEAM, STAKE)["kind"] == "project"


def test_declared_alias_beats_the_heuristics(tmp_path, monkeypatch):
    """"Jour Fixe KO <> AR" carries only initials; nothing can infer Alberto
    Reuters from it safely, so a human declares it once."""
    aliases = tmp_path / "meeting-aliases.json"
    aliases.write_text(
        '{"jour fixe ko <> ar": {"kind": "manager", "target": "Alberto-Reuters"}}',
        encoding="utf-8")
    monkeypatch.setattr(classify, "ALIASES_FILE", aliases)
    v = classify.classify(_title("Meeting join | Jour Fixe KO <> AR | Microsoft Teams"),
                          TEAM, STAKE)
    assert (v["kind"], v["target"]) == ("manager", "Alberto-Reuters")


def test_missing_alias_file_is_not_fatal(tmp_path, monkeypatch):
    monkeypatch.setattr(classify, "ALIASES_FILE", tmp_path / "nao-existe.json")
    v = classify.classify(_title("Chat | Leite, Ana | Microsoft Teams"), TEAM, STAKE)
    assert v["target"] == "Ana-Leite"


def test_job_carries_the_original_meeting_and_start_time():
    pend = {"wav": "2026-08-28_11-46_auto.wav",
            "started": "2026-08-28T11:46:57",
            "window_title": "Chat | Leite, Ana | Microsoft Teams"}
    job = classify.build_job(None, pend, {"kind": "person", "target": "Ana-Leite"})
    assert job["date"] == "2026-08-28" and job["time"] == "11-46"
    assert "Leite, Ana" in job["meeting"]      # provenance survives into the vault
    assert job["lang"] == "auto"               # English still reaches the coach
