from __future__ import annotations

import json

import pytest

from scripts import da_intake


def _payload(tmp_path, **overrides):
    payload = {
        "author": "Ana Leite",
        "kind": "decision",
        "title": "Acesso PBI por grupo",
        "summary": "O acesso passa a usar um grupo dedicado.",
        "body": "## Decision\n\nUse the dedicated group from October.",
        "proposed_target": "Projects/OKR 05 - Governanca de Acesso PBI",
        "sensitivity": "none",
        "source": "Claude Code conversation | 2026-09-10",
        "tags": ["okr", "power-bi"],
    }
    payload.update(overrides)
    path = tmp_path / "payload.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_submit_creates_immutable_submission(tmp_path, monkeypatch):
    root = tmp_path / "central"
    root.mkdir()
    monkeypatch.setenv("DA_CENTRAL_VAULT", str(root))

    created = da_intake.submit(str(_payload(tmp_path)))

    assert created.is_file()
    text = created.read_text(encoding="utf-8")
    assert "status: pending-review" in text
    assert "author: Ana Leite" in text
    assert "Projects/OKR 05 - Governanca de Acesso PBI" in text


def test_submit_refuses_to_guess_shared_path(tmp_path, monkeypatch):
    monkeypatch.delenv("DA_CENTRAL_VAULT", raising=False)

    with pytest.raises(da_intake.IntakeError, match="DA_CENTRAL_VAULT"):
        da_intake.submit(str(_payload(tmp_path)))


def test_publish_creates_final_note_and_receipt_without_mutating_submission(tmp_path, monkeypatch):
    root = tmp_path / "central"
    root.mkdir()
    monkeypatch.setenv("DA_CENTRAL_VAULT", str(root))
    submission = da_intake.submit(str(_payload(tmp_path)))
    original = submission.read_text(encoding="utf-8")
    publish = {
        "submission": submission.relative_to(root).as_posix(),
        "approver": "Kelvin Okuda",
        "target": "Projects/OKR 05 - Governanca de Acesso PBI",
        "filename": "2026-09-10 - Acesso PBI por grupo.md",
        "published_content": "---\ndate: 2026-09-10\ntype: decision\ntags: [okr]\nai-first: true\nsource: Intake\n---\n\n# Decision\n",
    }
    publish_path = tmp_path / "publish.json"
    publish_path.write_text(json.dumps(publish), encoding="utf-8")

    final, receipt = da_intake.publish(str(publish_path))

    assert final.is_file()
    assert receipt.is_file()
    assert submission.read_text(encoding="utf-8") == original


def test_publish_refuses_path_escape(tmp_path, monkeypatch):
    root = tmp_path / "central"
    root.mkdir()
    monkeypatch.setenv("DA_CENTRAL_VAULT", str(root))
    submission = da_intake.submit(str(_payload(tmp_path)))
    publish = {
        "submission": submission.relative_to(root).as_posix(),
        "approver": "Kelvin Okuda",
        "target": "../outside",
        "filename": "bad.md",
        "published_content": "test",
    }
    publish_path = tmp_path / "publish.json"
    publish_path.write_text(json.dumps(publish), encoding="utf-8")

    with pytest.raises(da_intake.IntakeError, match="Target path"):
        da_intake.publish(str(publish_path))
