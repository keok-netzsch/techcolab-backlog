<#
.SYNOPSIS
    Idempotent entry point for the Streamlit app. Always ends at http://localhost:8501
    or says out loud why it could not.

.DESCRIPTION
    The old flow was blind: start_app.bat ran `streamlit run` with no checks, and
    start_silent.vbs opened the browser after a fixed 5-second sleep. Two failures
    came out of that, and both looked to Kelvin like "the address changed":

      1. A wedged process keeps holding 8501. The port answers, so nothing looks
         broken, but the app serves a half-rendered page and the nav does nothing.
         Starting again does not help — the old process still owns the port.
         (2026-09-01: PID 27044 sat wedged for two hours in exactly this state.)
      2. The browser opened before the server was ready, so the first load failed
         and a reload was needed — on a slow start, every time.

    This script decides instead of guessing:
      - healthy on 8501            -> just open the browser, do not restart
      - port held but not healthy  -> kill that process, start fresh
      - port free                  -> start
    and it opens the browser only after /_stcore/health answers 200.

    The port is fixed on purpose. Streamlit can drift to the next free port when
    the requested one is busy, which produces a URL nobody bookmarked. Here a port
    that cannot be freed is an error with a message, never a silent move.

.PARAMETER Port
    Port to bind. Default 8501 — the address in every shortcut, the Raycast
    launcher and start_silent.vbs.

.PARAMETER NoBrowser
    Start (or verify) the server without opening a browser window.

.PARAMETER TimeoutSeconds
    How long to wait for the server to become healthy before failing loudly.
#>
[CmdletBinding()]
param(
    [int]$Port = 8501,
    [switch]$NoBrowser,
    [int]$TimeoutSeconds = 60
)

$ErrorActionPreference = 'Stop'
$Root      = Split-Path -Parent $PSScriptRoot
# Two logs on purpose: the running Streamlit process holds streamlit.log open, so
# the launcher cannot append to it while the app is up (found on the first run).
$LogFile   = Join-Path $Root 'streamlit.log'          # the app's own output
$StartLog  = Join-Path $Root 'logs\start-app.log'     # this script's decisions
$HealthUrl = "http://localhost:$Port/_stcore/health"
$AppUrl    = "http://localhost:$Port"

function Write-Step($msg) {
    $line = "[start-app $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $msg"
    Write-Output $line
    # Logging must never be what breaks the launcher.
    try {
        $dir = Split-Path -Parent $StartLog
        if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
        Add-Content -Path $StartLog -Value $line -Encoding utf8 -ErrorAction Stop
    } catch { }
}

function Test-AppHealthy {
    # Streamlit answers 200 "ok" on /_stcore/health only once it is actually
    # serving. A listening socket is not enough — that is what a wedged process
    # still has.
    try {
        $r = Invoke-WebRequest -Uri $HealthUrl -UseBasicParsing -TimeoutSec 3
        return ($r.StatusCode -eq 200)
    } catch {
        return $false
    }
}

function Get-PortOwner {
    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
            Select-Object -First 1
    if (-not $conn) { return $null }
    return Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
}

function Show-Failure($msg) {
    # Pattern 5 (ARCHITECTURE.md): a failure must look like a failure. This runs
    # from a hidden shortcut, so stderr alone would be swallowed.
    Write-Step "FAILED: $msg"
    try {
        Add-Type -AssemblyName System.Windows.Forms
        [System.Windows.Forms.MessageBox]::Show(
            "$msg`n`nLog: $StartLog", 'Personal Toolkit - could not start',
            'OK', 'Error') | Out-Null
    } catch { }
}

# ── 1. Already up and healthy? Then there is nothing to do. ───────────────────
if (Test-AppHealthy) {
    $owner = Get-PortOwner
    Write-Step "already healthy on $Port (PID $($owner.Id), up since $($owner.StartTime)) - reusing"
    if (-not $NoBrowser) { Start-Process $AppUrl }
    exit 0
}

# ── 2. Port held by something that is not answering: clear it. ────────────────
$owner = Get-PortOwner
if ($owner) {
    Write-Step "port $Port held by $($owner.ProcessName) PID $($owner.Id) (since $($owner.StartTime)) but not healthy - killing it"
    try {
        Stop-Process -Id $owner.Id -Force
    } catch {
        Show-Failure "Port $Port is held by $($owner.ProcessName) (PID $($owner.Id)) and it could not be stopped: $($_.Exception.Message)"
        exit 1
    }
    for ($i = 0; $i -lt 10 -and (Get-PortOwner); $i++) { Start-Sleep -Milliseconds 300 }
    if (Get-PortOwner) {
        Show-Failure "Port $Port is still held after killing PID $($owner.Id). Nothing was started - the app would otherwise land on a different port."
        exit 1
    }
    Write-Step "port $Port freed"
}

# ── 3. Environment, same as the old start_app.bat provided. ───────────────────
if (-not $env:TECHCOLAB_VAULT) {
    $env:TECHCOLAB_VAULT = Join-Path $HOME 'OneDrive - NETZSCH\Documents\TechColab_D&A_KO\App\Personal toolkit'
    Write-Step "TECHCOLAB_VAULT not inherited - using default"
}
if (-not $env:NETZSCH_LLM_API_KEY) {
    # An Explorer session started before the user env var existed does not have it.
    try {
        $fromReg = (Get-ItemProperty -Path 'HKCU:\Environment' -Name NETZSCH_LLM_API_KEY -ErrorAction Stop).NETZSCH_LLM_API_KEY
        if ($fromReg) { $env:NETZSCH_LLM_API_KEY = $fromReg; Write-Step 'NETZSCH_LLM_API_KEY read from registry' }
    } catch { }
}

# ── 4. Start it. ──────────────────────────────────────────────────────────────
$python = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    $python = 'python'
    Write-Step 'no .venv - falling back to system python'
}

# Start-Process redirection truncates, while the old start_app.bat appended with
# ">>". Rotating instead of truncating keeps the previous run readable without the
# log growing without bound (it was already 250k+ lines of deprecation warnings).
if (Test-Path $LogFile) {
    for ($i = 2; $i -ge 1; $i--) {
        $src = if ($i -eq 1) { $LogFile } else { "$LogFile.$($i-1)" }
        if (Test-Path $src) { Move-Item -Path $src -Destination "$LogFile.$i" -Force -ErrorAction SilentlyContinue }
    }
}

Write-Step "starting streamlit on $Port"
$args = @('-m', 'streamlit', 'run', (Join-Path $Root 'app.py'),
          '--server.port', $Port, '--server.headless', 'true')
Start-Process -FilePath $python -ArgumentList $args -WorkingDirectory $Root `
              -WindowStyle Hidden `
              -RedirectStandardOutput $LogFile -RedirectStandardError "$LogFile.err"

# ── 5. Wait for health, then open the browser. Never a blind sleep. ───────────
$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
while ((Get-Date) -lt $deadline) {
    if (Test-AppHealthy) {
        $owner = Get-PortOwner
        Write-Step "healthy on $Port (PID $($owner.Id))"
        if (-not $NoBrowser) { Start-Process $AppUrl }
        exit 0
    }
    Start-Sleep -Milliseconds 500
}

Show-Failure "The app did not become healthy on port $Port within $TimeoutSeconds seconds."
exit 1
