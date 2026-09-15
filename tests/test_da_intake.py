from __future__ import annotations

import json

import pytest

from scripts import da_intake


@pytest.fixture
def central(tmp_path, monkeypatch):
    root = tmp_path / "central"
    (root / "Projects" / "OKR 05 - Governanca de Acesso PBI").mkdir(parents=True)
    (root / "Resources").mkdir()
    monkeypatch.setenv("DA_CENTRAL_VAULT", str(root))
    return root


def _write(tmp_path, name, data):
    path = tmp_path / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def _payload(tmp_path, **overrides):
    payload = {
        "author": "Ana Leite",
        "kind": "decision",
        "title": "Acesso PBI por grupo",
        "summary": "O acesso passa a usar um grupo dedicado.",
        "body": "## Decision\n\nUse the dedicated group from October.",
        "proposed_target": "Projects/OKR 05 - Governanca de Acesso PBI",
        "sensitivity": "none",
        "source": "Claude Code conversation | 2026-09-11",
        "tags": ["okr", "power-bi"],
    }
    payload.update(overrides)
    return _write(tmp_path, "payload.json", payload)


def _publish_payload(tmp_path, root, submission, **overrides):
    payload = {
        "submission": submission.relative_to(root).as_posix(),
        "approver": "Kelvin Okuda",
        "target": "Projects/OKR 05 - Governanca de Acesso PBI",
        "filename": "2026-09-11 - Acesso PBI por grupo.md",
        "published_content": "---\ndate: 2026-09-11\ntype: decision\ntags: [okr]\n"
                             "ai-first: true\nsource: Intake\n---\n\n# Decision\n",
    }
    payload.update(overrides)
    return _write(tmp_path, "publish.json", payload)


def test_submit_creates_immutable_submission(tmp_path, central):
    created = da_intake.submit(_payload(tmp_path))

    text = created.read_text(encoding="utf-8")
    assert "status: pending-review" in text
    assert "author: Ana Leite" in text
    assert "target_exists: true" in text


def test_submit_keeps_long_titles_distinct_in_one_second(tmp_path, central, monkeypatch):
    fixed_now = da_intake.datetime(2026, 9, 11, 19, 43, 57, tzinfo=da_intake.timezone.utc)
    monkeypatch.setattr(da_intake, "_now", lambda: fixed_now)
    shared_prefix = "Canonical project record synchronization for a long project name " * 2

    first = da_intake.submit(_payload(tmp_path, title=shared_prefix + "Overview"))
    second = da_intake.submit(_payload(tmp_path, title=shared_prefix + "Charter"))

    assert first != second
    assert first.is_file()
    assert second.is_file()


def test_submit_refuses_to_guess_shared_path(tmp_path, monkeypatch):
    monkeypatch.delenv("DA_CENTRAL_VAULT", raising=False)

    with pytest.raises(da_intake.IntakeError, match="DA_CENTRAL_VAULT"):
        da_intake.submit(_payload(tmp_path))


def test_publish_creates_final_note_and_receipt_without_mutating_submission(tmp_path, central):
    submission = da_intake.submit(_payload(tmp_path))
    original = submission.read_text(encoding="utf-8")

    final, receipt = da_intake.publish(_publish_payload(tmp_path, central, submission))

    assert final.is_file()
    assert "author: Ana Leite" in receipt.read_text(encoding="utf-8")
    assert submission.read_text(encoding="utf-8") == original


def test_publish_keeps_receipts_distinct_for_same_filename_in_one_second(tmp_path, central,
                                                                           monkeypatch):
    """A common ``Status.md`` name must not make the second receipt collide."""
    fixed_now = da_intake.datetime(2026, 9, 11, 19, 15, 0, tzinfo=da_intake.timezone.utc)
    monkeypatch.setattr(da_intake, "_now", lambda: fixed_now)
    (central / "Projects" / "Second project").mkdir()

    first = da_intake.submit(_payload(tmp_path, title="First project update"))
    da_intake.publish(_publish_payload(
        tmp_path, central, first, filename="Status.md",
        published_content="# First status\n",
    ))

    second = da_intake.submit(_payload(tmp_path, title="Second project update"))
    _final, second_receipt = da_intake.publish(_publish_payload(
        tmp_path, central, second, target="Projects/Second project", filename="Status.md",
        published_content="# Second status\n",
    ))

    receipts = list((central / "Intake" / "Receipts").glob("*.md"))
    assert len(receipts) == 2
    assert second_receipt.is_file()


def test_publish_refuses_path_escape(tmp_path, central):
    submission = da_intake.submit(_payload(tmp_path))
    payload = _publish_payload(tmp_path, central, submission, target="../outside")

    with pytest.raises(da_intake.IntakeError, match="Target path"):
        da_intake.publish(payload)


# --- the shared folder is a SharePoint folder the whole team reads ------------

@pytest.mark.parametrize("field,text,group", [
    ("title", "Banda salarial do time de engenharia", "comp"),
    ("body", "O reajuste combinado foi de 15%.", "comp"),
    ("body", "Pagamento de PLR sai em marco.", "comp"),
    ("body", "Ela entregou o atestado medico na segunda.", "personal"),
    ("body", "O notebook tinha api_key = sk-abcdefghijklmnop no topo.", "secret"),
])
def test_submit_refuses_personal_money_health_and_credentials(tmp_path, central,
                                                              field, text, group):
    """These have no override, even with confirm_not_personal set."""
    payload = _payload(tmp_path, **{field: text, "confirm_not_personal": True})

    with pytest.raises(da_intake.IntakeError) as exc:
        da_intake.submit(payload)
    assert group in str(exc.value)


def test_salarial_is_caught_even_though_salario_spelling_differs(tmp_path, central):
    """The inherited pattern read `sal(a|a)rio` and let `salarial` through."""
    with pytest.raises(da_intake.IntakeError, match="comp"):
        da_intake.submit(_payload(tmp_path, body="A banda salarial foi revista."))


def test_ambiguous_words_ask_once_then_pass_and_are_recorded(tmp_path, central):
    """`promotion` is a pipeline stage in this team's own vault, not a person."""
    body = "O deployment pipeline promotion roda pelo Azure DevOps."

    with pytest.raises(da_intake.IntakeError, match="confirm_not_personal"):
        da_intake.submit(_payload(tmp_path, body=body))

    created = da_intake.submit(_payload(tmp_path, body=body, confirm_not_personal=True))
    assert "confirmed_not_personal: hr" in created.read_text(encoding="utf-8")


def test_clean_content_records_no_confirmation(tmp_path, central):
    created = da_intake.submit(_payload(tmp_path))
    assert "confirmed_not_personal: n/a" in created.read_text(encoding="utf-8")


def test_declared_sensitive_never_reaches_the_vault(tmp_path, central):
    with pytest.raises(da_intake.IntakeError, match="sensitive"):
        da_intake.submit(_payload(tmp_path, sensitivity="sensitive"))


def test_publish_scans_the_final_note_not_only_the_submission(tmp_path, central):
    submission = da_intake.submit(_payload(tmp_path))
    payload = _publish_payload(tmp_path, central, submission,
                               published_content="Reajuste salarial aprovado.")

    with pytest.raises(da_intake.IntakeError, match="comp"):
        da_intake.publish(payload)


# --- P-139: the two shapes that reached the shared vault on 2026-09-14 ---------
#
# Neither is caught by the compensation VOCABULARY: the variable-pay spreadsheet
# is cited by filename, and a weight arrives as a bare percentage in a table.

@pytest.mark.parametrize("content", [
    "A planilha `VR - DL` (linha do OKR 08, peso 35%) e a fonte da meta.",
    "Este OKR carrega peso real (35% do bonus do Daniel).",
    "| KR | Dono | Piso | Peso |",
    "O KR2 responde por 30% de peso no scorecard.",
])
def test_publish_refuses_variable_pay_and_okr_weights(tmp_path, central, content):
    submission = da_intake.submit(_payload(tmp_path))
    payload = _publish_payload(tmp_path, central, submission, published_content=content)

    with pytest.raises(da_intake.IntakeError, match="comp"):
        da_intake.publish(payload)


@pytest.mark.parametrize("content", [
    "Cobertura de 100% das entregas elegiveis.",
    # Font weight, not bonus weight. The first version of this gate matched a bare
    # `| Peso |` header and pulled both design-system notes out of the shared vault.
    "| Elemento | Tamanho (pt / rem) | Peso | Cor | Notas |",
])
def test_the_gate_catches_weights_not_every_percentage_or_column(tmp_path, central, content):
    submission = da_intake.submit(_payload(tmp_path))
    payload = _publish_payload(tmp_path, central, submission, published_content=content)

    final, _receipt = da_intake.publish(payload)
    assert final.is_file()


# --- a typo must not grow a folder -------------------------------------------

def test_publish_refuses_unknown_folder_and_suggests_the_real_one(tmp_path, central):
    submission = da_intake.submit(_payload(tmp_path))
    payload = _publish_payload(tmp_path, central, submission,
                               target="Projects/OKR 5 - Governanca de acesso PowerBI")

    with pytest.raises(da_intake.IntakeError) as exc:
        da_intake.publish(payload)
    assert "OKR 05 - Governanca de Acesso PBI" in str(exc.value)


def test_publish_allows_a_genuinely_new_folder_when_said_so(tmp_path, central):
    submission = da_intake.submit(_payload(tmp_path))
    payload = _publish_payload(tmp_path, central, submission,
                               target="Projects/BIA99 New Thing", allow_new_folder=True)

    final, _receipt = da_intake.publish(payload)
    assert final.is_file()


def test_submit_records_that_the_proposed_target_is_unknown(tmp_path, central):
    created = da_intake.submit(_payload(tmp_path, proposed_target="Projects/Nao Existe"))
    assert "target_exists: false" in created.read_text(encoding="utf-8")


# --- a decided submission leaves the queue ------------------------------------

def _resolve(tmp_path, root, submission, decision="return"):
    return _write(tmp_path, "resolve.json", {
        "submission": submission.relative_to(root).as_posix(),
        "decision": decision,
        "reason": "Falta dizer quem aprova a excecao.",
        "approver": "Kelvin Okuda",
    })


def test_returned_submission_leaves_the_queue(tmp_path, central):
    submission = da_intake.submit(_payload(tmp_path))
    assert len(da_intake.queue()) == 1

    da_intake.resolve(_resolve(tmp_path, central, submission))

    assert da_intake.queue() == []
    assert da_intake.queue(include_decided=True)[0]["state"] == "return"


def test_published_submission_leaves_the_queue(tmp_path, central):
    submission = da_intake.submit(_payload(tmp_path))
    da_intake.publish(_publish_payload(tmp_path, central, submission))

    assert da_intake.queue() == []
    assert da_intake.queue(include_decided=True)[0]["state"] == "publish"


def test_a_submission_is_decided_once(tmp_path, central):
    submission = da_intake.submit(_payload(tmp_path))
    da_intake.resolve(_resolve(tmp_path, central, submission))

    with pytest.raises(da_intake.IntakeError, match="already decided"):
        da_intake.publish(_publish_payload(tmp_path, central, submission))


def test_resolve_rejects_an_unknown_decision(tmp_path, central):
    submission = da_intake.submit(_payload(tmp_path))

    with pytest.raises(da_intake.IntakeError, match="decision must be"):
        da_intake.resolve(_resolve(tmp_path, central, submission, decision="maybe"))


def test_queue_filters_by_author(tmp_path, central):
    da_intake.submit(_payload(tmp_path))
    da_intake.submit(_payload(tmp_path, author="Pedro Hennig", title="Outro assunto"))

    assert len(da_intake.queue()) == 2
    assert len(da_intake.queue(author="ana leite")) == 1


def test_queue_is_empty_before_anything_is_submitted(central):
    assert da_intake.queue() == []
    assert "Nothing pending" in da_intake.render_queue([])


def test_cli_queue_runs_clean(capsys, central):
    assert da_intake.main(["queue"]) == 0
    assert "Nothing pending" in capsys.readouterr().out


# --- the file ships to machines this repo does not control --------------------

MIN_PYTHON = (3, 8)

# Constructs that work here and fail on an older interpreter. `ruff --fix` put the
# first one back into the file on 2026-09-11 and every test still passed, because
# this machine runs 3.13 and the teammate's might not. A comment does not stop an
# autofixer; this list does.
BANNED = {
    "from datetime import UTC": "datetime.UTC needs 3.11; use timezone.utc",
    "datetime.UTC": "datetime.UTC needs 3.11; use timezone.utc",
    "itertools.batched": "needs 3.12",
    "tomllib": "needs 3.11",
    "ExceptionGroup": "needs 3.11",
}


def _distributed_source():
    from pathlib import Path
    return (Path(da_intake.__file__).read_text(encoding="utf-8"), Path(da_intake.__file__))


def test_distributed_program_parses_on_the_oldest_supported_python():
    import ast

    source, path = _distributed_source()
    ast.parse(source, filename=str(path), feature_version=MIN_PYTHON)


def test_distributed_program_avoids_constructs_newer_than_the_floor():
    source, _path = _distributed_source()
    found = [f"{needle} ({why})" for needle, why in BANNED.items() if needle in source]
    floor = f"{MIN_PYTHON[0]}.{MIN_PYTHON[1]}"
    assert not found, f"scripts/da_intake.py must run on Python {floor}: {'; '.join(found)}"
