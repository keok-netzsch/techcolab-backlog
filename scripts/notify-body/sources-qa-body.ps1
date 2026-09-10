<#
  sources-qa-body.ps1 — corpo do toast do QA de consistencia.

  Le o JSON de `python -m vaultsources qa --json --offline` e imprime **so** o que
  tem severidade `erro`. Silencioso quando nao ha nenhum: gerador que nao imprime
  nada nao abre janela (padrao 8), e lembrete que toca em dia limpo para de ser lido.

  Offline de proposito: o check de rede (`deps`) depende de o notebook estar na VPN
  no minuto exato do disparo, e um falso alarme diario de certificado ensina o Kelvin
  a ignorar o aviso. A checagem online roda na rotina semanal `fontes-semanal`, que
  tem alguem lendo.

  Consumidor declarado da saida do QA (padrao 12), junto com a rotina semanal e o
  proprio `_reports/Sources-QA.md`.
#>

$ErrorActionPreference = 'Stop'
$repo = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$repo = Join-Path $repo 'techcolab-backlog'
if (-not (Test-Path $repo)) { $repo = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent }

Push-Location $repo
try {
  $raw = & python -m vaultsources qa --json --offline 2>$null
  if (-not $raw) { return }
  $data = $raw | ConvertFrom-Json
} catch {
  # O proprio QA quebrou. Isso e noticia, nao silencio.
  Write-Output "O QA de consistencia nao rodou: $($_.Exception.Message)"
  return
} finally {
  Pop-Location
}

$erros = @($data.findings | Where-Object { $_.severity -eq 'erro' })
if ($erros.Count -eq 0) { return }

Write-Output "$($erros.Count) inconsistencia(s) com severidade erro:"
Write-Output ""
foreach ($e in ($erros | Select-Object -First 6)) {
  Write-Output "- [$($e.check)] $($e.title)"
  if ($e.where) { Write-Output "    onde: $($e.where)" }
  if ($e.fix)   { Write-Output "    conserto: $($e.fix)" }
}
if ($erros.Count -gt 6) {
  Write-Output ""
  Write-Output "... e mais $($erros.Count - 6). Relatorio completo em _reports/Sources-QA.md"
}

# O engine de notify trata exit code != 0 como falha do gerador. O QA sai com 2
# quando acha erro, que aqui e o caso NORMAL de ter o que mostrar.
exit 0
