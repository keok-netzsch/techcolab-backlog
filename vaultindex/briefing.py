"""
vaultindex/briefing.py — what a session needs at the start, with zero LLM.

Assembled from things that already exist: the last session log (open threads, next-session
context, unchecked action items), the ledger of what waits for Kelvin, notes touched in the
last days, decisions of the last month and backlog items that moved. Nothing here writes;
nothing here guesses. Sensitive notes stay out unless asked, same as `search`.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from vaultindex.db import connect_ro, default_root, meta_value, stale_chunks

SECTION_ALIASES = {
    "open_threads": ("open threads", "threads abertos", "threads abertas", "fios abertos", "pendências", "pendencias"),
    "next_session_context": ("next session context", "contexto para a próxima", "contexto para a proxima", "próxima sessão", "proxima sessao"),
    "action_items": ("action items", "itens de ação", "itens de acao", "ações", "acoes"),
}
SECTION_CAP = 2000
_H1_RE = re.compile(r"^# .+$", re.M)
_H2_RE = re.compile(r"^## +(.+?)\s*$", re.M)
_UNCHECKED_RE = re.compile(r"^\s*- \[ \] .+$", re.M)


def sessions_dir(root: Path) -> Path:
    return Path(root) / "AI" / "sessions"


def latest_session_file(root: Path) -> Path | None:
    d = sessions_dir(root)
    if not d.is_dir():
        return None
    files = sorted((p for p in d.glob("*.md") if re.match(r"\d{4}-\d{2}-\d{2}", p.name)), key=lambda p: p.name)
    return files[-1] if files else None


def _last_block(text: str) -> str:
    """A day's file can hold several `# Session — …` blocks; the last one is the freshest."""
    starts = [m.start() for m in _H1_RE.finditer(text)]
    return text[starts[-1] :] if starts else text


def extract_sections(text: str) -> dict[str, str]:
    block = _last_block(text)
    heads = list(_H2_RE.finditer(block))
    found: dict[str, str] = {}
    for i, m in enumerate(heads):
        title = m.group(1).lower()
        body = block[m.end() : heads[i + 1].start() if i + 1 < len(heads) else len(block)].strip()
        for key, aliases in SECTION_ALIASES.items():
            if key not in found and any(a in title for a in aliases):
                if key == "action_items":
                    body = "\n".join(_UNCHECKED_RE.findall(body)) or "(nenhum em aberto)"
                found[key] = body[:SECTION_CAP] + (" …" if len(body) > SECTION_CAP else "")
    return found


def _pending_via_cli(repo_root: Path) -> dict:
    """Open ledger items through the CLI that owns them (agent/pending.py), never by reading its file."""
    script = repo_root / "agent" / "pending.py"
    try:
        r = subprocess.run(
            [sys.executable, str(script), "list", "--json"], capture_output=True, text=True, timeout=60, cwd=str(repo_root)
        )
        if r.returncode != 0:
            return {"error": f"pending.py saiu com {r.returncode}: {r.stderr.strip()[-300:]}"}
        data = json.loads(r.stdout or "[]")
        items = data if isinstance(data, list) else data.get("items") or data.get("pendencias") or []
        return {"open": len(items), "items": items[:8]}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def briefing(
    *,
    root: Path | None = None,
    index_dir: Path | None = None,
    days: int = 7,
    include_sensitive: bool = False,
    pending_loader=None,
    repo_root: Path | None = None,
    today: date | None = None,
) -> dict:
    root = Path(root or default_root())
    today = today or date.today()
    repo_root = Path(repo_root or Path(__file__).resolve().parents[1])
    out: dict = {"generated_at": datetime.now().isoformat(timespec="seconds"), "root": str(root), "days": days}

    sess = latest_session_file(root)
    if sess:
        text = sess.read_text(encoding="utf-8", errors="replace")
        out["last_session"] = {"path": sess.relative_to(root).as_posix(), **extract_sections(text)}
    else:
        out["last_session"] = None

    out["pending"] = (pending_loader or _pending_via_cli)(repo_root)

    con = connect_ro(index_dir)
    try:
        model = meta_value(con, "embedding_model")
        last_build = meta_value(con, "last_build")
        out["index"] = {
            "last_build": last_build,
            "age_seconds": int((datetime.now() - datetime.fromisoformat(last_build)).total_seconds()) if last_build else None,
            "notes": con.execute("SELECT count(*) FROM notes").fetchone()[0],
            "embedding_model": model,
            "embeddings_stale_chunks": stale_chunks(con, model),
        }
        cutoff_ts = (datetime.combine(today, datetime.min.time()) - timedelta(days=days)).timestamp()
        sens = "" if include_sensitive else "AND sensitive = 0"
        out["recent_notes"] = [
            {"path": r["rel_path"], "title": r["title"], "type": r["type"], "date": r["date"]}
            for r in con.execute(
                f"""SELECT rel_path, title, type, date FROM notes
                    WHERE mtime >= ? {sens} AND rel_path NOT LIKE 'Daily/%' AND rel_path NOT LIKE 'AI/sessions/%'
                    ORDER BY mtime DESC LIMIT 20""",
                (cutoff_ts,),
            )
        ]
        since_iso = (today - timedelta(days=30)).isoformat()
        out["recent_decisions"] = [
            {"path": r["rel_path"], "title": r["title"], "date": r["date"]}
            for r in con.execute(
                f"""SELECT rel_path, title, date FROM notes
                    WHERE type IN ('decision', 'adr') AND date >= ? {sens} ORDER BY date DESC LIMIT 15""",
                (since_iso,),
            )
        ]
        out["backlog_moved"] = [
            {"path": r["rel_path"], "title": r["title"]}
            for r in con.execute(
                """SELECT rel_path, title FROM notes
                   WHERE folder LIKE '%backlog items' AND mtime >= ? ORDER BY mtime DESC LIMIT 15""",
                (cutoff_ts,),
            )
        ]
        out["excluded_sensitive"] = not include_sensitive
    finally:
        con.close()
    return out


def render(b: dict) -> str:
    lines = [f"# Briefing · {b['generated_at'][:16]} · últimos {b['days']} dias", ""]
    ls = b.get("last_session")
    if ls:
        lines.append(f"## Última sessão: {ls['path']}")
        for key, label in (("next_session_context", "Contexto"), ("open_threads", "Threads abertos"), ("action_items", "Ações em aberto")):
            if ls.get(key):
                lines += [f"### {label}", ls[key], ""]
    else:
        lines.append("## Última sessão: nenhuma encontrada em AI/sessions/")
    p = b.get("pending") or {}
    if "error" in p:
        lines += ["## Pendências do Kelvin", f"ERRO ao ler o ledger: {p['error']}", ""]
    else:
        lines.append(f"## Pendências do Kelvin: {p.get('open', 0)} abertas")
        for it in p.get("items", []):
            pid = it.get("id") or it.get("codigo") or ""
            lines.append(f"- {pid} {str(it.get('texto') or it.get('text') or '')[:140]}")
        lines.append("")
    lines.append(f"## Decisões dos últimos 30 dias ({len(b.get('recent_decisions', []))})")
    lines += [f"- {d['date']} · {d['title']}  ({d['path']})" for d in b.get("recent_decisions", [])]
    lines.append("")
    lines.append(f"## Notas tocadas nos últimos {b['days']} dias ({len(b.get('recent_notes', []))}, fora Daily/ e sessões)")
    lines += [f"- [{n['type'] or 'sem type'}] {n['title']}  ({n['path']})" for n in b.get("recent_notes", [])]
    lines.append("")
    if b.get("backlog_moved"):
        lines.append(f"## Backlog que mexeu ({len(b['backlog_moved'])})")
        lines += [f"- {n['title']}  ({n['path']})" for n in b["backlog_moved"]]
        lines.append("")
    ix = b.get("index", {})
    lines.append(
        f"índice: {ix.get('notes')} notas · build há {ix.get('age_seconds')}s · modelo {ix.get('embedding_model')} · "
        f"{ix.get('embeddings_stale_chunks')} chunks sem vetor" + (" · sensível fora" if b.get("excluded_sensitive") else "")
    )
    return "\n".join(lines)
