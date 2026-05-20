# create-shortcuts.ps1
# Gera todos os atalhos do Techco.lab em uma pasta no Desktop.
# Execute novamente sempre que adicionar um novo script/app.

$desktop  = [System.Environment]::GetFolderPath("Desktop")
$folder   = Join-Path $desktop "Techco.lab"
$TB       = "C:\Users\Kelvin.okuda\techcolab-backlog"
$CR       = "C:\Users\Kelvin.okuda\Scripts\call-recorder"
$ps       = "powershell.exe"
$psArgs   = "-ExecutionPolicy Bypass -NoExit -File"
$ws       = New-Object -ComObject WScript.Shell

New-Item -ItemType Directory -Force -Path $folder | Out-Null

function New-Shortcut {
    param(
        [string]$Name,
        [string]$Target,
        [string]$Arguments = "",
        [string]$WorkDir,
        [string]$Description,
        [string]$Icon = "shell32.dll,13"
    )
    $lnk = $ws.CreateShortcut("$folder\$Name.lnk")
    $lnk.TargetPath     = $Target
    $lnk.Arguments      = $Arguments
    $lnk.WorkingDirectory = $WorkDir
    $lnk.Description    = $Description
    $lnk.IconLocation   = $Icon
    $lnk.Save()
    Write-Host "  ✅ $Name" -ForegroundColor Green
}

Write-Host ""
Write-Host "  Criando atalhos em: $folder" -ForegroundColor Cyan
Write-Host ""

# ── 1. Iniciar App ─────────────────────────────────────────────────────────────
# Abre o Personal Toolkit · Techco.lab no navegador (http://localhost:8501)
New-Shortcut `
    -Name        "1. Iniciar App" `
    -Target      "wscript.exe" `
    -Arguments   "`"$TB\start_silent.vbs`"" `
    -WorkDir     $TB `
    -Description "Inicia o Personal Toolkit Techco.lab (Streamlit, porta 8501)" `
    -Icon        "shell32.dll,13"

# ── 2. Call Recorder ───────────────────────────────────────────────────────────
# Abre o menu: [1] 1on1 com time  [2] English Coach
# Grava o áudio, transcreve com Whisper e processa com IA
New-Shortcut `
    -Name        "2. Call Recorder" `
    -Target      $ps `
    -Arguments   "$psArgs `"$CR\call-recorder.ps1`"" `
    -WorkDir     $CR `
    -Description "Grava e processa reuniões 1on1 ou sessões de English Coach" `
    -Icon        "shell32.dll,168"

# ── 3. Rodar Agente ────────────────────────────────────────────────────────────
# Fase 1: analisa o backlog e gera o relatório diário no Obsidian
# Depois abra o relatório no Obsidian, marque os itens aprovados, e use "Executar Agente"
New-Shortcut `
    -Name        "3. Rodar Agente" `
    -Target      "cmd.exe" `
    -Arguments   "/k `"$TB\run_agent.bat`"" `
    -WorkDir     $TB `
    -Description "Fase 1: analisa o backlog e gera o relatório diário no Obsidian" `
    -Icon        "shell32.dll,25"

# ── 4. Executar Agente ─────────────────────────────────────────────────────────
# Fase 2: abre o Claude Code com o comando já copiado no clipboard
# Basta colar (Ctrl+V) e pressionar Enter no Claude Code
New-Shortcut `
    -Name        "4. Executar Agente" `
    -Target      "cmd.exe" `
    -Arguments   "/k `"$TB\execute_agent.bat`"" `
    -WorkDir     $TB `
    -Description "Fase 2: abre Claude Code para executar itens aprovados no relatório" `
    -Icon        "shell32.dll,76"

# ── 5. Push Rápido ────────────────────────────────────────────────────────────
# Commit e push imediato nos dois repos, sem testes nem prompts
# Use no meio do desenvolvimento para salvar progresso no GitHub
New-Shortcut `
    -Name        "5. Push Rapido" `
    -Target      $ps `
    -Arguments   "$psArgs `"$TB\quick-push.ps1`"" `
    -WorkDir     $TB `
    -Description "Commit e push rápido em ambos os repos — sem testes, mensagem automática" `
    -Icon        "shell32.dll,19"

# ── 6. Encerrar Sessão ─────────────────────────────────────────────────────────
# Roda os testes, commita e faz push em todos os repositórios
# Use ao final de cada sessão de desenvolvimento
New-Shortcut `
    -Name        "6. Encerrar Sessao" `
    -Target      $ps `
    -Arguments   "$psArgs `"$TB\close-session.ps1`"" `
    -WorkDir     $TB `
    -Description "Roda testes, commita e push em techcolab-backlog e call-recorder" `
    -Icon        "shell32.dll,27"

Write-Host ""
Write-Host "  Pasta criada: $folder" -ForegroundColor DarkCyan
Write-Host "  Abra no Explorer para fixar na barra de tarefas ou arrastar para o Desktop." -ForegroundColor DarkGray
Write-Host ""
Start-Sleep -Seconds 2
explorer.exe $folder
