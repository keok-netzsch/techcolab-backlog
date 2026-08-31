# Corpo do lembrete diario de compromissos (perfil todo-reminder).
#
# Regenera o Action-Dashboard (varre o vault por '- [ ] (Dono) texto @data')
# e escreve na saida SO o que exige atencao hoje: vencidos e vencendo hoje,
# mais a contagem de oportunidades aguardando curadoria no backlog.
# Saida vazia = lembrete nao aparece (lembrete que toca em dia vazio para de
# ser lido - mesma regra dos outros perfis).
#
# Este script NAO decide nada e NAO usa LLM: e leitura do que a rotina das
# 09:00 extraiu das conversas para o vault e para o BacklogStore.

$ErrorActionPreference = "SilentlyContinue"
$repo = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent

$py = @'
import json, os, sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.join(os.environ["TOOLKIT_REPO"], "call-recorder"))
sys.path.insert(0, os.environ["TOOLKIT_REPO"])
import process

root = Path(process.VAULT)
tasks = process._dedup_tasks(process._collect_open_tasks(root, process.DASHBOARD_FILE))
today = datetime.now().date()

def d(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None

overdue = [t for t in tasks if d(t["due"]) and d(t["due"]) < today]
due_today = [t for t in tasks if d(t["due"]) == today]

lines = []
if overdue:
    lines.append(f"VENCIDOS ({len(overdue)}):")
    for t in overdue[:6]:
        dono = f"({t['owner']}) " if t["owner"] else ""
        lines.append(f"  - {dono}{t['text'][:70]}  @{t['due']}")
    if len(overdue) > 6:
        lines.append(f"  ... e mais {len(overdue) - 6}")
if due_today:
    lines.append(f"VENCEM HOJE ({len(due_today)}):")
    for t in due_today[:6]:
        dono = f"({t['owner']}) " if t["owner"] else ""
        lines.append(f"  - {dono}{t['text'][:70]}")

try:
    from backlog.store import BacklogStore
    # startswith ASCII de proposito: este .ps1 e lido como ANSI pelo PS 5.1 e
    # um acento no literal chegaria corrompido ao Python - o filtro nunca
    # casaria e a curadoria sumiria do lembrete em silencio.
    curadoria = [i for i in BacklogStore().load_all() if i.status.startswith("em an")]
    if curadoria:
        lines.append(f"CURADORIA: {len(curadoria)} oportunidade(s) aguardando "
                     f"sua decisao no backlog (status 'em analise').")
except Exception:
    pass

if lines:
    lines.append("")
    lines.append("Detalhe completo: Action-Dashboard.md no vault.")
    # Regenera o dashboard para o detalhe estar fresco quando ele abrir.
    # stdout capturado: o print interno do cmd_dashboard viraria a primeira
    # linha da janela do lembrete.
    try:
        import contextlib, io as _io
        with contextlib.redirect_stdout(_io.StringIO()):
            process.cmd_dashboard()
    except Exception:
        pass
    print("\n".join(lines))
'@

$env:TOOLKIT_REPO = $repo
$env:PYTHONIOENCODING = "utf-8"
$out = $py | & python - 2>$null
if ($out) { $out }
