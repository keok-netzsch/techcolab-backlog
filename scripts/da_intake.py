"""Immutable intake and publication for the D&A central vault.

Claude Code is the conversation layer; this program is the deterministic write
boundary. It has no model or API-key dependency and only creates new files.

Three things this program refuses to do, because the folder it writes into is a
SharePoint folder the whole D&A team reads:

    sensitive content   the same pattern groups the nightly
                        `vault-central-sensitive-scan.ps1` uses, applied at write
                        time instead of ten hours later
    invented folders    publishing into a project folder that does not exist
                        creates a parallel home for knowledge nobody will find
    silent queues       a submission always ends in a decision file, so a returned
                        or rejected item leaves the queue instead of resurfacing
                        at every review

Python 3.8 is the floor. This file is handed to teammates as a zip and runs on
whatever interpreter their machine has, so nothing here may depend on a recent
one. `tests/test_da_intake.py` enforces that floor mechanically, because a comment
saying so did not survive a single `ruff --fix`.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ALLOWED_KINDS = {"decision", "status", "lesson", "process", "reference"}
ALLOWED_TARGETS = {"Areas", "Projects", "Resources", "Templates"}
ALLOWED_DECISIONS = {"return", "reject"}

# Ported from scripts/vault-central-sensitive-scan.ps1 (groups comp, money, hr,
# secret, confid), which reads the vault at 18:25 every day and reports what it
# finds. Reporting is the wrong verb for a shared folder: by the time it runs, the
# content has been on SharePoint for hours and OneDrive has already pushed it to
# everyone. The same rule belongs here, where the write can still be refused.
#
# Two widenings over what that scan had on 2026-09-11, both found by testing this
# gate rather than by reading it:
#
#   sal[aá]ri   the old `sal(a|á)rio|salar(y|ies)` missed `salarial` and
#               `salariais`, and "banda salarial" is how the subject is actually
#               written in Portuguese. A submission about salary bands passed clean.
#   personal    PLR, medical leave, citizenship and CPF, which are the subjects
#               that piled up in the Inbox triage of 2026-09-10 and the ones a
#               teammate is most likely to paste in by accident rather than intent.
#
# The .ps1 carries the same widening; the two lists are meant to stay in step.
SENSITIVE_PATTERNS = [
    ("comp", r"sal[aá]ri|salar(y|ies)|remunera|compensation|b(o|ô)nus|\bbonus\b|\bmerit\b|"
             r"m(e|é)rito|\bPLR\b|reajuste|stock option|\bequity\b"),
    ("money", r"R\$ ?\d|€ ?\d|\bEUR ?\d{3}"),
    ("hr", r"avalia(c|ç)(a|ã)o de desempenho|performance review|performance evaluation|"
           r"devolutiva|\bPDI\b|\b9[ -]?box\b|promo(c|ç)(a|ã)o\b|\bpromotion\b|headcount|"
           r"demiss|dismissal|\btermination\b|desligamento|advert(e|ê)ncia|senioridade|"
           r"plano de carreira"),
    ("personal", r"atestado|consulta m(e|é)dica|licen(c|ç)a m(e|é)dica|afastamento|"
                 r"\bCPF\b|\bcidadania\b|processo judicial"),
    ("secret", r"api[_ -]?key\s*[:=]|password\s*[:=]|senha\s*[:=]|\bsk-[A-Za-z0-9]{10,}|"
               r"ghp_[A-Za-z0-9]{10,}|xoxb-[A-Za-z0-9-]{10,}|Bearer [A-Za-z0-9._\-]{15,}|"
               r"AKIA[0-9A-Z]{16}"),
    ("confid", r"n(a|ã)o verbalizad|ainda n(a|ã)o (foi )?anunciad|n(a|ã)o compartilhar|"
               r"do not share|internal only"),
]

_COMPILED = [(name, re.compile(pattern, re.IGNORECASE)) for name, pattern in SENSITIVE_PATTERNS]

# Two tiers, because one tier gets this gate switched off.
#
# HARD is a person's money, health, identity, or a credential. Nothing in D&A work
# needs those words in a shared folder, so there is no override.
#
# SOFT is where the vocabulary collides with the team's own work: `promotion` is a
# deployment-pipeline stage and `headcount` is a column in the QBR dashboard spec,
# and both already sit in the vault written by people meaning machines. Measured on
# 2026-09-11 across the 182 notes in the central vault, the SOFT groups fire on 4
# files and every one is about a system. A gate that refuses those with no way
# through is a gate that gets worked around in week one, so the author confirms
# once and the confirmation is recorded for the reviewer to see.
HARD_GROUPS = {"comp", "secret", "personal"}
SOFT_GROUPS = {"hr", "money", "confid"}


class IntakeError(ValueError):
    """A user-correctable intake error."""


def _central_root() -> Path:
    raw = os.environ.get("DA_CENTRAL_VAULT")
    if not raw:
        raise IntakeError("DA_CENTRAL_VAULT is not set; refusing to guess a shared-vault path.")
    root = Path(raw).expanduser().resolve()
    if not root.is_dir():
        raise IntakeError(f"DA_CENTRAL_VAULT does not exist or is not a folder: {root}")
    return root


def _read_json(path: str) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IntakeError(f"Cannot read payload JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise IntakeError("Payload must be a JSON object.")
    return value


def _required(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise IntakeError(f"Payload field '{field}' is required.")
    return value.strip()


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:48] or "submission"


def scan_sensitive(text: str) -> list[tuple[str, str]]:
    """Every (group, offending line) in the text. Empty means clean.

    Returns the line and not just the group, so a refusal can tell the author what
    to reword. A refusal that names only a category sends them guessing.
    """
    hits: list[tuple[str, str]] = []
    seen = set()
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or len(stripped) > 2000:
            continue
        for name, rx in _COMPILED:
            match = rx.search(stripped)
            if not match:
                continue
            key = (name, match.group(0).lower())
            if key in seen:
                continue
            seen.add(key)
            hits.append((name, stripped[:160]))
    return hits


def _refuse_if_sensitive(text: str, what: str, confirmed_not_personal: bool = False) -> list[str]:
    """Refuse on a HARD match always, on a SOFT match unless the author confirmed.

    Returns the SOFT groups that were let through, so the submission records them
    and the reviewer sees what was waved past instead of trusting it silently.
    """
    hits = scan_sensitive(text)
    hard = [(name, line) for name, line in hits if name in HARD_GROUPS]
    soft = [(name, line) for name, line in hits if name in SOFT_GROUPS]
    if hard:
        lines = [f"Refusing to write {what}: it names a person's pay, health, "
                 "identity or a credential."]
        lines += [f"  [{name}] {line}" for name, line in hard[:6]]
        lines.append("The central vault is a SharePoint folder the whole D&A team reads.")
        lines.append("Reword it or keep it in a personal vault. There is no override for these.")
        raise IntakeError("\n".join(lines))
    if soft and not confirmed_not_personal:
        lines = [f"Hold on. {what.capitalize()} uses words that usually mean people:"]
        lines += [f"  [{name}] {line}" for name, line in soft[:6]]
        lines.append("If these are about systems and not about a person (pipeline promotion,")
        lines.append('a headcount column, a policy), add "confirm_not_personal": true to the')
        lines.append("payload. The confirmation is recorded for the reviewer.")
        raise IntakeError("\n".join(lines))
    return sorted({name for name, _line in soft})


def _safe_relative(value: str) -> Path:
    candidate = Path(value)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise IntakeError("Target path must be relative and may not contain '..'.")
    if not candidate.parts or candidate.parts[0] not in ALLOWED_TARGETS:
        raise IntakeError("Target path must start with one of: "
                          f"{', '.join(sorted(ALLOWED_TARGETS))}.")
    return candidate


def _safe_relative_intake(value: str) -> Path:
    candidate = Path(value)
    if candidate.is_absolute() or ".." in candidate.parts or not candidate.parts \
            or candidate.parts[0] != "Intake":
        raise IntakeError("submission must be a relative path inside Intake/.")
    return candidate


def _existing_targets(root: Path) -> list[str]:
    out = []
    for top in sorted(ALLOWED_TARGETS):
        base = root / top
        if not base.is_dir():
            continue
        out.append(top)
        for child in sorted(base.iterdir()):
            if child.is_dir() and not child.name.startswith("."):
                out.append(f"{top}/{child.name}")
    return out


def _check_target_exists(root: Path, target: Path, allow_new: bool) -> None:
    """A publish target must already exist, unless the reviewer says otherwise.

    `Projects/OKR 5 - Governanca de acesso PowerBI` and
    `Projects/OKR 05 - Governanca de Acesso PBI` are one letter and one zero apart,
    and only one of them is where the team looks. Creating the other on a typo is
    how a shared vault grows folders nobody reads.
    """
    if allow_new or (root / target).is_dir():
        return
    known = _existing_targets(root)
    close = difflib.get_close_matches(target.as_posix(), known, n=3, cutoff=0.55)
    message = [f"Target folder does not exist: {target.as_posix()}"]
    if close:
        message.append("Did you mean one of these?")
        message += [f"  {item}" for item in close]
    message.append('Pass "allow_new_folder": true only if this folder is genuinely new.')
    raise IntakeError("\n".join(message))


def _exclusive_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
    except FileExistsError as exc:
        raise IntakeError(f"Refusing to overwrite an existing file: {path}") from exc


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _submission_markdown(payload: dict[str, Any], submission_id: str, now: datetime,
                         target_exists: bool) -> str:
    author = _required(payload, "author")
    kind = _required(payload, "kind").lower()
    if kind not in ALLOWED_KINDS:
        raise IntakeError(f"kind must be one of: {', '.join(sorted(ALLOWED_KINDS))}")
    title = _required(payload, "title")
    summary = _required(payload, "summary")
    body = _required(payload, "body")
    target = _safe_relative(_required(payload, "proposed_target"))
    sensitivity = payload.get("sensitivity", "none")
    if sensitivity not in {"none", "possible", "sensitive"}:
        raise IntakeError("sensitivity must be none, possible, or sensitive.")
    if sensitivity == "sensitive":
        raise IntakeError(
            "This submission is declared sensitive, so it does not belong in the central "
            "vault. Keep it in a personal vault, or submit an anonymised version that "
            "carries the lesson without the case.")
    source = _required(payload, "source")
    tags = payload.get("tags", [])
    if not isinstance(tags, list) or not all(isinstance(item, str) for item in tags):
        raise IntakeError("tags must be a list of strings.")
    waved = _refuse_if_sensitive("\n".join([title, summary, body]), "this submission",
                                 bool(payload.get("confirm_not_personal", False)))
    tag_lines = "\n".join(f"  - {item.strip()}" for item in tags if item.strip()) or "  - da-intake"
    exists = "true" if target_exists else "false"
    confirmed = ", ".join(waved) or "n/a"
    return f"""---
date: {now.date().isoformat()}
type: da-submission
status: pending-review
submission_id: {submission_id}
author: {author}
kind: {kind}
proposed_target: {target.as_posix()}
target_exists: {exists}
sensitivity: {sensitivity}
confirmed_not_personal: {confirmed}
source: {source}
tags:
{tag_lines}
ai-first: true
---

# Submission — {title}

> This is an immutable D&A central-vault submission. It is not an official
> published record until an authorized reviewer approves it through `/da-revisar`.

## Summary

{summary}

## Proposed content

{body}
"""


def submit(payload_path: str) -> Path:
    root = _central_root()
    payload = _read_json(payload_path)
    now = _now()
    title = _required(payload, "title")
    author = _required(payload, "author")
    target = _safe_relative(_required(payload, "proposed_target"))
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    digest = hashlib.sha256(f"{author}|{title}|{now.isoformat()}".encode()).hexdigest()[:10]
    submission_id = f"DAI-{stamp}-{digest}"
    content = _submission_markdown(payload, submission_id, now, (root / target).is_dir())
    path = root / "Intake" / now.strftime("%Y-%m") / f"{stamp}-{_slug(author)}-{_slug(title)}.md"
    _exclusive_write(path, content)
    return path


def _decision_path(root: Path, submission_rel: Path) -> Path:
    """One decision file per submission, named after it.

    Named after the submission on purpose: deciding whether an item is still open is
    then a file-existence check, not a scan that parses the frontmatter of every
    receipt. The queue has to stay cheap or the Friday review stops happening.
    """
    return root / "Intake" / "_decisions" / (submission_rel.stem + ".md")


def _load_fields(root: Path, rel: Path) -> dict[str, str]:
    path = root / rel
    if not path.is_file():
        raise IntakeError(f"Submission does not exist: {rel.as_posix()}")
    fields: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[:24]:
        match = re.match(r"^([a-z_]+):\s*(.+?)\s*$", line)
        if match:
            fields[match.group(1)] = match.group(2)
    return fields


def publish(payload_path: str) -> tuple[Path, Path]:
    root = _central_root()
    payload = _read_json(payload_path)
    submission_rel = _safe_relative_intake(_required(payload, "submission"))
    fields = _load_fields(root, submission_rel)
    decision = _decision_path(root, submission_rel)
    if decision.exists():
        raise IntakeError("This submission was already decided: "
                          f"{decision.relative_to(root).as_posix()}")
    published_content = _required(payload, "published_content")
    approver = _required(payload, "approver")
    target = _safe_relative(_required(payload, "target"))
    filename = _required(payload, "filename")
    if Path(filename).name != filename or not filename.endswith(".md"):
        raise IntakeError("filename must be a plain .md filename, not a path.")
    _check_target_exists(root, target, bool(payload.get("allow_new_folder", False)))
    _refuse_if_sensitive(published_content, "this published note",
                         bool(payload.get("confirm_not_personal", False)))
    now = _now()
    final_path = root / target / filename
    _exclusive_write(final_path, published_content)
    digest = hashlib.sha256(published_content.encode("utf-8")).hexdigest()
    author = fields.get("author", "unknown")
    published_rel = final_path.relative_to(root).as_posix()
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    receipt = root / "Intake" / "Receipts" / f"{stamp}-{Path(filename).stem}.md"
    _exclusive_write(receipt, f"""---
date: {now.date().isoformat()}
type: da-publication-receipt
submission: {submission_rel.as_posix()}
author: {author}
published: {published_rel}
approver: {approver}
content_sha256: {digest}
ai-first: true
---

# Publication receipt

> Immutable receipt for a publication created through the D&A intake boundary.
""")
    _exclusive_write(decision, f"""---
date: {now.date().isoformat()}
type: da-decision
decision: publish
submission: {submission_rel.as_posix()}
author: {author}
approver: {approver}
published: {published_rel}
ai-first: true
---

Published. Receipt: {receipt.relative_to(root).as_posix()}
""")
    return final_path, receipt


def resolve(payload_path: str) -> Path:
    """Return or reject a submission, so that it leaves the queue.

    Without this the review had one exit. A submission the reviewer sent back kept
    `status: pending-review` forever and never got a receipt, so the listing rule in
    the skill showed it again at every review, for good.
    """
    root = _central_root()
    payload = _read_json(payload_path)
    submission_rel = _safe_relative_intake(_required(payload, "submission"))
    fields = _load_fields(root, submission_rel)
    decision = _required(payload, "decision").lower()
    if decision not in ALLOWED_DECISIONS:
        raise IntakeError(f"decision must be one of: {', '.join(sorted(ALLOWED_DECISIONS))}")
    reason = _required(payload, "reason")
    approver = _required(payload, "approver")
    path = _decision_path(root, submission_rel)
    if path.exists():
        raise IntakeError("This submission was already decided: "
                          f"{path.relative_to(root).as_posix()}")
    now = _now()
    author = fields.get("author", "unknown")
    _exclusive_write(path, f"""---
date: {now.date().isoformat()}
type: da-decision
decision: {decision}
submission: {submission_rel.as_posix()}
author: {author}
approver: {approver}
ai-first: true
---

{reason}
""")
    return path


def queue(author: str | None = None, include_decided: bool = False) -> list[dict[str, str]]:
    """Submissions and where each one stands.

    Serves the reviewer ("what is waiting for me") and the author ("what happened to
    the thing I sent"), which is one question asked from two sides.
    """
    root = _central_root()
    intake = root / "Intake"
    if not intake.is_dir():
        return []
    out: list[dict[str, str]] = []
    for month in sorted(intake.iterdir()):
        if not month.is_dir() or not re.match(r"^\d{4}-\d{2}$", month.name):
            continue
        for path in sorted(month.glob("*.md")):
            rel = path.relative_to(root)
            fields = _load_fields(root, rel)
            decision_file = _decision_path(root, rel)
            state = "pending"
            approver = ""
            if decision_file.is_file():
                decided = _load_fields(root, decision_file.relative_to(root))
                state = decided.get("decision", "decided")
                approver = decided.get("approver", "")
            if not include_decided and state != "pending":
                continue
            if author and fields.get("author", "").lower() != author.strip().lower():
                continue
            out.append({
                "submission": rel.as_posix(),
                "author": fields.get("author", "unknown"),
                "kind": fields.get("kind", "?"),
                "date": fields.get("date", "?"),
                "proposed_target": fields.get("proposed_target", "?"),
                "target_exists": fields.get("target_exists", "?"),
                "state": state,
                "approver": approver,
            })
    return out


def render_queue(rows: list[dict[str, str]]) -> str:
    if not rows:
        return "Nothing pending. The D&A intake queue is empty."
    lines = [f"{len(rows)} submission(s):", ""]
    for row in rows:
        warn = "" if row["target_exists"] != "false" else "   [target folder does not exist]"
        lines.append(f"- {row['date']}  {row['author']}  ({row['kind']})"
                     f"  -> {row['proposed_target']}{warn}")
        lines.append(f"  {row['submission']}  [{row['state']}]")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Immutable D&A central-vault intake")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("submit", "publish", "resolve"):
        command = sub.add_parser(name)
        command.add_argument("--payload", required=True, help="UTF-8 JSON payload path")
    listing = sub.add_parser("queue")
    listing.add_argument("--author", help="only submissions from this author")
    listing.add_argument("--all", action="store_true", help="include decided submissions")
    listing.add_argument("--json", action="store_true", help="machine-readable output")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "submit":
            print(submit(args.payload))
        elif args.command == "publish":
            final_path, receipt = publish(args.payload)
            print(json.dumps({"published": str(final_path), "receipt": str(receipt)}))
        elif args.command == "resolve":
            print(resolve(args.payload))
        else:
            rows = queue(author=args.author, include_decided=args.all)
            print(json.dumps(rows, ensure_ascii=False, indent=2) if args.json
                  else render_queue(rows))
    except IntakeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
