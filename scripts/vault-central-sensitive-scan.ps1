# Sensitive-content scan for the D&A team central vault (10_2ndBrain).
# Companion to vault-central-consolidation-agent.ps1.
#
# NOT report-only since 2026-08-29, on Kelvin's explicit instruction: a file with a
# NEW finding is pulled out of the shared vault IMMEDIATELY (moved to a quarantine
# folder off SharePoint, content fully preserved) and only returns after his review.
# The 08:15 consolidation agent will flag these removals - that is the audit trail,
# not a malfunction. SharePoint version history still holds the old content; full
# cleanup of a real leak also needs the version history handled manually.
#
# Why it exists (2026-08-29): a manual sweep found that an exclusion note in
# okr-ownership-roster.md had leaked the very confidential fact it was excluding.
# This scan looks for compensation/HR terms, money amounts, secrets, and
# confidentiality markers in a vault shared with the whole team, and reports
# anything NEW against a reviewed baseline.
#
# Baseline model: every finding gets a stable key (file + pattern group + line
# content hash). Findings already in the baseline file are "known" (reviewed as
# benign). Since 2026-09-04 the confidentiality check is split in two: 'confid' for
# phrases that always mean secrecy, 'confid-mark' for the classification word used as
# an actual marking, so a governance document that only names the levels no longer
# needs a baseline entry.
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
    # Split on 2026-09-04 (P-072). The old single 'confid' group matched the bare word
    # "confidential" anywhere on a line, so it could not tell a document that IS marked
    # secret from one that WRITES ABOUT the classification scheme. Every DG document
    # naming Public / Internal / Confidential / Restricted was quarantined, and the
    # workaround was re-running -UpdateBaseline for each new one.
    #   confid      - phrases that are an instruction whatever the surrounding text.
    #   confid-mark - the classification word ONLY in a marking construction: a label
    #                 ("Classification: Confidential"), an assertion ("X is confidential"),
    #                 an imperative ("treat as confidential"), or a line that is nothing
    #                 but the word. Naming the level in a list, a table row or a glossary
    #                 definition no longer matches.
    @{ Name = "confid";      SkipLongLines = $true;  Regex = 'n(a|\u00e3)o verbalizad|ainda n(a|\u00e3)o (foi )?anunciad|n(a|\u00e3)o compartilhar|do not share|internal only' },
    @{ Name = "confid-mark"; SkipLongLines = $true;  Regex = '^\W{0,6}(confidential|confidencial)\W{0,6}$|(classification|sensitivity|classifica(c|\u00e7)(a|\u00e3)o|sigilo|n(i|\u00ed)vel)\s*[:=]\s*\W{0,4}(confidential|confidencial)|(strictly|highly|estritamente|altamente)\s+(confidential|confidencial)|\b(is|are|was|were|\u00e9|s\u00e3o|era|eram)\s+(strictly\s+|highly\s+|estritamente\s+|altamente\s+)?(confidential|confidencial)\b|(treat|keep|mark|marked|tratar|manter)\s+\S*\s*(as|como)\s+(confidential|confidencial)|(confidential|confidencial)\s+(and|e)\s+proprietary' }
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

# --- Quarantine (Kelvin's instruction, 2026-08-29): any file with a NEW finding is
# moved out of the shared vault immediately. It comes back only after his review -
# the report below carries a ready-to-paste restore command per file.
# Skipped under -UpdateBaseline: that run IS the review (he is accepting findings).
# .NET IO calls throughout because vault folder names contain [brackets].
$quarantineRoot = "C:\Users\Kelvin.okuda\VaultBackups\10_2ndBrain-quarantine"
$quarantineLog = Join-Path $reportDir "sensitive-quarantine-log.md"
$quarantined = @()
$quarantineFailed = @()
if (-not $UpdateBaseline -and $newFindings.Count -gt 0) {
    $filesToPull = @($newFindings | ForEach-Object { $_.File } | Sort-Object -Unique)
    foreach ($rel in $filesToPull) {
        $src = Join-Path $vaultPath $rel
        $dst = Join-Path (Join-Path $quarantineRoot $today) $rel
        try {
            [System.IO.Directory]::CreateDirectory([System.IO.Path]::GetDirectoryName($dst)) | Out-Null
            if ([System.IO.File]::Exists($dst)) { $dst = "$dst.$((Get-Date).ToString('HHmmss'))" }
            [System.IO.File]::Move($src, $dst)
            $quarantined += New-Object PSObject -Property @{ File = $rel; Dest = $dst }
        } catch {
            $quarantineFailed += New-Object PSObject -Property @{ File = $rel; Error = $_.Exception.Message }
        }
    }
    if ($quarantined.Count -gt 0 -or $quarantineFailed.Count -gt 0) {
        $logLines = @("## $((Get-Date).ToString('yyyy-MM-dd HH:mm')) - $($quarantined.Count) file(s) quarantined")
        foreach ($q in $quarantined) { $logLines += "- ``$($q.File)`` -> ``$($q.Dest)``" }
        foreach ($q in $quarantineFailed) { $logLines += "- FAILED to quarantine ``$($q.File)``: $($q.Error)" }
        $logLines += ""
        Add-Content -Path $quarantineLog -Value ($logLines -join "`r`n") -Encoding utf8
    }
}

# Baseline update is an explicit, manual act - after a human reviewed the report.
if ($UpdateBaseline) {
    $allKeys = @($findings | ForEach-Object { $_.Key } | Sort-Object -Unique)
    ConvertTo-Json $allKeys | Set-Content -Path $baselinePath -Encoding UTF8
}

# --- Report ---
$r = New-Object System.Collections.Generic.List[string]
$r.Add("# Vault Central Sensitive Scan - $today")
$r.Add("")
$r.Add("Scanned $($files.Count) text files in ``10_2ndBrain`` against $($patternGroups.Count) pattern groups ($($patternGroups.Name -join ' / ')).")
$r.Add("Baseline: $($baseline.Count) reviewed-as-benign findings.")
$r.Add("")

if ($newFindings.Count -eq 0) {
    $r.Add("## Result: OK - no new findings")
    $r.Add("")
    $r.Add("$($knownFindings.Count) known (baselined) matches, nothing new since the last reviewed baseline.")
    $todayQuarantine = Join-Path $quarantineRoot $today
    if ([System.IO.Directory]::Exists($todayQuarantine)) {
        $r.Add("")
        $r.Add("NOTE: files were quarantined earlier today and may still be pending your review - see ``sensitive-quarantine-log.md``.")
    }
} else {
    $r.Add("## Result: ATTENTION - $($newFindings.Count) NEW finding(s)")
    $r.Add("")
    $r.Add("Files with new findings were PULLED FROM THE VAULT (quarantine, content preserved). Review each: if benign, restore with the command below and re-run with ``-UpdateBaseline`` to accept; if sensitive, edit the quarantined copy and restore only the clean version (SharePoint version history still keeps old versions - handle it there too).")
    $r.Add("")
    $r.Add("| Group | File | Line | Excerpt |")
    $r.Add("|---|---|---|---|")
    foreach ($f in ($newFindings | Sort-Object Group, File, Line)) {
        $safeExcerpt = $f.Excerpt -replace '\|', '\|'
        $r.Add("| $($f.Group) | $($f.File) | $($f.Line) | $safeExcerpt |")
    }
    $r.Add("")
    if ($quarantined.Count -gt 0) {
        $r.Add("### Quarantined - restore after review")
        $r.Add("")
        foreach ($q in $quarantined) {
            $restoreDst = Join-Path $vaultPath $q.File
            $r.Add("- ``$($q.File)``")
            $r.Add('  ```powershell')
            $r.Add("  [System.IO.File]::Move(`"$($q.Dest)`", `"$restoreDst`")")
            $r.Add('  ```')
        }
        $r.Add("")
    }
    if ($quarantineFailed.Count -gt 0) {
        $r.Add("### Quarantine FAILED (file still in the vault - handle manually)")
        $r.Add("")
        foreach ($q in $quarantineFailed) {
            $r.Add("- ``$($q.File)``: $($q.Error)")
        }
        $r.Add("")
    }
    $r.Add("Known (baselined) matches: $($knownFindings.Count).")
}

if ($UpdateBaseline) {
    $r.Add("")
    $r.Add("Baseline UPDATED this run: all $($findings.Count) current matches accepted as reviewed.")
}

$r.Add("")
$r.Add("---")
$r.Add("Generated by ``scripts/vault-central-sensitive-scan.ps1`` (techcolab-backlog). Scheduled task: D&A Vault Central Sensitive Scan, hourly 08:25-18:25.")

Set-Content -Path $reportPath -Value ($r -join "`r`n") -Encoding utf8

if ($newFindings.Count -gt 0) { exit 3 } else { exit 0 }

} catch {
    $msg = "$($_.Exception.Message)`nAt line $($_.InvocationInfo.ScriptLineNumber): $($_.InvocationInfo.Line)"
    Set-Content -Path $reportPath -Value "# Vault Central Sensitive Scan - $today`n`nERROR: scan crashed before completing.`n`n``````
$msg
``````" -Encoding utf8
    exit 1
}
