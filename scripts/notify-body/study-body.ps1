# Gerador de corpo do lembrete de estudo (perfil study-reminder do notify.ps1).
# Migrado 1:1 do antigo vault/study-notify.ps1 (2026-08-30, P3) — a lógica é a mesma:
# lê study-plan.json + trackers de área no vault e monta o resumo do dia.
# Contrato do motor: só o stdout vira corpo; sem stdout = lembrete não abre.
# Silêncio proposital: se toda área ativa já teve sessão HOJE, não há o que lembrar.
# Nenhum dado pessoal vive aqui — tudo vem dos arquivos locais do vault em runtime.

$ErrorActionPreference = 'Stop'
$VaultRoot = if ($env:TECHCOLAB_VAULT_ROOT) { $env:TECHCOLAB_VAULT_ROOT }
             else { Join-Path $env:USERPROFILE 'OneDrive - NETZSCH\Documents\TechColab_D&A_KO\vault' }

# Movido 2026-09-02 para vault\study-tools\study\; os trackers em $a.tracker continuam
# resolvidos a partir de $VaultRoot (a pasta vault), por isso só o plano muda de lugar.
$planPath = Join-Path $VaultRoot 'study-tools\study\study-plan.json'
if (-not (Test-Path $planPath)) { Write-Host "study-plan.json ausente em $VaultRoot"; exit 1 }
$plan  = Get-Content $planPath -Raw -Encoding utf8 | ConvertFrom-Json

$today = Get-Date
$todayStr = $today.ToString('yyyy-MM-dd')
$daysSinceMonday = ([int]$today.DayOfWeek + 6) % 7
$monday = $today.Date.AddDays(-$daysSinceMonday)

$lines = @()
$allDoneToday = $true
$anyActive = $false

# Prazos: os 2 mais próximos ainda futuros
$next = @($plan.deadlines | Where-Object { [datetime]$_.date -ge $today.Date } |
    Sort-Object { [datetime]$_.date } | Select-Object -First 2)
foreach ($d in $next) {
    $days = ([datetime]$d.date - $today.Date).Days
    $lines += "$($d.id): $days dias"
}

# Áreas ativas: minutos na semana, dias parado, itens SRS vencidos
foreach ($p in $plan.areas.PSObject.Properties) {
    $a = $p.Value
    if ($a.status -ne 'active') { continue }
    $anyActive = $true

    $rows = @($plan.sessions | Where-Object { $_.area -eq $p.Name -and [datetime]$_.date -ge $monday })
    $weekMin = ($rows | Measure-Object -Property minutes -Sum).Sum
    if (-not $weekMin) { $weekMin = 0 }

    $all = @($plan.sessions | Where-Object { $_.area -eq $p.Name }) | Sort-Object date
    $idle = if ($all.Count) { ($today.Date - [datetime]$all[-1].date).Days } else { -1 }
    if ($idle -ne 0) { $allDoneToday = $false }

    $due = ''
    if ($a.tracker) {
        $trackerPath = Join-Path $VaultRoot $a.tracker
        if (Test-Path $trackerPath) {
            $t = Get-Content $trackerPath -Raw -Encoding utf8 | ConvertFrom-Json
            if ($t.items) {
                $n = @($t.items.PSObject.Properties | Where-Object { $_.Value.next_review -le $todayStr }).Count
                if ($n -gt 0) { $due = ", $n vencidos" }
            }
        }
    }

    $idleTxt = if ($idle -lt 0) { 'sem sessao ainda' } elseif ($idle -eq 0) { 'feito hoje' } else { "parado ha ${idle}d" }
    $flag = if (($idle -ge 3 -or $idle -lt 0) -and $a.weekly_target_min -gt 0) { '! ' } else { '' }
    $lines += "$flag$($p.Name): $weekMin/$($a.weekly_target_min)min, $idleTxt$due"
}

# Dia completo = silêncio (o motor não abre janela sem corpo)
if ($anyActive -and $allDoneToday) {
    Write-Host "todas as areas ativas ja estudadas hoje - silencioso."
    return
}

($lines -join "`n") + "`nAbra o Claude Code e digite /study"
