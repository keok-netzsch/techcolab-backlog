<#
.SYNOPSIS
    Motor unico de notificacao do toolkit. Um script, N perfis em notify-config.json.

.DESCRIPTION
    Substitui os scripts de lembrete paralelos (P3 do PM review 2026-08-29). Cada tarefa
    agendada passa a chamar:

        notify.ps1 -Profile <nome>

    O QUE MUDA: onde a logica vivia. O QUE NAO MUDA: texto, horario e comportamento de
    cada lembrete - a migracao e 1:1 por decisao do plano.

    DOIS MODOS, e a escolha NAO e estetica:

      messagebox  janela WinForms TopMost, bloqueante. E o modo correto para lembrete
                  que nao pode ser perdido. Adotado em 2026-08-11 porque a API de toast
                  reportava sucesso em toda execucao (10 entradas reais no registro de
                  notificacoes do Windows, horarios batendo com cada disparo agendado)
                  enquanto o Focus Assist suprimia o banner - o lembrete se perdia em
                  silencio. MessageBox nao passa pelo Focus Assist.

      balloon     NotifyIcon do system tray. Menos intrusivo, mas sujeito a supressao.
                  Existe aqui porque os lembretes de estudo (cdmp, study) usam esse modo
                  hoje e a migracao e 1:1. Nao escolha este modo para algo critico.

    CORPO DINAMICO: um perfil pode ter "message" (texto fixo) ou "messageScript"
    (caminho, relativo a raiz do repo, de um .ps1 que ESCREVE o corpo na saida). Se o
    script nao devolver nada, o lembrete NAO aparece - lembrete que toca em dia vazio
    para de ser lido.

.PARAMETER Profile
    Nome do perfil em notify-config.json.

.PARAMETER List
    Lista os perfis disponiveis e sai.

.PARAMETER WhatIf
    Resolve o perfil e imprime o que seria mostrado, sem abrir janela nenhuma.
    Use para testar migracao de tarefa agendada.

.EXAMPLE
    .\scripts\notify.ps1 -Profile morning-reminder
    .\scripts\notify.ps1 -Profile triage-reminder -WhatIf
    .\scripts\notify.ps1 -List
#>
[CmdletBinding()]
param(
    [string]$Profile,
    [switch]$List,
    [switch]$WhatIf,
    [string]$ConfigPath
)

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path $PSScriptRoot -Parent
if (-not $ConfigPath) { $ConfigPath = Join-Path $PSScriptRoot 'notify-config.json' }

if (-not (Test-Path $ConfigPath)) {
    Write-Host "Config nao encontrada: $ConfigPath"
    exit 1
}

try {
    $config = Get-Content $ConfigPath -Raw -Encoding utf8 | ConvertFrom-Json
} catch {
    Write-Host "Config invalida ($ConfigPath): $($_.Exception.Message)"
    exit 1
}

if ($List) {
    Write-Host "Perfis em $ConfigPath :"
    $config.profiles.PSObject.Properties | ForEach-Object {
        $m = if ($_.Value.mode) { $_.Value.mode } else { 'messagebox' }
        "  {0,-20} [{1}] {2}" -f $_.Name, $m, $_.Value.title
    }
    exit 0
}

if (-not $Profile) { Write-Host "Informe -Profile <nome> (ou -List)."; exit 1 }

$p = $config.profiles.$Profile
if (-not $p) {
    Write-Host "Perfil desconhecido: $Profile"
    Write-Host "Disponiveis: $(($config.profiles.PSObject.Properties.Name) -join ', ')"
    exit 1
}

$title = $p.title
$mode  = if ($p.mode) { $p.mode } else { 'messagebox' }

# --- corpo: fixo ou gerado ---
$message = $p.message
if ($p.messageScript) {
    $gen = Join-Path $repoRoot $p.messageScript
    if (-not (Test-Path $gen)) { Write-Host "Gerador nao encontrado: $gen"; exit 1 }
    # Zerar antes: $LASTEXITCODE guarda o codigo do ULTIMO processo/script - sem isso um
    # valor residual faria o motor abortar por um erro que nao e deste gerador.
    $global:LASTEXITCODE = 0
    try {
        # Só o stdout vira corpo. Diagnostico do gerador sai por Write-Host, que nao
        # entra no pipeline - capturar 2>&1 aqui misturaria erro com texto do lembrete.
        $out = & $gen | Out-String
    } catch {
        Write-Host "Gerador falhou ($($p.messageScript)): $($_.Exception.Message)"
        exit 1
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Gerador saiu com codigo $LASTEXITCODE - nao da para saber se ha algo a notificar."
        exit $LASTEXITCODE
    }
    $message = $out.Trim()
}

# Silencio proposital: sem corpo, sem lembrete.
if ([string]::IsNullOrWhiteSpace($message)) {
    Write-Host "[$Profile] nada a notificar - silencioso."
    exit 0
}

if ($WhatIf) {
    Write-Host "--- $Profile (modo: $mode) ---"
    Write-Host "TITULO : $title"
    Write-Host "CORPO  :"
    Write-Host $message
    exit 0
}

switch ($mode) {
    'messagebox' {
        Add-Type -AssemblyName System.Windows.Forms
        try {
            # Form invisivel so para dar dono a MessageBox: sem isso ela pode nascer
            # atras da janela ativa e o lembrete some do campo de visao.
            $form = New-Object System.Windows.Forms.Form
            $form.TopMost = $true
            $form.Opacity = 0
            $form.ShowInTaskbar = $false
            $form.StartPosition = "CenterScreen"
            $form.Size = New-Object System.Drawing.Size(0, 0)
            $form.Show()
            [System.Windows.Forms.MessageBox]::Show($form, $message, $title,
                [System.Windows.Forms.MessageBoxButtons]::OK,
                [System.Windows.Forms.MessageBoxIcon]::Information) | Out-Null
            $form.Close()
            Write-Host "[$Profile] MessageBox exibida e fechada."
        } catch {
            Write-Host "[$Profile] MessageBox falhou: $($_.Exception.Message)"
            exit 1
        }
    }
    'balloon' {
        Add-Type -AssemblyName System.Windows.Forms
        Add-Type -AssemblyName System.Drawing
        try {
            $notify = New-Object System.Windows.Forms.NotifyIcon
            $notify.Icon = [System.Drawing.SystemIcons]::Information
            $notify.BalloonTipTitle = $title
            $notify.BalloonTipText = $message
            $notify.Visible = $true
            $notify.ShowBalloonTip(20000)
            Start-Sleep -Seconds 12   # o balao some se o processo morre antes de renderizar
            $notify.Dispose()
            Write-Host "[$Profile] balao exibido."
        } catch {
            Write-Host "[$Profile] balao falhou: $($_.Exception.Message)"
            exit 1
        }
    }
    default {
        Write-Host "Modo desconhecido '$mode' no perfil $Profile (use messagebox ou balloon)."
        exit 1
    }
}

exit 0
