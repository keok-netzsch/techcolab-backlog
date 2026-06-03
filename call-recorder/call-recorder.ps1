# call-recorder.ps1
# Location: $env:USERPROFILE\techcolab-backlog\call-recorder\
#
# Modes:
#   1. 1on1 com time     — grava e estrutura reuniao 1:1 com liderado (Team/)
#   2. English Coach     — sessao de pratica de ingles com avaliacao por IA
#   3. Call com Gestor   — grava e estrutura reuniao com gestor/stakeholder (Stakeholders/)

# Vault root — override with env var TECHCOLAB_VAULT_ROOT; fallback below.
$VAULT      = if ($env:TECHCOLAB_VAULT_ROOT) { $env:TECHCOLAB_VAULT_ROOT } else { "$env:USERPROFILE\OneDrive - NETZSCH\Documents\TechColab_D&A_KO" }
$SCRIPT_DIR = "$env:USERPROFILE\techcolab-backlog\call-recorder"
$PYTHON     = "python"

$PEOPLE = @(
    @{ Name = "Ana Leite";     Folder = "Ana-Leite"     },
    @{ Name = "Daniel Lima";   Folder = "Daniel-Lima"   },
    @{ Name = "Lucas Shizuno"; Folder = "Lucas-Shizuno" },
    @{ Name = "Pedro Hennig";  Folder = "Pedro-Hennig"  },
    @{ Name = "Pedro Klein";   Folder = "Pedro-Klein"   }
)

$MANAGERS = @(
    @{ Name = "Alberto Reuters";       Folder = "Alberto-Reuters"       },
    @{ Name = "Stefan Lautenschlager"; Folder = "Stefan-Lautenschlager" }
)

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


function Save-Block {
    param(
        [string]$FilePath,
        [string]$Content,
        [string]$Mode = "prepend"   # prepend = mais recente no topo | append = mais recente no final
    )
    if (-not (Test-Path $FilePath)) {
        $Content | Out-File -FilePath $FilePath -Encoding UTF8
        return
    }
    $existing = Get-Content $FilePath -Raw -Encoding UTF8

    # Append: Overview.md cresce para baixo
    if ($Mode -eq "append") {
        $new = $existing.TrimEnd() + "`n`n---`n`n" + $Content + "`n"
        $new | Out-File -FilePath $FilePath -Encoding UTF8
        return
    }

    # Prepend: 1on1 / OKR / PDI — conteudo mais recente logo apos o frontmatter YAML.
    # Parsing por linha (deterministico): detecta o bloco YAML (--- ... ---) no topo
    # e insere o novo conteudo imediatamente depois dele. Robusto a quantos "---"
    # o resto do arquivo contenha como separadores de sessoes anteriores.
    $lines    = $existing -split "`r?`n"
    $insertAt = 0   # sem frontmatter -> insere no topo

    if ($lines.Count -gt 0 -and $lines[0].Trim() -eq "---") {
        for ($i = 1; $i -lt $lines.Count; $i++) {
            if ($lines[$i].Trim() -eq "---") { $insertAt = $i + 1; break }
        }
    }

    $head = if ($insertAt -gt 0) { ($lines[0..($insertAt - 1)] -join "`n") } else { "" }
    $tail = if ($insertAt -lt $lines.Count) { ($lines[$insertAt..($lines.Count - 1)] -join "`n") } else { "" }

    $block = "`n`n" + $Content.TrimEnd() + "`n`n---`n"
    $new   = ($head.TrimEnd() + $block + "`n" + $tail.TrimStart("`n")).TrimEnd() + "`n"
    $new | Out-File -FilePath $FilePath -Encoding UTF8
}

# Limpeza de transcripts antigos (>30 dias)
function Remove-OldTranscripts {
    $trans_dir = Join-Path $SCRIPT_DIR "transcripts"
    if (-not (Test-Path $trans_dir)) { return }
    $cutoff = (Get-Date).AddDays(-30)
    $old = Get-ChildItem $trans_dir -File | Where-Object { $_.LastWriteTime -lt $cutoff }
    if ($old.Count -gt 0) {
        $old | Remove-Item -Force
        Write-Host "  [CLEAN] $($old.Count) transcript(s) antigo(s) removido(s)." -ForegroundColor DarkGray
    }
    # Arquivos temporarios na raiz do script (transcript_en_* deixados por sessoes anteriores)
    Get-ChildItem $SCRIPT_DIR -Filter "transcript_en_*.txt" -File |
        Where-Object { $_.LastWriteTime -lt $cutoff } |
        Remove-Item -Force
}

# Fluxo: English Coach
function Invoke-EnglishCoach {
    Write-Host ""
    Write-Host "  ================================" -ForegroundColor Cyan
    Write-Host "      ENGLISH COACH (AI)          " -ForegroundColor Cyan
    Write-Host "  ================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Fale em ingles. A sessao sera gravada, transcrita e avaliada por IA." -ForegroundColor Gray
    Write-Host ""

    $topic = Read-Host "  Topico / contexto (ENTER para pular)"

    # Session type
    Write-Host ""
    Write-Host "  Tipo de sessao:" -ForegroundColor Gray
    Write-Host "  [1] meeting  [2] presentation  [3] technical" -ForegroundColor DarkGray
    Write-Host "  [4] casual   [5] negotiation   [6] interview  [ENTER] pular" -ForegroundColor DarkGray
    $typeMap = @{ "1"="meeting"; "2"="presentation"; "3"="technical"; "4"="casual"; "5"="negotiation"; "6"="interview" }
    $typeInput = Read-Host "  Escolha (1-6 ou ENTER)"
    $topic_type = if ($typeMap.ContainsKey($typeInput)) { $typeMap[$typeInput] } else { "" }
    if ($topic_type -ne "") { Write-Host "  Tipo: $topic_type" -ForegroundColor Yellow }

    $date_str   = Get-Date -Format "yyyy-MM-dd"
    $time_str   = Get-Date -Format "HH-mm"
    $trans_file = Join-Path $SCRIPT_DIR "transcript_en_${date_str}_${time_str}.txt"

    Write-Host ""
    Write-Host "  [REC] Gravando em ingles..." -ForegroundColor Red
    Write-Host "  [REC] Feche a janela Python (Ctrl+C nela) para parar." -ForegroundColor Red
    Write-Host ""

    $py_script = Join-Path $SCRIPT_DIR "record.py"
    $proc = Start-Process -FilePath $PYTHON `
        -ArgumentList "`"$py_script`" --language en --output `"$trans_file`"" `
        -PassThru `
        -WindowStyle Normal
    $proc.WaitForExit()

    if (-not (Test-Path $trans_file)) {
        Write-Host "  [ERROR] Transcript nao encontrado: $trans_file" -ForegroundColor Red
        Read-Host "  ENTER para sair"; return
    }

    $size = (Get-Item $trans_file).Length
    if ($size -lt 10) {
        Write-Host "  [ERROR] Transcript vazio." -ForegroundColor Red
        Remove-Item $trans_file -Force
        Read-Host "  ENTER para sair"; return
    }

    Write-Host "  [OK] Transcript gerado. Avaliando com Claude..." -ForegroundColor Green
    Write-Host ""

    $coach_py = Join-Path $SCRIPT_DIR "coach.py"
    $coach_args = @("--transcript", $trans_file)
    if ($topic -ne "") { $coach_args += "--topic"; $coach_args += $topic }
    if ($topic_type -ne "") { $coach_args += "--topic-type"; $coach_args += $topic_type }

    & $PYTHON $coach_py @coach_args
    $coachExit = $LASTEXITCODE

    if ($coachExit -ne 0) {
        Write-Host "  [ERROR] coach.py falhou (exit $coachExit). Transcript mantido em:" -ForegroundColor Red
        Write-Host "  $trans_file" -ForegroundColor Yellow
        Read-Host "  ENTER para sair"; return
    }

    # Limpar transcript temporario somente apos sucesso
    if (Test-Path $trans_file) { Remove-Item $trans_file -Force }

    Write-Host ""
    Write-Host "  Sessao salva no vault: Areas/English-Learning/sessions/" -ForegroundColor DarkCyan
    Write-Host "  Progresso acumulado:   Areas/English-Learning/progress.md" -ForegroundColor DarkCyan
    Write-Host ""
    Read-Host "  ENTER para sair"
}

function Invoke-ManagerCall {
    # 1. Select manager
    $names   = @($MANAGERS | ForEach-Object { $_["Name"] })
    $idx     = Show-Menu -Title "Com qual gestor e a call?" -Options $names
    $manager = $MANAGERS[$idx]

    Write-Host "  -> $($manager["Name"])" -ForegroundColor Green

    # 2. Recording
    $date_str   = Get-Date -Format "yyyy-MM-dd"
    $time_str   = Get-Date -Format "HH-mm"
    $trans_dir  = Join-Path $SCRIPT_DIR "transcripts"
    $trans_file = Join-Path $trans_dir "${date_str}_${time_str}_$($manager["Folder"]).txt"

    New-Item -ItemType Directory -Force -Path $trans_dir | Out-Null

    Write-Host ""
    Write-Host "  [REC] Gravando call com $($manager["Name"])..." -ForegroundColor Red
    Write-Host "  [REC] Feche a janela Python (Ctrl+C nela) para parar." -ForegroundColor Red
    Write-Host ""

    # Detect call language BEFORE recording so Whisper uses the right model
    $lang_ans  = Read-Host "  Was this call in English? (S/n)"
    $lang_flag = if ($lang_ans -match '^[nN]$') { "pt" } else { "en" }

    $py_script = Join-Path $SCRIPT_DIR "record.py"
    $proc = Start-Process -FilePath $PYTHON `
        -ArgumentList "`"$py_script`" --language $lang_flag --output `"$trans_file`"" `
        -PassThru `
        -WindowStyle Normal

    Write-Host "  [INFO] Aguardando Python encerrar..." -ForegroundColor Yellow
    $proc.WaitForExit()
    $recExit = $proc.ExitCode
    if ($recExit -ne 0) {
        Write-Host "  [ERROR] record.py encerrou com erro (exit $recExit). Transcript pode estar incompleto." -ForegroundColor Red
        Read-Host "  ENTER para sair"; return
    }

    if (-not (Test-Path $trans_file)) {
        Write-Host "  [ERROR] Transcricao nao encontrada: $trans_file" -ForegroundColor Red
        Read-Host "  ENTER para sair"
        return
    }

    $size = (Get-Item $trans_file).Length
    if ($size -lt 10) {
        Write-Host "  [ERROR] Transcript vazio ou muito curto." -ForegroundColor Red
        Remove-Item $trans_file -Force
        Read-Host "  ENTER para sair"; return
    }

    $chars = (Get-Item $trans_file).Length
    Write-Host "  [OK] Transcricao gerada ($chars bytes) — idioma: $lang_flag" -ForegroundColor Green

    # 3. Processar com Ollama (process.py)

    $process_py = Join-Path $SCRIPT_DIR "process.py"
    & $PYTHON $process_py manager --manager $manager["Folder"] --transcript $trans_file --date $date_str --lang $lang_flag
    $procExit = $LASTEXITCODE

    if ($procExit -ne 0) {
        Write-Host "  [ERROR] process.py falhou (exit $procExit). Transcript mantido em:" -ForegroundColor Red
        Write-Host "  $trans_file" -ForegroundColor Yellow
        Read-Host "  ENTER para sair"; return
    }

    Write-Host ""
    Write-Host "  Sessao salva no vault." -ForegroundColor DarkCyan
    Write-Host ""
    Read-Host "  ENTER para sair"
}

# ===============================================================
# FLUXO PRINCIPAL
# ===============================================================

Clear-Host
Write-Host ""
Write-Host "  ================================" -ForegroundColor DarkCyan
Write-Host "      Call Recorder -- KO         " -ForegroundColor DarkCyan
Write-Host "  ================================" -ForegroundColor DarkCyan

# Limpeza silenciosa de arquivos antigos
Remove-OldTranscripts

# 0. Selecionar modo
$modeIdx = Show-Menu -Title "O que voce quer fazer?" -Options @("1on1 com time", "English Coach", "Call com Gestor")

if ($modeIdx -eq 1) {
    Invoke-EnglishCoach
    exit 0
}

if ($modeIdx -eq 2) {
    Invoke-ManagerCall
    exit 0
}

# 1. Selecionar pessoa
$names  = @($PEOPLE | ForEach-Object { $_["Name"] })
$idx    = Show-Menu -Title "Com quem e a call?" -Options $names
$person = $PEOPLE[$idx]

Write-Host "  -> $($person["Name"])" -ForegroundColor Green

# 2. Tipo de reuniao
$typeIdx   = Show-Menu -Title "Tipo de reuniao" -Options @("Regular (pauta livre)", "Estruturada (mensal)")
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
} else {
    $ans = Read-Host "  Quer sugestao de pauta para 20min? (s/n)"
    if ($ans -eq "s") {
        $process_py = Join-Path $SCRIPT_DIR "process.py"
        & $PYTHON $process_py agenda --person $person["Folder"]
        Write-Host ""
        Read-Host "  Pressione ENTER quando pronto para gravar"
    }
}

# 3. Gravacao
$date_str   = Get-Date -Format "yyyy-MM-dd"
$time_str   = Get-Date -Format "HH-mm"
$trans_dir  = Join-Path $SCRIPT_DIR "transcripts"
$trans_file = Join-Path $trans_dir "${date_str}_${time_str}_$($person["Folder"]).txt"

New-Item -ItemType Directory -Force -Path $trans_dir | Out-Null

Write-Host ""
Write-Host "  [REC] Gravando para $($person["Name"])..." -ForegroundColor Red
Write-Host "  [REC] Feche a janela Python (Ctrl+C nela) para parar." -ForegroundColor Red
Write-Host ""

# Inicia Python em janela separada (Ctrl+C nao mata este script)
$py_script = Join-Path $SCRIPT_DIR "record.py"
$proc = Start-Process -FilePath $PYTHON `
    -ArgumentList "`"$py_script`" --output `"$trans_file`"" `
    -PassThru `
    -WindowStyle Normal

Write-Host "  [INFO] Aguardando Python encerrar..." -ForegroundColor Yellow
$proc.WaitForExit()
$recExit = $proc.ExitCode
if ($recExit -ne 0) {
    Write-Host "  [ERROR] record.py encerrou com erro (exit $recExit). Transcript pode estar incompleto." -ForegroundColor Red
    Read-Host "  ENTER para sair"; exit 1
}

if (-not (Test-Path $trans_file)) {
    Write-Host "  [ERROR] Transcricao nao encontrada: $trans_file" -ForegroundColor Red
    Read-Host "  ENTER para sair"
    exit 1
}

$size = (Get-Item $trans_file).Length
if ($size -lt 10) {
    Write-Host "  [ERROR] Transcript vazio ou muito curto." -ForegroundColor Red
    Remove-Item $trans_file -Force
    Read-Host "  ENTER para sair"; exit 1
}

$chars = (Get-Item $trans_file).Length
Write-Host "  [OK] Transcricao gerada ($chars bytes)" -ForegroundColor Green

# 4. Processar com Ollama (process.py)
Write-Host ""
Write-Host "  [Ollama] Processando transcricao..." -ForegroundColor Yellow
Write-Host ""

$lang_ans = Read-Host "  Was this call in English? (s/N)"
$lang_flag = if ($lang_ans -match '^[sS]$') { "en" } else { "pt" }

$process_py   = Join-Path $SCRIPT_DIR "process.py"
$process_args = @("transcript", "--person", $person["Folder"], "--transcript", $trans_file, "--date", $date_str, "--lang", $lang_flag)
if ($structured) { $process_args += "--structured" }
& $PYTHON $process_py @process_args
$procExit = $LASTEXITCODE

if ($procExit -ne 0) {
    Write-Host "  [ERROR] process.py falhou (exit $procExit). Transcript mantido em:" -ForegroundColor Red
    Write-Host "  $trans_file" -ForegroundColor Yellow
    Read-Host "  ENTER para sair"; exit 1
}

Write-Host ""
Write-Host "  Sessao salva no vault." -ForegroundColor DarkCyan
Write-Host ""
Read-Host "  ENTER para sair"
