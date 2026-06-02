# vault-bootstrap.ps1
# Consulta o vault Obsidian via Local REST API e gera contexto de sessão
# Uso: .\vault-bootstrap.ps1
# Uso com foco: .\vault-bootstrap.ps1 -Focus "performance"
#
# Requer: Obsidian aberto com o plugin obsidian-local-rest-api ativo
# API: https://localhost:27124 | porta insegura desativada

param(
    [string]$Focus = ""  # foco opcional: "team", "backlog", "performance", "governance"
)

# ─── Config ──────────────────────────────────────────────────────────────────
$API_BASE = "https://localhost:27124"
# Chave lida da variável de ambiente OBSIDIAN_API_KEY (nunca hardcode segredos).
# Defina uma vez (permanente):
#   [Environment]::SetEnvironmentVariable("OBSIDIAN_API_KEY", "<sua-chave>", "User")
$API_KEY  = $env:OBSIDIAN_API_KEY
if ([string]::IsNullOrWhiteSpace($API_KEY)) {
    Write-Host "❌ Variável de ambiente OBSIDIAN_API_KEY não definida." -ForegroundColor Red
    Write-Host "   Defina com: [Environment]::SetEnvironmentVariable('OBSIDIAN_API_KEY','<chave>','User')" -ForegroundColor Yellow
    exit 1
}

$headers = @{
    "Authorization" = "Bearer $API_KEY"
    "Content-Type"  = "application/json"
}

# Ignorar cert auto-assinado do plugin
if (-not ([System.Management.Automation.PSTypeName]"TrustAllCerts").Type) {
    Add-Type @"
using System.Net;
using System.Security.Cryptography.X509Certificates;
public class TrustAllCerts : ICertificatePolicy {
    public bool CheckValidationResult(
        ServicePoint sp, X509Certificate cert, WebRequest req, int problem) { return true; }
}
"@
    [System.Net.ServicePointManager]::CertificatePolicy = New-Object TrustAllCerts
}

# ─── Helpers ─────────────────────────────────────────────────────────────────
function Get-VaultNote {
    param([string]$Path)
    try {
        $encoded = [Uri]::EscapeUriString($Path)
        $r = Invoke-RestMethod -Uri "$API_BASE/vault/$encoded" `
                               -Headers $headers -Method Get -ErrorAction Stop
        return $r
    } catch {
        return $null
    }
}

function Search-Vault {
    param([string]$Query, [int]$ContextLen = 200)
    try {
        $enc = [Uri]::EscapeDataString($Query)
        $r = Invoke-RestMethod `
            -Uri "$API_BASE/search/simple/?query=$enc&contextLength=$ContextLen" `
            -Headers $headers -Method Get -ErrorAction Stop
        return $r
    } catch {
        return @()
    }
}

function Get-TodayDate  { Get-Date -Format "yyyy-MM-dd" }
function Get-WeekStart  { (Get-Date).AddDays(-(Get-Date).DayOfWeek.value__ + 1).ToString("yyyy-MM-dd") }

# ─── Checks de saúde ─────────────────────────────────────────────────────────
Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║       Vault Bootstrap — TechColab_D&A_KO             ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Testar conexão
try {
    $ping = Invoke-RestMethod -Uri "$API_BASE/" -Headers $headers -Method Get -ErrorAction Stop
    Write-Host "✅ Obsidian Local REST API conectada" -ForegroundColor Green
} catch {
    Write-Host "❌ Obsidian não está respondendo em $API_BASE" -ForegroundColor Red
    Write-Host "   → Abra o Obsidian e verifique que o plugin 'Local REST API' está ativo" -ForegroundColor Yellow
    exit 1
}

$today     = Get-TodayDate
$weekStart = Get-WeekStart

Write-Host "📅 Hoje: $today | Semana a partir de: $weekStart" -ForegroundColor DarkGray
Write-Host ""

# ─── 1. Última sessão ─────────────────────────────────────────────────────────
Write-Host "━━━ 📋 ÚLTIMA SESSÃO ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow

$lastSession = Get-VaultNote "App/Personal toolkit/AI/sessions/$today.md"
if (-not $lastSession) {
    # tentar ontem
    $yesterday = (Get-Date).AddDays(-1).ToString("yyyy-MM-dd")
    $lastSession = Get-VaultNote "App/Personal toolkit/AI/sessions/$yesterday.md"
    if ($lastSession) { Write-Host "  (sem sessão hoje — mostrando $yesterday)" -ForegroundColor DarkGray }
}

if ($lastSession) {
    # Extrair o preamble "For future Claude"
    $lines = $lastSession -split "`n"
    $preamble = $lines | Where-Object { $_ -match "^>" } | Select-Object -First 3
    $preamble | ForEach-Object { Write-Host "  $_" -ForegroundColor White }
} else {
    Write-Host "  Nenhuma sessão encontrada para hoje ou ontem." -ForegroundColor DarkGray
}
Write-Host ""

# ─── 2. 1-on-1s da semana ────────────────────────────────────────────────────
Write-Host "━━━ 👥 1-ON-1s DESTA SEMANA ━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow

$oneonone = Search-Vault "1on1 $weekStart" -ContextLen 150
if ($oneonone.Count -gt 0) {
    $oneonone | Select-Object -First 5 | ForEach-Object {
        Write-Host "  📄 $($_.filename)" -ForegroundColor Cyan
        Write-Host "     $($_.context)" -ForegroundColor DarkGray
        Write-Host ""
    }
} else {
    Write-Host "  Nenhum 1-on-1 registrado esta semana." -ForegroundColor DarkGray
}
Write-Host ""

# ─── 3. Action items pendentes do time ───────────────────────────────────────
Write-Host "━━━ ⚠️  ACTION ITEMS PENDENTES (Kelvin owns) ━━━━━━━━━━" -ForegroundColor Yellow

$actions = Search-Vault "Action pending (Kelvin)" -ContextLen 200
if ($actions.Count -gt 0) {
    $actions | Select-Object -First 8 | ForEach-Object {
        Write-Host "  📌 $($_.filename)" -ForegroundColor Magenta
        Write-Host "     $($_.context)" -ForegroundColor DarkGray
        Write-Host ""
    }
} else {
    Write-Host "  Nenhum action item encontrado." -ForegroundColor DarkGray
}
Write-Host ""

# ─── 4. Status do backlog ────────────────────────────────────────────────────
if ($Focus -eq "" -or $Focus -eq "backlog") {
    Write-Host "━━━ 📦 BACKLOG — EM DESENVOLVIMENTO ━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow

    $inDev = Search-Vault "status: em desenvolvimento" -ContextLen 120
    if ($inDev.Count -gt 0) {
        $inDev | Select-Object -First 6 | ForEach-Object {
            Write-Host "  🔄 $($_.filename)" -ForegroundColor Blue
            Write-Host "     $($_.context)" -ForegroundColor DarkGray
            Write-Host ""
        }
    } else {
        Write-Host "  Nenhum item em desenvolvimento." -ForegroundColor DarkGray
    }
    Write-Host ""
}

# ─── 5. Performance Assessment (se foco ou próxima ação) ─────────────────────
if ($Focus -eq "performance" -or $Focus -eq "") {
    Write-Host "━━━ 📊 PERFORMANCE ASSESSMENT FY26 ━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow

    $perfNote = Get-VaultNote "Team/FY26 - Assessment Observations Carryover.md"
    if ($perfNote) {
        $lines = $perfNote -split "`n" | Select-Object -First 10
        $lines | ForEach-Object { Write-Host "  $_" -ForegroundColor White }
    } else {
        Write-Host "  Nota de carryover não encontrada." -ForegroundColor DarkGray
    }
    Write-Host ""
}

# ─── 6. Open threads do agente diário ────────────────────────────────────────
if ($Focus -eq "" -or $Focus -eq "backlog") {
    $reportPath = "App/Personal toolkit/agent-reports/report-$today.md"
    $report = Get-VaultNote $reportPath
    if ($report) {
        Write-Host "━━━ 🤖 RELATÓRIO DO AGENTE — HOJE ━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow
        $lines = $report -split "`n" | Select-Object -First 20
        $lines | ForEach-Object { Write-Host "  $_" -ForegroundColor White }
        Write-Host ""
    }
}

# ─── 7. Team snapshot rápido ─────────────────────────────────────────────────
if ($Focus -eq "team" -or $Focus -eq "") {
    Write-Host "━━━ 👤 TEAM — ÚLTIMO CONTATO ━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow

    @("Ana-Leite", "Daniel-Lima", "Lucas-Shizuno", "Pedro-Klein", "Pedro-Hennig") | ForEach-Object {
        $person = $_
        $note = Get-VaultNote "Team/$person/Overview.md"
        if ($note) {
            $lastInteraction = ($note -split "`n" | Where-Object { $_ -match "last-interaction:" } | Select-Object -First 1) -replace ".*last-interaction:\s*", ""
            $name = $person -replace "-", " "
            Write-Host "  👤 $name — último contato: $lastInteraction" -ForegroundColor Cyan
        }
    }
    Write-Host ""
}

# ─── Rodapé ──────────────────────────────────────────────────────────────────
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "📌 Dica: cole este output no início do seu chat Claude como contexto." -ForegroundColor DarkGray
Write-Host "   Uso avançado: .\vault-bootstrap.ps1 -Focus team|backlog|performance|governance" -ForegroundColor DarkGray
Write-Host ""
