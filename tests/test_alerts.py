"""Tests for PDI/OKR Alerts (idea-031): deterministic risk scan of OKR.md / PDI.md.
`today` is injected so overdue detection is stable."""
import sys
from pathlib import Path

CR_DIR = Path(__file__).resolve().parents[1] / "call-recorder"
sys.path.insert(0, str(CR_DIR))

import process  # noqa: E402

TODAY = "2026-07-29"


def test_parse_any_date_both_formats():
    assert process._parse_any_date("Deadline: 2026-06-30").isoformat() == "2026-06-30"
    assert process._parse_any_date("Data de Conclusao: 30/06/2026").isoformat() == "2026-06-30"
    assert process._parse_any_date("no date here") is None


def test_overdue_deadline_iso_format():
    a = process.scan_pdi_okr_alerts("- **Deadline:** 2026-06-30\n", today=TODAY)
    assert len(a) == 1 and a[0]["kind"] == "overdue_deadline"
    assert a[0]["date"] == "2026-06-30"


def test_overdue_deadline_br_format():
    a = process.scan_pdi_okr_alerts("**Data de Conclusão:** 30/06/2026\n", today=TODAY)
    assert any(x["kind"] == "overdue_deadline" and x["date"] == "2026-06-30" for x in a)


def test_future_deadline_does_not_fire():
    a = process.scan_pdi_okr_alerts("- **Deadline:** 2026-12-31\n", today=TODAY)
    assert a == []


def test_completed_section_is_ignored():
    text = ("## Completed Objectives\n\n"
            "| ERP/SAP | 2025-12-31 | ✅ Completed |\n")
    assert process.scan_pdi_okr_alerts(text, today=TODAY) == []


def test_done_marked_line_not_flagged():
    # a past dated line explicitly done must not raise an overdue alert
    a = process.scan_pdi_okr_alerts("- **Deadline:** 2026-06-30 ✅\n", today=TODAY)
    assert all(x["kind"] != "overdue_deadline" for x in a)


def test_explicit_overdue_marker():
    a = process.scan_pdi_okr_alerts("| Alura Python | 2026-03-27 | ⚠️ OVERDUE |\n", today=TODAY)
    assert a[0]["kind"] == "explicit_overdue"


def test_zero_progress_flagged():
    a = process.scan_pdi_okr_alerts("- **Progress:** 0%\n", today=TODAY)
    assert a[0]["kind"] == "zero_progress" and a[0]["date"] is None


def test_zero_progress_prose_does_not_fire():
    # preamble prose "0% progress" (number-first) is not the field -> no alert
    a = process.scan_pdi_okr_alerts(
        "> For future Claude: active objective with 0% progress and overdue actions.\n",
        today=TODAY)
    assert all(x["kind"] != "zero_progress" for x in a)


def test_conclusao_keyword_not_mistaken_for_done():
    # "Conclusão" contains "conclus" but must NOT be treated as the done marker "concluíd"
    a = process.scan_pdi_okr_alerts("**Data de Conclusão:** 30/06/2026\n", today=TODAY)
    assert any(x["kind"] == "overdue_deadline" for x in a)


def test_repeated_blocks_are_deduped():
    row = "| Alura Python | 2026-03-27 | ⚠️ OVERDUE |\n"
    a = process.scan_pdi_okr_alerts(row * 3, today=TODAY)
    assert len(a) == 1


def test_cmd_alerts_person_writes_digest(tmp_path, monkeypatch):
    monkeypatch.setattr(process, "VAULT", str(tmp_path))
    p = tmp_path / "Team" / "Ana-Leite"
    p.mkdir(parents=True)
    (p / "OKR.md").write_text("**Data de Conclusão:** 30/06/2026\n", encoding="utf-8")
    (p / "PDI.md").write_text("- **Progress:** 0%\n- **Deadline:** 2026-05-29\n", encoding="utf-8")

    out = process.cmd_alerts(person_folder="Ana-Leite")

    assert out == str(p / "alerts.md")
    md = (p / "alerts.md").read_text(encoding="utf-8")
    assert "type: pdi-okr-alerts" in md
    assert "## For future Claude" in md
    assert "overdue_deadline" in md
    assert "zero_progress" in md


def test_cmd_alerts_all_writes_rollup(tmp_path, monkeypatch):
    monkeypatch.setattr(process, "VAULT", str(tmp_path))
    for folder in ("Ana-Leite", "Pedro-Klein"):
        d = tmp_path / "Team" / folder
        d.mkdir(parents=True)
        (d / "OKR.md").write_text("- **Deadline:** 2026-05-01\n", encoding="utf-8")
        (d / "PDI.md").write_text("", encoding="utf-8")

    out = process.cmd_alerts()

    assert out == str(tmp_path / "PDI-OKR-Alerts.md")
    roll = Path(out).read_text(encoding="utf-8")
    assert "# PDI/OKR Alerts - Team" in roll
    assert "Ana Leite" in roll and "Pedro Klein" in roll
    assert (tmp_path / "Team" / "Ana-Leite" / "alerts.md").exists()
