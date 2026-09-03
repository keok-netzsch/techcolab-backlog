# Instala a tarefa agendada do indice de busca do vault.
#
#   .\install-vault-index-task.ps1            # instala (ou recria) "TechColab Vault Index"
#   .\install-vault-index-task.ps1 -Remove    # desinstala
#
# O que faz: diariamente as 18:00 roda scripts\vault-index-nightly.ps1, que chama
# `python -m vaultindex build --embed`. 18:00 fica depois do `vault-daily-commit`
# (17:30), entao a noite ja indexa o que o dia commitou. StartWhenAvailable: noite com
# a maquina desligada roda na proxima ligada. Limite de 1h: o pior caso realista (indice
# apagado + embutir ~13 mil chunks) leva minutos; 1h e folga, nao estimativa.
#
# Registre a mudanca em docs/scheduled-automation.md no mesmo commit (ARCHITECTURE.md,
# "O que roda sozinho").

param([switch]$Remove)

$nome = "TechColab Vault Index"
$script = Join-Path $env:USERPROFILE "techcolab-backlog\scripts\vault-index-nightly.ps1"

if ($Remove) {
    Unregister-ScheduledTask -TaskName $nome -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Tarefa '$nome' removida."
    exit 0
}

if (-not (Test-Path $script)) { Write-Host "ERRO: nao encontrei $script"; exit 1 }

$arg = '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $script + '"'
$acao = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $arg
$gatilho = New-ScheduledTaskTrigger -Daily -At "18:00"
$cfg = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1)

Unregister-ScheduledTask -TaskName $nome -Confirm:$false -ErrorAction SilentlyContinue
Register-ScheduledTask -TaskName $nome -Action $acao -Trigger $gatilho -Settings $cfg `
    -Description "Indice de busca do vault (vaultindex): build incremental + embeddings dos chunks novos. Log em techcolab-backlog\logs\vault-index-YYYY-MM.log." | Out-Null

$t = Get-ScheduledTask -TaskName $nome
Write-Host ("Tarefa '{0}' instalada: {1}, proxima execucao {2}" -f $nome, $t.State, (Get-ScheduledTaskInfo -TaskName $nome).NextRunTime)
