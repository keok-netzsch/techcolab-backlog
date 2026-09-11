"""Immutable intake and publication for the D&A central vault.

Claude Code is the conversation layer; this program is the deterministic write
boundary. It has no model or API-key dependency and only creates new files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ALLOWED_KINDS = {"decision", "status", "lesson", "process", "reference"}
ALLOWED_TARGETS = {"Areas", "Projects", "Resources", "Templates"}


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


def _safe_relative(value: str) -> Path:
    candidate = Path(value)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise IntakeError("Target path must be relative and may not contain '..'.")
    if not candidate.parts or candidate.parts[0] not in ALLOWED_TARGETS:
        raise IntakeError(f"Target path must start with one of: {', '.join(sorted(ALLOWED_TARGETS))}.")
    return candidate


def _safe_relative_intake(value: str) -> Path:
    candidate = Path(value)
    if candidate.is_absolute() or ".." in candidate.parts or not candidate.parts or candidate.parts[0] != "Intake":
        raise IntakeError("submission must be a relative path inside Intake/.")
    return candidate


def _exclusive_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
    except FileExistsError as exc:
        raise IntakeError(f"Refusing to overwrite an existing file: {path}") from exc


def _submission_markdown(payload: dict[str, Any], submission_id: str, now: datetime) -> str:
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
    source = _required(payload, "source")
    tags = payload.get("tags", [])
    if not isinstance(tags, list) or not all(isinstance(item, str) for item in tags):
        raise IntakeError("tags must be a list of strings.")
    tag_lines = "\n".join(f"  - {item.strip()}" for item in tags if item.strip()) or "  - da-intake"
    return f"""---
date: {now.date().isoformat()}
type: da-submission
status: pending-review
submission_id: {submission_id}
author: {author}
kind: {kind}
proposed_target: {target.as_posix()}
sensitivity: {sensitivity}
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
    now = datetime.now(UTC)
    title = _required(payload, "title")
    author = _required(payload, "author")
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    digest = hashlib.sha256(f"{author}|{title}|{now.isoformat()}".encode()).hexdigest()[:10]
    submission_id = f"DAI-{stamp}-{digest}"
    content = _submission_markdown(payload, submission_id, now)
    path = root / "Intake" / now.strftime("%Y-%m") / f"{stamp}-{_slug(author)}-{_slug(title)}.md"
    _exclusive_write(path, content)
    return path


def publish(payload_path: str) -> tuple[Path, Path]:
    root = _central_root()
    payload = _read_json(payload_path)
    submission_rel = _safe_relative_intake(_required(payload, "submission"))
    submission_path = root / submission_rel
    if not submission_path.is_file():
        raise IntakeError(f"Submission does not exist: {submission_rel.as_posix()}")
    published_content = _required(payload, "published_content")
    approver = _required(payload, "approver")
    target = _safe_relative(_required(payload, "target"))
    filename = _required(payload, "filename")
    if Path(filename).name != filename or not filename.endswith(".md"):
        raise IntakeError("filename must be a plain .md filename, not a path.")
    now = datetime.now(UTC)
    final_path = root / target / filename
    _exclusive_write(final_path, published_content)
    digest = hashlib.sha256(published_content.encode("utf-8")).hexdigest()
    receipt = root / "Intake" / "Receipts" / f"{now.strftime('%Y%m%dT%H%M%SZ')}-{Path(filename).stem}.md"
    receipt_content = f"""---
date: {now.date().isoformat()}
type: da-publication-receipt
submission: {submission_rel.as_posix()}
published: {final_path.relative_to(root).as_posix()}
approver: {approver}
content_sha256: {digest}
ai-first: true
---

# Publication receipt

> Immutable receipt for a publication created through the D&A intake boundary.
"""
    _exclusive_write(receipt, receipt_content)
    return final_path, receipt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Immutable D&A central-vault intake")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("submit", "publish"):
        command = sub.add_parser(name)
        command.add_argument("--payload", required=True, help="UTF-8 JSON payload path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "submit":
            print(submit(args.payload))
        else:
            final_path, receipt = publish(args.payload)
            print(json.dumps({"published": str(final_path), "receipt": str(receipt)}))
    except IntakeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
