# english-coach.ps1 — English practice session with AI evaluation
# Usage: .\english-coach.ps1 [-Topic "your topic"]
# Requires: Ollama running locally (qwen2.5-coder) + Python with faster-whisper
# No API keys — fully local (Whisper for transcription, Ollama for evaluation).

param(
    [string]$Topic = ""
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$Venv       = "$env:USERPROFILE\techcolab-backlog\call-recorder\.venv"
$Python     = if (Test-Path "$Venv\Scripts\python.exe") { "$Venv\Scripts\python.exe" } else { "python" }
$RecordPy   = "$ScriptDir\record.py"
$CoachPy    = "$ScriptDir\coach.py"

# ── Banner ────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  ╔══════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "  ║        ENGLISH COACH  (AI-powered)       ║" -ForegroundColor Cyan
Write-Host "  ╚══════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Speak freely in English. The session will be recorded," -ForegroundColor Gray
Write-Host "  transcribed by Whisper, and evaluated by Claude." -ForegroundColor Gray
Write-Host ""

if ($Topic -eq "") {
    $Topic = Read-Host "  Topic / context (press Enter to skip)"
}

if ($Topic -ne "") {
    Write-Host "  Topic: $Topic" -ForegroundColor Yellow
}

# Session type selection
Write-Host ""
Write-Host "  Session type:" -ForegroundColor Gray
Write-Host "  [1] meeting  [2] presentation  [3] technical" -ForegroundColor DarkGray
Write-Host "  [4] casual   [5] negotiation   [6] interview  [Enter] skip" -ForegroundColor DarkGray
$typeMap = @{ "1"="meeting"; "2"="presentation"; "3"="technical"; "4"="casual"; "5"="negotiation"; "6"="interview" }
$typeInput = Read-Host "  Choose (1-6 or Enter)"
$TopicType = if ($typeMap.ContainsKey($typeInput)) { $typeMap[$typeInput] } else { "" }
if ($TopicType -ne "") {
    Write-Host "  Type: $TopicType" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "  Press Enter to start recording. Press Ctrl+C to stop." -ForegroundColor Green
Read-Host | Out-Null

# ── Record ────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  [REC] Recording in English... (Ctrl+C to stop)" -ForegroundColor Red

$Timestamp    = Get-Date -Format "yyyy-MM-dd_HH-mm"
$TranscriptFile = "$ScriptDir\transcript_en_$Timestamp.txt"

try {
    & $Python $RecordPy --language en --output $TranscriptFile
} catch {
    Write-Host "  [ERROR] Recording failed: $_" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $TranscriptFile)) {
    Write-Host "  [ERROR] Transcript file not created." -ForegroundColor Red
    exit 1
}

$TranscriptSize = (Get-Item $TranscriptFile).Length
if ($TranscriptSize -lt 10) {
    Write-Host "  [ERROR] Transcript appears empty." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "  [OK] Transcript saved: $TranscriptFile" -ForegroundColor Green

# ── Evaluate ─────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  [AI] Evaluating with Ollama (qwen2.5-coder)..." -ForegroundColor Cyan

$CoachArgs = @("--transcript", $TranscriptFile)
if ($Topic -ne "") {
    $CoachArgs += "--topic"
    $CoachArgs += $Topic
}
if ($TopicType -ne "") {
    $CoachArgs += "--topic-type"
    $CoachArgs += $TopicType
}

try {
    $CoachOutput = & $Python $CoachPy @CoachArgs
    Write-Host $CoachOutput
} catch {
    Write-Host "  [ERROR] Coach evaluation failed: $_" -ForegroundColor Red
    exit 1
}

# ── Done ──────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  Session complete. Check your Obsidian vault:" -ForegroundColor Cyan
Write-Host "  Areas/English-Learning/sessions/" -ForegroundColor Gray
Write-Host "  Areas/English-Learning/progress.md" -ForegroundColor Gray
Write-Host ""

# Clean up temp transcript (vault already has the full session note)
if (Test-Path $TranscriptFile) {
    Remove-Item $TranscriptFile -Force
}
