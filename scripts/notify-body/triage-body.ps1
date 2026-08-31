<#
    Corpo do lembrete de roteamento de gravacoes (perfil triage-reminder do notify.ps1).

    Extraido de scripts/triage-reminder.ps1 na migracao P3 (2026-08-30). A logica e a
    mesma; muda so quem mostra a janela.

    CONTRATO com o notify.ps1:
      - escreve o corpo do lembrete no stdout (Write-Output)
      - escreve NADA quando nao ha pendencia -> o motor fica silencioso
      - exit 0 sempre que a consulta funcionou (com ou sem pendencia)
      - exit != 0 so quando nao deu para saber (route.py ausente / JSON ilegivel)

    Por que JSON e nao a listagem humana: a versao anterior raspava o texto formatado
    com regex e passou a achar ZERO itens quando o formato mudou por um espaco - falhando
    exatamente como "nao ha nada a rotear", o pior modo de falha possivel para um lembrete.
#>

$py    = "python"
$base  = Join-Path $env:USERPROFILE "techcolab-backlog\call-recorder"
$route = Join-Path $base "route.py"

if (-not (Test-Path $route)) { Write-Host "route.py nao encontrado em $base"; exit 1 }

$json = & $py $route --json 2>&1 | Out-String
try {
    $pend = @($json | ConvertFrom-Json)
} catch {
    Write-Host "Nao consegui ler a lista: $($_.Exception.Message)"
    Write-Host $json
    exit 1
}

if ($pend.Count -eq 0) { exit 0 }   # silencio proposital

$linhas = $pend | ForEach-Object {
    $titulo = $_.meeting
    if (-not $titulo) { $titulo = $_.id }
    $titulo = $titulo -replace "\s*\|\s*Microsoft Teams", ""
    "  - $titulo"
} | Select-Object -First 8

Write-Output @"
$($pend.Count) call(s) transcrita(s) esperando destino no vault:

$($linhas -join "`n")

Para rotear, peca ao Claude:

  "roteia as gravacoes"

Ele le a transcricao, sugere os assuntos e os destinos, e voce confirma.
Uma call pode ir para VARIOS destinos - cada um recebe so o seu recorte.

Se preferir na mao:

  python "%USERPROFILE%\techcolab-backlog\call-recorder\route.py"
"@

exit 0
