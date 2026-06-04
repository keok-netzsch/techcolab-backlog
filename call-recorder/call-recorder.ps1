# call-recorder.ps1
# Location: $env:USERPROFILE\techcolab-backlog\call-recorder\
#
# Unified flow:
#   1) Language?  English / Portugues
#   2) Category?  Time (Team/) / Stakeholder (Stakeholders/) / Outro (Inbox/)
#   3) Record once -> process per category -> if English, also run the coach
#
# People/stakeholder lists are read live from the vault (no hardcoded names).
# IMPORTANT: keep this file ASCII-only in code lines. It runs under Windows
# PowerShell 5.1, which reads no-BOM files as ANSI; a stray non-ASCII char
# (em-dash, smart quote) breaks string parsing.

$VAULT      = if ($env:TECHCOLAB_VAULT_ROOT) { $env:TECHCOLAB_VAULT_ROOT } else { "$env:USERPROFILE\OneDrive - NETZSCH\Documents\TechColab_D&A_KO" }
$SCRIPT_DIR = "$env:USERPROFILE\techcolab-backlog\call-recorder"
$PYTHON     = "python"

function Show-Menu {
    param([string]$Title, [string[]]$Options)
    Write-Host ""
    Write-Host "  $Title" -ForegroundColor Cyan
    Write-Host ("  " + "-" * $Title.Length)
    for ($i = 0; $i -lt $Options.Count; $i++) {
        Write-Host ("  [" + ($i + 1) + "] " + $Options[$i])
    }
    Write-Host ""
    $idx = -1
    while ($idx -lt 0 -or $idx -ge $Options.Count) {
        $raw = Read-Host "  Escolha (1-$($Options.Count))"
        if ($raw -match '^\d+$') { $idx = [int]$raw - 1 }
    }
    return $idx
}

# Read person/stakeholder folders live from the vault. Excludes the stray
# "1on1" folder and anything starting with "_".
function Get-VaultFolders {
    param([string]$Subdir)
    $base = Join-Path $VAULT $Subdir
    if (-not (Test-Path $base)) { return @() }
    Get-ChildItem $base -Directory |
        Where-Object { $_.Name -ne "1on1" -and -not $_.Name.StartsWith("_") } |
        ForEach-Object { [pscustomobject]@{ Name = ($_.Name -replace '-', ' '); Folder = $_.Name } }
}

# Create a new stakeholder folder with a minimal scaffold; returns the slug.
function New-Stakeholder {
    param([string]$DisplayName)
    $name = $DisplayName.Trim()
    $slug = ($name -replace '\s+', '-') -replace '[\\/:*?"<>|]', ''
    $dir  = Join-Path (Join-Path $VAULT "Stakeholders") $slug
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $today = Get-Date -Format "yyyy-MM-dd"
    $ov = Join-Path $dir "Overview.md"
    if (-not (Test-Path $ov)) {
        "---`ntype: stakeholder`ncreated: $today`n---`n`n**Role:** `n`n## Overview`n" |
            Out-File -FilePath $ov -Encoding UTF8
    }
    $o1 = Join-Path $dir "1on1.md"
    if (-not (Test-Path $o1)) {
        "---`ntype: 1on1-log`nperson: $name`n---`n" | Out-File -FilePath $o1 -Encoding UTF8
    }
    Write-Host "  [OK] Stakeholder criado: Stakeholders\$slug" -ForegroundColor Green
    return $slug
}

# Record one session into $TransFile; returns $true on a non-empty transcript.
function Invoke-Recording {
    param([string]$TransFile, [string]$LangFlag)
    Write-Host ""
    Write-Host "  [REC] Gravando (idioma: $LangFlag)..." -ForegroundColor Red
    Write-Host "  [REC] Feche a janela Python (Ctrl+C nela) para parar." -ForegroundColor Red
    Write-Host ""
    $py   = Join-Path $SCRIPT_DIR "record.py"
    $proc = Start-Process -FilePath $PYTHON `
        -ArgumentList "`"$py`" --language $LangFlag --output `"$TransFile`"" `
        -PassThru -WindowStyle Normal
    $proc.WaitForExit()
    if ($proc.ExitCode -ne 0) {
        Write-Host "  [ERROR] record.py encerrou com erro (exit $($proc.ExitCode))." -ForegroundColor Red
        return $false
    }
    if (-not (Test-Path $TransFile)) {
        Write-Host "  [ERROR] Transcricao nao encontrada: $TransFile" -ForegroundColor Red
        return $false
    }
    if ((Get-Item $TransFile).Length -lt 10) {
        Write-Host "  [ERROR] Transcript vazio ou muito curto." -ForegroundColor Red
        Remove-Item $TransFile -Force
        return $false
    }
    Write-Host "  [OK] Transcricao gerada ($((Get-Item $TransFile).Length) bytes)." -ForegroundColor Green
    return $true
}

# Run the English coach on a transcript (English practice tracking).
function Invoke-Coach {
    param([string]$TransFile)
    Write-Host ""
    Write-Host "  [EN] Conversa em ingles - avaliando como pratica de ingles..." -ForegroundColor Cyan
    $coach = Join-Path $SCRIPT_DIR "coach.py"
    & $PYTHON $coach --transcript $TransFile
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [WARN] coach.py falhou (exit $LASTEXITCODE). Avaliacao de ingles pulada." -ForegroundColor Yellow
    } else {
        Write-Host "  [OK] Progresso de ingles atualizado (Areas/English-Learning/)." -ForegroundColor DarkCyan
    }
}

# Cleanup of old transcripts (>30 days). Audio (.wav) is pruned by record.py.
function Remove-OldTranscripts {
    $trans_dir = Join-Path $SCRIPT_DIR "transcripts"
    if (-not (Test-Path $trans_dir)) { return }
    $cutoff = (Get-Date).AddDays(-30)
    $old = Get-ChildItem $trans_dir -File | Where-Object { $_.LastWriteTime -lt $cutoff }
    if ($old.Count -gt 0) {
        $old | Remove-Item -Force
        Write-Host "  [CLEAN] $($old.Count) transcript(s) antigo(s) removido(s)." -ForegroundColor DarkGray
    }
    Get-ChildItem $SCRIPT_DIR -Filter "transcript_*.txt" -File -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -lt $cutoff } | Remove-Item -Force
}

# ===============================================================
# FLUXO PRINCIPAL
# ===============================================================

Clear-Host
Write-Host ""
Write-Host "  ================================" -ForegroundColor DarkCyan
Write-Host "      Call Recorder -- KO         " -ForegroundColor DarkCyan
Write-Host "  ================================" -ForegroundColor DarkCyan

Remove-OldTranscripts

# 1) Idioma
$langIdx  = Show-Menu -Title "Idioma da conversa?" -Options @("English", "Portugues")
$langFlag = if ($langIdx -eq 0) { "en" } else { "pt" }

# 2) Categoria
$catIdx = Show-Menu -Title "Categoria?" -Options @("Time (liderado)", "Stakeholder", "Outro (nota avulsa)")

$date_str  = Get-Date -Format "yyyy-MM-dd"
$time_str  = Get-Date -Format "HH-mm"
$trans_dir = Join-Path $SCRIPT_DIR "transcripts"
New-Item -ItemType Directory -Force -Path $trans_dir | Out-Null

# Resolve target (folder + processing action) per category
$folder       = $null
$structured   = $false
$process_args = $null

if ($catIdx -eq 0) {
    # ----- TIME -----
    $people = @(Get-VaultFolders "Team")
    if ($people.Count -eq 0) { Write-Host "  [ERROR] Nenhum liderado em Team/." -ForegroundColor Red; Read-Host "  ENTER"; exit 1 }
    $idx    = Show-Menu -Title "Com quem do time?" -Options @($people | ForEach-Object { $_.Name })
    $folder = $people[$idx].Folder
    Write-Host "  -> $($people[$idx].Name)" -ForegroundColor Green

    $typeIdx    = Show-Menu -Title "Tipo de reuniao" -Options @("Regular (pauta livre)", "Estruturada (mensal)")
    $structured = $typeIdx -eq 1
    if ($structured) {
        Write-Host ""
        Write-Host "  PERGUNTAS DA REUNIAO ESTRUTURADA:" -ForegroundColor Cyan
        Write-Host ("  " + "-" * 38) -ForegroundColor DarkGray
        Write-Host ""
        Write-Host "  1. Como voce tem se sentido em relacao a sua carga de" -ForegroundColor White
        Write-Host "     trabalho nas ultimas semanas?" -ForegroundColor White
        Write-Host ""
        Write-Host "  2. Se voce pudesse ajustar algo na forma como o trabalho" -ForegroundColor White
        Write-Host "     e distribuido, o que mudaria?" -ForegroundColor White
        Write-Host ""
        Write-Host "  3. Como voce percebe a colaboracao entre as pessoas do" -ForegroundColor White
        Write-Host "     time no dia a dia?" -ForegroundColor White
        Write-Host ""
        Write-Host "  4. O que poderia ser feito para o time se sentir mais" -ForegroundColor White
        Write-Host "     conectado e alinhado como grupo?" -ForegroundColor White
        Write-Host ""
        Read-Host "  Perguntas exibidas. ENTER quando pronto para gravar"
    }

    $trans_file   = Join-Path $trans_dir "${date_str}_${time_str}_${folder}.txt"
    $process_args = @("transcript", "--person", $folder, "--transcript", $trans_file, "--date", $date_str, "--lang", $langFlag)
    if ($structured) { $process_args += "--structured" }

} elseif ($catIdx -eq 1) {
    # ----- STAKEHOLDER -----
    $stk     = @(Get-VaultFolders "Stakeholders")
    $options = @($stk | ForEach-Object { $_.Name }) + "[+] Criar novo stakeholder"
    $idx     = Show-Menu -Title "Qual stakeholder?" -Options $options
    if ($idx -eq $stk.Count) {
        $newName = Read-Host "  Nome do novo stakeholder"
        if (-not $newName.Trim()) { Write-Host "  [ERROR] Nome vazio." -ForegroundColor Red; Read-Host "  ENTER"; exit 1 }
        $folder = New-Stakeholder $newName
    } else {
        $folder = $stk[$idx].Folder
        Write-Host "  -> $($stk[$idx].Name)" -ForegroundColor Green
    }
    $trans_file   = Join-Path $trans_dir "${date_str}_${time_str}_${folder}.txt"
    $process_args = @("manager", "--manager", $folder, "--transcript", $trans_file, "--date", $date_str, "--lang", $langFlag)

} else {
    # ----- OUTRO (nota avulsa) -----
    Write-Host "  -> Nota avulsa (Inbox, para triar depois)" -ForegroundColor Green
    $trans_file   = Join-Path $trans_dir "${date_str}_${time_str}_nota-avulsa.txt"
    $process_args = @("note", "--transcript", $trans_file, "--date", $date_str, "--time", $time_str, "--lang", $langFlag)
}

# Metadata for the queue job
$kind     = @("person", "manager", "note")[$catIdx]
$target   = if ($catIdx -eq 2) { "" } else { $folder }
$base     = [System.IO.Path]::GetFileNameWithoutExtension($trans_file)
$rec_dir  = Join-Path $SCRIPT_DIR "recordings"
$wav_path = Join-Path $rec_dir "$base.wav"
$coach    = $langFlag -eq "en"

# 3) Quando processar? (enfileirar = nao trava; processa as 17h no agente diario)
$pmode = Show-Menu -Title "Quando processar?" -Options @("Enfileirar (processa as 17h, nao trava agora)", "Processar agora (lento)")

if ($pmode -eq 0) {
    # ----- FILA: grava so o .wav (sem Whisper) e enfileira -----
    New-Item -ItemType Directory -Force -Path $rec_dir | Out-Null
    Write-Host ""
    Write-Host "  [REC] Gravando (idioma: $langFlag) - so audio, sem transcrever agora..." -ForegroundColor Red
    Write-Host "  [REC] Feche a janela Python (Ctrl+C nela) para parar." -ForegroundColor Red
    Write-Host ""
    $py_script = Join-Path $SCRIPT_DIR "record.py"
    $proc = Start-Process -FilePath $PYTHON `
        -ArgumentList "`"$py_script`" --language $langFlag --record-only --output `"$trans_file`"" `
        -PassThru -WindowStyle Normal
    $proc.WaitForExit()
    if ($proc.ExitCode -ne 0 -or -not (Test-Path $wav_path)) {
        Write-Host "  [ERROR] Gravacao falhou (audio nao salvo)." -ForegroundColor Red
        Read-Host "  ENTER para sair"; exit 1
    }
    $job = [ordered]@{
        wav        = "$base.wav"
        transcript = $trans_file
        kind       = $kind
        target     = $target
        lang       = $langFlag
        date       = $date_str
        time       = $time_str
        structured = [bool]$structured
        coach      = [bool]$coach
    }
    $job_path = Join-Path $rec_dir "$base.job.json"
    $enc = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($job_path, ($job | ConvertTo-Json -Compress), $enc)
    Write-Host ""
    Write-Host "  [OK] Enfileirado. Transcricao + processamento as 17h (agente diario)." -ForegroundColor DarkCyan
    Write-Host "  Audio: recordings\$base.wav" -ForegroundColor DarkGray
    Write-Host ""
    Read-Host "  ENTER para sair"; exit 0
}

# ----- PROCESSAR AGORA (fluxo sincrono) -----
if (-not (Invoke-Recording -TransFile $trans_file -LangFlag $langFlag)) {
    Read-Host "  ENTER para sair"; exit 1
}

Write-Host ""
Write-Host "  [Ollama] Processando transcricao..." -ForegroundColor Yellow
$process_py = Join-Path $SCRIPT_DIR "process.py"
& $PYTHON $process_py @process_args
$procExit = $LASTEXITCODE
if ($procExit -ne 0) {
    Write-Host "  [ERROR] process.py falhou (exit $procExit). Transcript mantido em:" -ForegroundColor Red
    Write-Host "  $trans_file" -ForegroundColor Yellow
    Read-Host "  ENTER para sair"; exit 1
}

if ($langFlag -eq "en") {
    Invoke-Coach -TransFile $trans_file
}

Write-Host ""
Write-Host "  Concluido. Sessao salva no vault." -ForegroundColor DarkCyan
Write-Host ""
Read-Host "  ENTER para sair"
