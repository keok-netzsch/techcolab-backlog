"""Auditoria de custo fixo de contexto e de acúmulo — medição determinística, sem LLM.

Existe porque a primeira auditoria (2026-08-31) custou ~15 chamadas de ferramenta com o
modelo contando arquivos à mão, errou três números a favor da própria tese e generalizou
uma sessão como se fosse o conjunto. Medir tem que ser código; o modelo só lê o delta.

O que mede (tudo em disco, nada de rede):
  - custo fixo de contexto: os arquivos que entram em TODA sessão, em chars
  - índice de memória: linhas e quantas passam do limite de 150 chars
  - skills pessoais e comandos: quantidade e peso das descriptions
  - plugins: instalados e habilitados
  - transcripts e snapshots: quantidade e MB
  - rotinas agendadas: quantas pastas em scheduled-tasks (a lista viva vem da tool
    list_scheduled_tasks, que este script não alcança; a rotina compara os dois)

Grava dois arquivos no vault, ambos derivados e refeitos do zero:
  _reports/Token-Audit.md            o relatório desta rodada, com o delta da anterior
  _reports/token-audit-history.jsonl uma linha por rodada, para o delta e para tendência

Uso:
  python scripts/audit_tokens.py            # mede, grava, imprime o resumo
  python scripts/audit_tokens.py --json     # só o JSON da rodada, sem gravar
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

HOME = Path.home()
VAULT = Path(os.environ.get(
    "TECHCOLAB_VAULT_ROOT",
    str(HOME / "OneDrive - NETZSCH" / "Documents" / "TechColab_D&A_KO"),
))
CLAUDE = HOME / ".claude"
MEMORY_DIR = CLAUDE / "projects" / "C--Users-Kelvin-okuda" / "memory"
REPORTS = VAULT / "_reports"

# Os arquivos que o Claude Code carrega sozinho. "sempre" = toda sessão; os outros,
# quando a sessão nasce naquela pasta.
CONTEXT_FILES = {
    "~/.claude/CLAUDE.md":          (CLAUDE / "CLAUDE.md", "sempre"),
    "~/CLAUDE.md":                  (HOME / "CLAUDE.md", "sempre"),
    "MEMORY.md":                    (MEMORY_DIR / "MEMORY.md", "sempre"),
    "techcolab-backlog/CLAUDE.md":  (HOME / "techcolab-backlog" / "CLAUDE.md", "repo"),
    "vault/_CLAUDE.md":             (VAULT / "_CLAUDE.md", "vault"),
}
INDEX_LINE_LIMIT = 150      # limite do consolidate-memory para linha de índice
GROWTH_ALERT = 0.10         # 10% a mais que a rodada anterior = destaque


def _chars(p: Path) -> int:
    try:
        return len(p.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return 0


def _description_chars(md_files: list[str]) -> tuple[int, int]:
    n = total = 0
    for f in md_files:
        try:
            head = open(f, encoding="utf-8", errors="replace").read(4000)
        except OSError:
            continue
        m = re.search(r"^description:\s*(.+?)(?=^\w+:|^---)", head, re.S | re.M)
        if m:
            n += 1
            total += len(" ".join(m.group(1).split()))
    return n, total


def measure() -> dict:
    ctx = {}
    for label, (p, scope) in CONTEXT_FILES.items():
        ctx[label] = {"chars": _chars(p), "scope": scope}
    sempre = sum(v["chars"] for v in ctx.values() if v["scope"] == "sempre")
    repo = sempre + ctx["techcolab-backlog/CLAUDE.md"]["chars"]
    vault = sempre + ctx["vault/_CLAUDE.md"]["chars"]

    mem_index = MEMORY_DIR / "MEMORY.md"
    try:
        lines = mem_index.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        lines = []
    entries = [l for l in lines if l.startswith("- [")]
    long_lines = [l for l in entries if len(l) > INDEX_LINE_LIMIT]

    skills = glob.glob(str(CLAUDE / "skills" / "*" / "SKILL.md"))
    sk_n, sk_chars = _description_chars(skills)
    commands = glob.glob(str(CLAUDE / "commands" / "*.md"))
    cmd_n, cmd_chars = _description_chars(commands)

    plugins_total = plugins_enabled = 0
    reg = CLAUDE / "plugins" / "installed_plugins.json"
    if reg.exists():
        try:
            d = json.load(open(reg, encoding="utf-8"))
            plugins_total = len(d.get("plugins", {}))
        except (OSError, ValueError):
            pass
    # habilitado/desabilitado vive no settings; sem ele, assume-se total
    st = CLAUDE / "settings.json"
    try:
        s = json.load(open(st, encoding="utf-8"))
        ep = s.get("enabledPlugins") or {}
        plugins_enabled = sum(1 for v in ep.values() if v) if ep else plugins_total
    except (OSError, ValueError):
        plugins_enabled = plugins_total

    proj = CLAUDE / "projects" / "C--Users-Kelvin-okuda"
    transcripts = list(proj.glob("*.jsonl")) if proj.exists() else []
    t_mb = round(sum(p.stat().st_size for p in transcripts) / 1024 / 1024, 1)
    snaps = list((CLAUDE / "shell-snapshots").glob("*")) if (CLAUDE / "shell-snapshots").exists() else []

    routines_dirs = [p for p in (CLAUDE / "scheduled-tasks").glob("*/") if (p / "SKILL.md").exists()]

    return {
        "date": date.today().isoformat(),
        "context": ctx,
        "context_total": {"sempre": sempre, "sessao_no_repo": repo, "sessao_no_vault": vault},
        "memory_index": {"entries": len(entries), "long_lines": len(long_lines),
                         "chars": ctx["MEMORY.md"]["chars"]},
        "skills": {"count": sk_n, "description_chars": sk_chars},
        "commands": {"count": cmd_n, "description_chars": cmd_chars},
        "plugins": {"installed": plugins_total, "enabled": plugins_enabled},
        "transcripts": {"count": len(transcripts), "mb": t_mb},
        "shell_snapshots": {"count": len(snaps)},
        "routine_dirs": {"count": len(routines_dirs)},
    }


def _flat(m: dict) -> dict[str, float]:
    """As métricas que se comparam semana a semana, achatadas."""
    return {
        "contexto sempre (chars)": m["context_total"]["sempre"],
        "contexto no repo (chars)": m["context_total"]["sessao_no_repo"],
        "contexto no vault (chars)": m["context_total"]["sessao_no_vault"],
        "MEMORY.md linhas": m["memory_index"]["entries"],
        "MEMORY.md linhas >150": m["memory_index"]["long_lines"],
        "skills pessoais": m["skills"]["count"],
        "skills: chars de description": m["skills"]["description_chars"],
        "comandos": m["commands"]["count"],
        "comandos: chars de description": m["commands"]["description_chars"],
        "plugins instalados": m["plugins"]["installed"],
        "transcripts": m["transcripts"]["count"],
        "transcripts (MB)": m["transcripts"]["mb"],
        "pastas de rotina em scheduled-tasks": m["routine_dirs"]["count"],
    }


def load_previous() -> dict | None:
    h = REPORTS / "token-audit-history.jsonl"
    if not h.exists():
        return None
    last = None
    for line in h.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                last = json.loads(line)
            except ValueError:
                continue
    return last


def render(m: dict, prev: dict | None) -> tuple[str, list[str]]:
    now, before = _flat(m), (_flat(prev) if prev else {})
    grew = []
    rows = []
    for k, v in now.items():
        pv = before.get(k)
        if pv is None:
            delta = "—"
        else:
            diff = v - pv
            if isinstance(v, float) or isinstance(pv, float):
                delta = f"{diff:+.1f}"
            else:
                delta = f"{int(diff):+d}"
            if pv and diff / pv > GROWTH_ALERT:
                grew.append(f"{k}: {pv} → {v} ({delta})")
        vs = f"{v:.1f}" if isinstance(v, float) else str(v)
        ps = ("—" if pv is None else (f"{pv:.1f}" if isinstance(pv, float) else str(pv)))
        rows.append(f"| {k} | {vs} | {ps} | {delta} |")

    tok = lambda c: f"~{round(c / 4 / 1000, 1)}k"
    ct = m["context_total"]
    prev_date = prev["date"] if prev else "nenhuma"
    out = [
        "# Token audit",
        "",
        f"Medido em {m['date']} por `scripts/audit_tokens.py`. Rodada anterior: {prev_date}.",
        "Arquivo gerado do zero a cada rodada; o histórico está em `token-audit-history.jsonl`.",
        "",
        "## Custo fixo de contexto por sessão",
        "",
        f"- sempre: {ct['sempre']:,} chars ({tok(ct['sempre'])} tokens)",
        f"- sessão no repo: {ct['sessao_no_repo']:,} chars ({tok(ct['sessao_no_repo'])} tokens)",
        f"- sessão no vault: {ct['sessao_no_vault']:,} chars ({tok(ct['sessao_no_vault'])} tokens)",
        "",
        "| Arquivo | Chars | Quando carrega |",
        "|---|---:|---|",
    ]
    for label, v in m["context"].items():
        out.append(f"| `{label}` | {v['chars']:,} | {v['scope']} |")
    out += ["", "## Todas as métricas, contra a rodada anterior", "",
            "| Métrica | Agora | Anterior | Delta |", "|---|---:|---:|---:|"] + rows
    out += ["", "## O que cresceu mais de 10%", ""]
    out += [f"- {g}" for g in grew] if grew else ["- nada"]
    out += ["", "## Fora do alcance deste script", "",
            "- rotinas agendadas **vivas**: `list_scheduled_tasks` (a pasta em disco sobrevive ao delete)",
            "- conectores da conta: `claude mcp list` (health check de rede, lento)",
            "- uso real de cada MCP: grep nos transcripts, ver `feedback_medir_uso_no_conjunto_nao_numa_sessao`",
            ""]
    return "\n".join(out), grew


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="imprime o JSON da rodada e não grava")
    args = ap.parse_args(argv)

    m = measure()
    if args.json:
        print(json.dumps(m, ensure_ascii=False, indent=2))
        return 0

    prev = load_previous()
    md, grew = render(m, prev)
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "Token-Audit.md").write_text(md, encoding="utf-8")
    with open(REPORTS / "token-audit-history.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(m, ensure_ascii=False) + "\n")

    ct = m["context_total"]
    print(f"[audit] contexto: sempre {ct['sempre']:,} | repo {ct['sessao_no_repo']:,} | vault {ct['sessao_no_vault']:,} chars")
    print(f"[audit] MEMORY.md {m['memory_index']['entries']} linhas ({m['memory_index']['long_lines']} >150)")
    print(f"[audit] skills {m['skills']['count']} / comandos {m['commands']['count']} / plugins {m['plugins']['installed']}")
    print(f"[audit] transcripts {m['transcripts']['count']} ({m['transcripts']['mb']} MB) / rotinas em disco {m['routine_dirs']['count']}")
    if grew:
        print("[audit] CRESCEU >10%: " + "; ".join(grew))
    else:
        print("[audit] nada cresceu mais de 10%" + (" (primeira rodada, sem base)" if not prev else ""))
    print(f"[audit] {REPORTS / 'Token-Audit.md'}")
    return 2 if grew else 0


if __name__ == "__main__":
    sys.exit(main())
