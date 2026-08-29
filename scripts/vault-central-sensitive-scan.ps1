# Daily sensitive-content scan for the D&A team central vault (10_2ndBrain).
# Report-only - never writes to, edits, or deletes anything inside the central vault.
# Companion to vault-central-consolidation-agent.ps1 (same read-only design).
#
# Why it exists (2026-08-29): a manual sweep found that an exclusion note in
# okr-ownership-roster.md had leaked the very confidential fact it was excluding.
# This scan looks for compensation/HR terms, money amounts, secrets, and
# confidentiality markers in a vault shared with the whole team, and reports
# anything NEW against a reviewed baseline.
#
# Baseline model: every finding gets a stable key (file + pattern group + line
# content hash). Findings already in the baseline file are "known" (reviewed as
# benign, e.g. DAMA governance docs legitimately containing "confidential").
# Only NEW findings are surfaced prominently. The baseline is NEVER updated
# automatically - run manually with -UpdateBaseline after reviewing a report:
#   powershell -File vault-central-sensitive-scan.ps1 -UpdateBaseline
#
# PowerShell 5.1 compatible. ASCII-only source: accented chars in patterns use
# .NET regex \uXXXX escapes so the script has no encoding dependency.

param(
    [switch]$UpdateBaseline
)

$ErrorActionPreference = "Stop"

$vaultPath = "C:\Users\Kelvin.okuda\NETZSCH\Business Intelligence & Analytics - General\02_Organization\10_2ndBrain"
$baselinePath = "C:\Users\Kelvin.okuda\techcolab-backlog\scripts\vault-central-sensitive-baseline.json"
$reportDir = "C:\Users\Kelvin.okuda\OneDrive - NETZSCH\Documents\TechColab_D&A_KO\AI\vault-central-reports"
$today = Get-Date -Format "yyyy-MM-dd"
$reportPath = Join-Path $reportDir "$today-sensitive-scan.md"

# File types to scan (text content). .obsidian is app state, not vault content.
$textExtensions = @(".md", ".txt", ".html", ".htm", ".json", ".js", ".css", ".csv", ".yml", ".yaml", ".xml")

# Pattern groups. SkipLongLines avoids base64 blobs in HTML build artifacts
# triggering fuzzy word matches; secret patterns always scan every line.
$patternGroups = @(
    @{ Name = "comp";    SkipLongLines = $true;  Regex = 'sal(a|\u00e1)rio|salar(y|ies)|remunera|compensation|b(o|\u00f4)nus|\bbonus\b|\bmerit\b|m(e|\u00e9)rito' },
    @{ Name = "money";   SkipLongLines = $true;  Regex = 'R\$ ?\d|\u20ac ?\d|\bEUR ?\d{3}' },
    @{ Name = "hr";      SkipLongLines = $true;  Regex = 'avalia(c|\u00e7)(a|\u00e3)o de desempenho|performance review|performance evaluation|devolutiva|\bPDI\b|\b9[ -]?box\b|promo(c|\u00e7)(a|\u00e3)o\b|\bpromotion\b|headcount|demiss|dismissal|\btermination\b' },
    @{ Name = "secret";  SkipLongLines = $false; Regex = 'api[_ -]?key\s*[:=]|password\s*[:=]|senha\s*[:=]|\bsk-[A-Za-z0-9]{10,}|ghp_[A-Za-z0-9]{10,}|xoxb-[A-Za-z0-9-]{10,}|Bearer [A-Za-z0-9._\-]{15,}|AKIA[0-9A-Z]{16}' },
    @{ Name = "confid";  SkipLongLines = $true;  Regex = 'confidencial|confidential|n(a|\u00e3)o verbalizad|ainda n(a|\u00e3)o (foi )?anunciad|n(a|\u00e3)o compartilhar|do not share|internal only' }
)
$longLineThreshold = 800
$excerptMax = 200

if (-not (Test-Path $reportDir)) {
    New-Item -ItemType Directory -Path $reportDir -Force | Out-Null
}

if (-not (Test-Path $vaultPath)) {
    Set-Content -Path $reportPath -Value "# Vault Central Sensitive Scan - $today`n`nERROR: central vault path not found at $vaultPath. OneDrive may not be synced. No scan performed." -Encoding utf8
    exit 1
}

# Same rationale as the consolidation agent: a safety scan that dies silently is
# worse than one that reports its own failure.
try {

$sha1 = [System.Security.Cryptography.SHA1]::Create()
function Get-FindingKey([string]$text) {
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($text)
    return ([System.BitConverter]::ToString($sha1.ComputeHash($bytes)) -replace "-", "").Substring(0, 16)
}

# Load baseline (known, reviewed-as-benign finding keys)
$baseline = @{}
if (Test-Path $baselinePath) {
    $raw = Get-Content $baselinePath -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach ($k in $raw) { $baseline[$k] = $true }
}

$files = Get-ChildItem $vaultPath -Recurse -File | Where-Object {
    $textExtensions -contains $_.Extension.ToLower() -and
    $_.FullName.Substring($vaultPath.Length) -notmatch '\\\.obsidian\\'
}

$findings = @()
foreach ($file in $files) {
    $relPath = $file.FullName.Substring($vaultPath.Length + 1)
    # -LiteralPath: vault folder names contain [brackets] (e.g. "OKR 04 - [declinado]"),
    # which Get-Content would otherwise expand as wildcards and fail to bind -Encoding.
    $lines = Get-Content -LiteralPath $file.FullName -Encoding UTF8 -ErrorAction SilentlyContinue
    if ($null -eq $lines) { continue }
    $lineNo = 0
    foreach ($line in $lines) {
        $lineNo++
        foreach ($group in $patternGroups) {
            if ($group.SkipLongLines -and $line.Length -gt $longLineThreshold) { continue }
            if ($line -match $group.Regex) {
                $trimmed = $line.Trim()
                if ($trimmed.Length -gt $excerptMax) { $trimmed = $trimmed.Substring(0, $excerptMax) }
                $key = Get-FindingKey "$relPath|$($group.Name)|$trimmed"
                $findings += New-Object PSObject -Property @{
                    Key = $key; File = $relPath; Line = $lineNo
                    Group = $group.Name; Excerpt = $trimmed
                    Known = $baseline.ContainsKey($key)
                }
            }
        }
    }
}

$newFindings = @($findings | Where-Object { -not $_.Known })
$knownFindings = @($findings | Where-Object { $_.Known })

# Baseline update is an explicit, manual act - after a human reviewed the report.
if ($UpdateBaseline) {
    $allKeys = @($findings | ForEach-Object { $_.Key } | Sort-Object -Unique)
    ConvertTo-Json $allKeys | Set-Content -Path $baselinePath -Encoding UTF8
}

# --- Report ---
$r = New-Object System.Collections.Generic.List[string]
$r.Add("# Vault Central Sensitive Scan - $today")
$r.Add("")
$r.Add("Scanned $($files.Count) text files in ``10_2ndBrain`` against $($patternGroups.Count) pattern groups (comp / money / hr / secret / confid).")
$r.Add("Baseline: $($baseline.Count) reviewed-as-benign findings. Read-only - nothing in the central vault was touched.")
$r.Add("")

if ($newFindings.Count -eq 0) {
    $r.Add("## Result: OK - no new findings")
    $r.Add("")
    $r.Add("$($knownFindings.Count) known (baselined) matches, nothing new since the last reviewed baseline.")
} else {
    $r.Add("## Result: ATTENTION - $($newFindings.Count) NEW finding(s)")
    $r.Add("")
    $r.Add("Review each one. If benign, re-run with ``-UpdateBaseline`` to accept; if sensitive, fix the file in the central vault (and remember SharePoint version history keeps old versions).")
    $r.Add("")
    $r.Add("| Group | File | Line | Excerpt |")
    $r.Add("|---|---|---|---|")
    foreach ($f in ($newFindings | Sort-Object Group, File, Line)) {
        $safeExcerpt = $f.Excerpt -replace '\|', '\|'
        $r.Add("| $($f.Group) | $($f.File) | $($f.Line) | $safeExcerpt |")
    }
    $r.Add("")
    $r.Add("Known (baselined) matches: $($knownFindings.Count).")
}

if ($UpdateBaseline) {
    $r.Add("")
    $r.Add("Baseline UPDATED this run: all $($findings.Count) current matches accepted as reviewed.")
}

$r.Add("")
$r.Add("---")
$r.Add("Generated by ``scripts/vault-central-sensitive-scan.ps1`` (techcolab-backlog). Scheduled task: D&A Vault Central Sensitive Scan, daily 08:25.")

Set-Content -Path $reportPath -Value ($r -join "`r`n") -Encoding utf8

if ($newFindings.Count -gt 0) { exit 3 } else { exit 0 }

} catch {
    $msg = "$($_.Exception.Message)`nAt line $($_.InvocationInfo.ScriptLineNumber): $($_.InvocationInfo.Line)"
    Set-Content -Path $reportPath -Value "# Vault Central Sensitive Scan - $today`n`nERROR: scan crashed before completing.`n`n``````
$msg
``````" -Encoding utf8
    exit 1
}
