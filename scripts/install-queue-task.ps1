# Instala a tarefa dedicada da fila de transcricao e desfaz a duplicacao.
#
#   .\install-queue-task.ps1            # instala
#   .\install-queue-task.ps1 -Remove    # desinstala (e nao restaura a duplicacao)
#
# O que faz, e por que:
#
# 1. Cria "CallRecorder-Queue" as 20:00, chamando SO a fila.
# 2. Desabilita "TechColab Daily Agent", que era a segunda tarefa apontando para
#    run_agent.bat. As duas rodavam o MESMO agent/daily_report.py - uma as 07:00
#    e outra as 20:00 - e o CLAUDE.md do repo diz que so pode existir uma, porque
#    duas competem pelo mesmo logs\agent-last.log e uma fica permanentemente
#    vermelha mascarando falha real.
#
# Desabilita em vez de apagar: se algo nesse agente for necessario a noite e nao
# estiver no da manha, da para reverter com um clique em vez de reconstruir.
# "TechColab Backlog Agent" (07:00) segue intacto - e o relatorio da manha.

param([switch]$Remove)

$nome = "CallRecorder-Queue"
$script = Join-Path $env:USERPROFILE "techcolab-backlog\scripts\run-queue.ps1"

if ($Remove) {
    Unregister-ScheduledTask -TaskName $nome -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Tarefa '$nome' removida."
    Write-Host "ATENCAO: 'TechColab Daily Agent' continua desabilitado de proposito."
    Write-Host "Reative a mao so se souber que quer as duas tarefas no mesmo .bat."
    exit 0
}

if (-not (Test-Path $script)) { Write-Host "ERRO: nao encontrei $script"; exit 1 }

$arg = '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $script + '"'
$acao = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $arg
$gatilho = New-ScheduledTaskTrigger -Daily -At "20:00"

# 6h de limite: 4h de audio a ~2x tempo real cabem, e um travamento nao segura a
# maquina ate o dia seguinte. StartWhenAvailable para que noite com a maquina
# desligada nao vire gravacao perdida - o guard de horario dentro do
# daily_report ja impede que a recuperacao caia no meio do expediente.
$cfg = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 6)

Register-ScheduledTask -TaskName $nome -Action $acao -Trigger $gatilho `
    -Settings $cfg -Force `
    -Description "Transcreve as gravacoes pendentes (process.py queue). Separada do agente de backlog em 2026-08-29: as duas no mesmo run_agent.bat faziam a analise de ideias consumir o limite de 6h e a transcricao nunca rodar." | Out-Null

$duplicada = Get-ScheduledTask -TaskName "TechColab Daily Agent" -ErrorAction SilentlyContinue
if ($duplicada -and $duplicada.State -ne "Disabled") {
    Disable-ScheduledTask -TaskName "TechColab Daily Agent" | Out-Null
    Write-Host "'TechColab Daily Agent' DESABILITADO (era a segunda tarefa no mesmo run_agent.bat)."
}

$t = Get-ScheduledTask -TaskName $nome
$i = $t | Get-ScheduledTaskInfo
Write-Host ("Tarefa : {0}" -f $t.TaskName)
Write-Host ("Estado : {0}" -f $t.State)
Write-Host ("Proxima: {0}" -f $i.NextRunTime)
Write-Host ""
Write-Host "Tarefas apontando para run_agent.bat agora:"
Get-ScheduledTask | Where-Object { $_.Actions.Arguments -match "run_agent" } |
    ForEach-Object { Write-Host ("   {0}  [{1}]" -f $_.TaskName, $_.State) }
