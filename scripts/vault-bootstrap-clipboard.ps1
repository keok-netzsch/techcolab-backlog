# vault-bootstrap-clipboard.ps1
# Versão silenciosa do vault-bootstrap: copia o contexto direto para a área de transferência.
# Ativado pelo atalho Ctrl+Alt+B.
# Requer: Obsidian aberto com Local REST API ativo (porta 27124)

$API_BASE = "https://localhost:27124"
# Chave lida da variável de ambiente OBSIDIAN_API_KEY (nunca hardcode segredos).
$API_KEY  = $env:OBSIDIAN_API_KEY
if ([string]::IsNullOrWhiteSpace($API_KEY)) {
    $msg = "❌ OBSIDIAN_API_KEY não definida. Configure a variável de ambiente do usuário."
    $msg | Set-Clipboard
    Add-Type -AssemblyName System.Windows.Forms -ErrorAction SilentlyContinue
    [System.Windows.Forms.MessageBox]::Show($msg, "Vault Bootstrap", 0, 48) | Out-Null
    exit 1
}
$headers  = @{ "Authorization" = "Bearer $API_KEY" }

# Ignorar cert auto-assinado
try {
    Add-Type @"
using System.Net;
using System.Security.Cryptography.X509Certificates;
public class TrustAllCertsVBC : ICertificatePolicy {
    public bool CheckValidationResult(ServicePoint sp, X509Certificate cert, WebRequest req, int problem) { return true; }
}
"@ -ErrorAction Stop
    [System.Net.ServicePointManager]::CertificatePolicy = New-Object TrustAllCertsVBC
} catch {}

function Get-VaultNote([string]$Path) {
    try {
        $enc = [Uri]::EscapeUriString($Path)
        return Invoke-RestMethod -Uri "$API_BASE/vault/$enc" -Headers $headers -Method Get -TimeoutSec 4 -ErrorAction Stop
    } catch { return $null }
}
function Search-Vault([string]$Query, [int]$Ctx = 180) {
    try {
        $enc = [Uri]::EscapeDataString($Query)
        return Invoke-RestMethod -Uri "$API_BASE/search/simple/?query=$enc&contextLength=$Ctx" -Headers $headers -Method Get -TimeoutSec 4 -ErrorAction Stop
    } catch { return @() }
}

$today     = Get-Date -Format "yyyy-MM-dd"
$weekStart = (Get-Date).AddDays(-(Get-Date).DayOfWeek.value__ + 1).ToString("yyyy-MM-dd")
$lines     = [System.Collections.Generic.List[string]]::new()

# ── Verificar API ──────────────────────────────────────────────────────────────
try {
    Invoke-RestMethod -Uri "$API_BASE/" -Headers $headers -Method Get -TimeoutSec 3 -ErrorAction Stop | Out-Null
} catch {
    $msg = "❌ Obsidian não está respondendo. Abra o Obsidian e ative o plugin Local REST API."
    $msg | Set-Clipboard
    Add-Type -AssemblyName System.Windows.Forms -ErrorAction SilentlyContinue
    [System.Windows.Forms.MessageBox]::Show($msg, "Vault Bootstrap", 0, 48) | Out-Null
    exit 1
}

$lines.Add("# Vault Context — $today")
$lines.Add("_(gerado por vault-bootstrap-clipboard.ps1)_")
$lines.Add("")

# ── Última sessão ──────────────────────────────────────────────────────────────
$session = Get-VaultNote "App/Personal toolkit/AI/sessions/$today.md"
if (-not $session) {
    $yesterday = (Get-Date).AddDays(-1).ToString("yyyy-MM-dd")
    $session = Get-VaultNote "App/Personal toolkit/AI/sessions/$yesterday.md"
}
if ($session) {
    $preamble = ($session -split "`n") | Where-Object { $_ -match "^>" } | Select-Object -First 2
    $lines.Add("## Última sessão")
    $preamble | ForEach-Object { $lines.Add($_) }
    $lines.Add("")
}

# ── 1on1s da semana ───────────────────────────────────────────────────────────
$o3 = Search-Vault "1on1 $weekStart" -Ctx 120
if ($o3.Count -gt 0) {
    $lines.Add("## 1-on-1s desta semana")
    $o3 | Select-Object -First 4 | ForEach-Object { $lines.Add("- **$($_.filename):** $($_.context)") }
    $lines.Add("")
}

# ── Action items pendentes ────────────────────────────────────────────────────
$actions = Search-Vault "Action pending (Kelvin)" -Ctx 180
if ($actions.Count -gt 0) {
    $lines.Add("## Action items pendentes (Kelvin)")
    $actions | Select-Object -First 6 | ForEach-Object { $lines.Add("- **$($_.filename):** $($_.context)") }
    $lines.Add("")
}

# ── Backlog em desenvolvimento ────────────────────────────────────────────────
$indev = Search-Vault "status: em desenvolvimento" -Ctx 100
if ($indev.Count -gt 0) {
    $lines.Add("## Backlog em desenvolvimento")
    $indev | Select-Object -First 5 | ForEach-Object { $lines.Add("- $($_.filename)") }
    $lines.Add("")
}

# ── Performance FY26 ──────────────────────────────────────────────────────────
$carryover = Get-VaultNote "Team/FY26 - Assessment Observations Carryover.md"
if ($carryover) {
    $excerpt = ($carryover -split "`n") | Where-Object { $_ -match "^>" } | Select-Object -First 1
    $lines.Add("## Performance Assessment FY26")
    $lines.Add($excerpt)
    $lines.Add("")
}

# ── Team last contact ─────────────────────────────────────────────────────────
$lines.Add("## Team — último contato")
$cutoff = (Get-Date).AddDays(-7).ToString("yyyy-MM-dd")
@("Ana-Leite","Daniel-Lima","Lucas-Shizuno","Pedro-Klein","Pedro-Hennig") | ForEach-Object {
    $note = Get-VaultNote "Team/$_/Overview.md"
    if ($note) {
        $last = ($note -split "`n" | Where-Object { $_ -match "last-interaction:" } | Select-Object -First 1) -replace ".*last-interaction:\s*",""
        $flag = if ($last -and $last -lt $cutoff) { " ⚠️ overdue" } else { "" }
        $lines.Add("- $($_ -replace '-',' '): $last$flag")
    }
}
$lines.Add("")
$lines.Add("---")
$lines.Add("*Cole este bloco no início do chat como contexto de sessão.*")

# ── Copiar para clipboard ─────────────────────────────────────────────────────
$output = $lines -join "`n"
$output | Set-Clipboard

# Notificação toast (não bloqueia)
$notif = @"
$($output.Length) chars copiados para o clipboard.
Cole no início do chat Claude para restaurar contexto.
"@

Add-Type -AssemblyName System.Windows.Forms -ErrorAction SilentlyContinue
try {
    $balloon = New-Object System.Windows.Forms.NotifyIcon
    $balloon.Icon = [System.Drawing.SystemIcons]::Information
    $balloon.BalloonTipTitle = "Vault Bootstrap ✅"
    $balloon.BalloonTipText  = "Contexto copiado para o clipboard. Cole no chat Claude."
    $balloon.Visible = $true
    $balloon.ShowBalloonTip(3000)
    Start-Sleep -Milliseconds 3500
    $balloon.Dispose()
} catch {}
