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
    Write-Host "  [REC] Gravando (idioma: auto-detect)..." -ForegroundColor Red
    Write-Host "  [REC] Feche a janela Python (Ctrl+C nela) para parar." -ForegroundColor Red
    Write-Host ""
    $py   = Join-Path $SCRIPT_DIR "record.py"
    $proc = Start-Process -FilePath $PYTHON `
        -ArgumentList "`"$py`" --language auto --output `"$TransFile`"" `
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

# Build unified person list: [team members] + [stakeholders (stk)] + [Outro]
$teamPeople  = @(Get-VaultFolders "Team")
$stkPeople   = @(Get-VaultFolders "Stakeholders")
if ($teamPeople.Count -eq 0 -and $stkPeople.Count -eq 0) {
    Write-Host "  [ERROR] Nenhum contato encontrado em Team/ ou Stakeholders/." -ForegroundColor Red
    Read-Host "  ENTER"; exit 1
}

$combined = @()
$combined += $teamPeople   | ForEach-Object { [pscustomobject]@{ Label=$_.Name;   Folder=$_.Name -replace ' ','-'; Kind="person"  } }
$combined += $stkPeople    | ForEach-Object { [pscustomobject]@{ Label="$($_.Name) (stk)"; Folder=$_.Folder; Kind="manager" } }
$combined += [pscustomobject]@{ Label="Outro (nota avulsa)"; Folder=""; Kind="note" }

$selIdx = Show-Menu -Title "Com quem?" -Options @($combined | ForEach-Object { $_.Label })
$sel    = $combined[$selIdx]
Write-Host "  -> $($sel.Label)" -ForegroundColor Green

$date_str  = Get-Date -Format "yyyy-MM-dd"
$time_str  = Get-Date -Format "HH-mm"
$trans_dir = Join-Path $SCRIPT_DIR "transcripts"
New-Item -ItemType Directory -Force -Path $trans_dir | Out-Null

$kind       = $sel.Kind
$folder     = $sel.Folder
$structured = $false

if ($kind -eq "person") {
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
}

if ($kind -eq "manager" -and $stkPeople.Count -gt 0) {
    # Offer to create a new stakeholder if selection was the (stk) option not yet in vault
    # (New-Stakeholder path kept for explicit [+] scenario via direct script use if needed)
    if (-not (Test-Path (Join-Path (Join-Path $VAULT "Stakeholders") $folder))) {
        Write-Host "  [WARN] Pasta do stakeholder nao encontrada: Stakeholders\$folder" -ForegroundColor Yellow
    }
}

$trans_file = switch ($kind) {
    "person"  { Join-Path $trans_dir "${date_str}_${time_str}_${folder}.txt" }
    "manager" { Join-Path $trans_dir "${date_str}_${time_str}_${folder}.txt" }
    default   { Join-Path $trans_dir "${date_str}_${time_str}_nota-avulsa.txt" }
}

$process_args = switch ($kind) {
    "person"  { @("transcript", "--person",  $folder, "--transcript", $trans_file, "--date", $date_str, "--lang", "pt") }
    "manager" { @("manager",    "--manager", $folder, "--transcript", $trans_file, "--date", $date_str, "--lang", "pt") }
    default   { @("note", "--transcript", $trans_file, "--date", $date_str, "--time", $time_str, "--lang", "pt") }
}
if ($structured) { $process_args += "--structured" }

# Metadata for the queue job (lang=auto: Whisper detects; coach decided by process.py)
$langFlag = "auto"
$target   = $folder
$base     = [System.IO.Path]::GetFileNameWithoutExtension($trans_file)
$rec_dir  = Join-Path $SCRIPT_DIR "recordings"
$wav_path = Join-Path $rec_dir "$base.wav"
$coach    = $false  # process.py decides from detected language when lang=auto

# 3) Quando processar? (enfileirar = nao trava; processa as 17h no agente diario)
$pmode = Show-Menu -Title "Quando processar?" -Options @("Enfileirar (processa as 17h, nao trava agora)", "Processar agora (lento)")

if ($pmode -eq 0) {
    # ----- FILA: grava so o .wav (sem Whisper) e enfileira -----
    New-Item -ItemType Directory -Force -Path $rec_dir | Out-Null
    Write-Host ""
    Write-Host "  [REC] Gravando (idioma: auto-detect) - so audio, sem transcrever agora..." -ForegroundColor Red
    Write-Host "  [REC] Feche a janela Python (Ctrl+C nela) para parar." -ForegroundColor Red
    Write-Host ""
    $py_script = Join-Path $SCRIPT_DIR "record.py"
    $proc = Start-Process -FilePath $PYTHON `
        -ArgumentList "`"$py_script`" --language auto --record-only --output `"$trans_file`"" `
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
        lang       = "auto"
        date       = $date_str
        time       = $time_str
        structured = [bool]$structured
        coach      = $false
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

# Read detected language from sidecar written by record.py
$detectedLang = "pt"
$langSidecar  = $trans_file + ".lang"
if (Test-Path $langSidecar) {
    $detectedLang = (Get-Content $langSidecar -Raw).Trim()
    Remove-Item $langSidecar -Force
}
# Patch --lang in process_args with the detected value
$process_args = $process_args | ForEach-Object { $_ }
$li = [Array]::IndexOf($process_args, "--lang")
if ($li -ge 0 -and $li + 1 -lt $process_args.Count) { $process_args[$li + 1] = $detectedLang }

Write-Host ""
Write-Host "  [Ollama] Processando transcricao (idioma detectado: $detectedLang)..." -ForegroundColor Yellow
$process_py = Join-Path $SCRIPT_DIR "process.py"
& $PYTHON $process_py @process_args
$procExit = $LASTEXITCODE
if ($procExit -ne 0) {
    Write-Host "  [ERROR] process.py falhou (exit $procExit). Transcript mantido em:" -ForegroundColor Red
    Write-Host "  $trans_file" -ForegroundColor Yellow
    Read-Host "  ENTER para sair"; exit 1
}

if ($detectedLang -eq "en") {
    Invoke-Coach -TransFile $trans_file
}

Write-Host ""
Write-Host "  Concluido. Sessao salva no vault." -ForegroundColor DarkCyan
Write-Host ""
Read-Host "  ENTER para sair"
