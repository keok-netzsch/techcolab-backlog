# Fila de transcricao - tarefa dedicada
#
# Existia dentro de agent/daily_report.py, chamada por run_agent.bat, e nunca
# chegava a rodar: DUAS tarefas apontavam para o mesmo .bat (TechColab Backlog
# Agent as 07:00 e TechColab Daily Agent as 20:00), contrariando a regra do
# proprio CLAUDE.md do repo - "there must be exactly one task pointing at
# run_agent.bat: two of them race on logs\agent-last.log and one ends up
# permanently red, masking real failures".
#
# O efeito pratico media-se em dias: a analise de ideias consumia o limite de 6h
# e o processo morria antes de alcancar a transcricao. Em 2026-08-29 havia 10
# gravacoes paradas em .wav, ~4h de audio, sem que nada indicasse falha.
#
# Separado porque as duas cargas nao tem nada em comum:
#   - relatorio de backlog: leve, util de manha, roda as 07:00
#   - transcricao: Whisper em CPU por horas, precisa da noite e da maquina livre
#
# Amarrar as duas no mesmo .bat fazia a leve atrasar a pesada ate a morte.

$ErrorActionPreference = "Stop"

$base = Join-Path $env:USERPROFILE "techcolab-backlog\call-recorder"
$logs = Join-Path $env:USERPROFILE "techcolab-backlog\logs"
if (-not (Test-Path $logs)) { New-Item -ItemType Directory -Path $logs | Out-Null }

$log = Join-Path $logs "queue-last.log"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

"=== fila iniciada $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===" | Out-File $log -Encoding utf8

try {
    Push-Location $base
    # -u para o log sair em tempo real: sem isso, uma fila que trava por horas
    # deixa o arquivo vazio e nao ha como saber onde ela parou.
    & python -u "process.py" queue 2>&1 | Tee-Object -FilePath $log -Append
    $rc = $LASTEXITCODE
} catch {
    "ERRO: $($_.Exception.Message)" | Out-File $log -Append -Encoding utf8
    $rc = 1
} finally {
    Pop-Location
}

"=== fila terminada $(Get-Date -Format 'HH:mm:ss') rc=$rc ===" | Out-File $log -Append -Encoding utf8
exit $rc
