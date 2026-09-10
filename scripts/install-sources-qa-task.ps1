<#
  Instala (ou remove) a tarefa do QA de consistencia.

      .\install-sources-qa-task.ps1            # instala / reinstala
      .\install-sources-qa-task.ps1 -Remove    # desinstala

  Dias uteis 08:50. O horario nao e arbitrario: fica 20 min depois da rotina
  `pendencias-do-kelvin` (08:30) e 10 min depois de `TechColab Aprovacoes
  Pendentes` (08:40), no mesmo bloco em que ele ja esta olhando o que precisa de
  decisao. Um alerta de consistencia solto no meio da tarde nao encontra ninguem.

  Silencioso quando nao ha achado de severidade `erro`: o corpo
  (`notify-body/sources-qa-body.ps1`) nao imprime nada e o motor nao abre janela
  (padrao 8). Roda offline de proposito — o check de rede depende da VPN no minuto
  exato do disparo, e falso alarme diario de certificado ensina a ignorar o aviso.

  Nasceu em 2026-09-10, junto com o pacote `vaultsources`. Ver
  `docs/vaultsources.md` e o ADR `2026-09-10-vaultsources-conhecimento-externo.md`.
#>

param([switch]$Remove)

$nome = "TechColab Sources QA"
$script = Join-Path $env:USERPROFILE "techcolab-backlog\scripts\notify.ps1"

if ($Remove) {
    Unregister-ScheduledTask -TaskName $nome -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Tarefa '$nome' removida."
    exit 0
}

if (-not (Test-Path $script)) {
    Write-Host "ERRO: nao encontrei $script"
    exit 1
}

$arg = '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $script + '" -Profile sources-qa'
$acao = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $arg

$gatilho = New-ScheduledTaskTrigger -Weekly `
    -DaysOfWeek Monday, Tuesday, Wednesday, Thursday, Friday -At "08:50"

# StartWhenAvailable: se a maquina estiver desligada as 08:50, o aviso aparece no
# proximo logon em vez de sumir naquele dia.
$cfg = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 20)

Register-ScheduledTask -TaskName $nome -Action $acao -Trigger $gatilho `
    -Settings $cfg -Description "QA de consistencia do segundo cerebro (vaultsources). Silencioso quando nao ha erro." -Force | Out-Null

Write-Host "Tarefa '$nome' instalada: dias uteis 08:50."
Write-Host "Teste agora com: .\scripts\notify.ps1 -Profile sources-qa"
