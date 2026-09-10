<#
.SYNOPSIS
  Gera o bundle de CAs que faz o trafego externo funcionar dentro da rede NETZSCH.

.DESCRIPTION
  A rede corporativa inspeciona TLS. O certificado que chega no Python foi emitido
  por uma CA interna que o certifi nao conhece, entao requests, yt-dlp e qualquer
  outra saida morrem com CERTIFICATE_VERIFY_FAILED.

  Este script concatena o bundle do certifi com as CAs raiz e intermediarias
  instaladas no Windows (que incluem a CA interna) e grava um PEM unico. Quem usa
  aponta SSL_CERT_FILE para ele — ver vaultsources/net.py.

  Nao desliga verificacao de certificado. Esse era o atalho e nao entra.

.PARAMETER Out
  Caminho do PEM. Default: $env:LOCALAPPDATA\techcolab\ca-bundle.pem

.NOTES
  Reexecutar depois de: `pip install -U certifi`, troca de maquina, ou mudanca de
  CA corporativa. O QA (`python -m vaultsources qa`) acusa bundle ausente ou que
  parou de validar.
#>
param(
  [string]$Out = (Join-Path $env:LOCALAPPDATA 'techcolab\ca-bundle.pem')
)

$ErrorActionPreference = 'Stop'

New-Item -ItemType Directory -Force -Path (Split-Path $Out) | Out-Null

$certifi = & python -c "import certifi;print(certifi.where())"
if (-not (Test-Path $certifi)) { throw "certifi nao encontrado (python -c 'import certifi') " }

$sb = [System.Text.StringBuilder]::new()
[void]$sb.AppendLine("# gerado por scripts/build-ca-bundle.ps1 em $(Get-Date -Format 'yyyy-MM-dd HH:mm')")
[void]$sb.AppendLine("# base: $certifi")
[void]$sb.AppendLine((Get-Content -Raw $certifi))

$n = 0
foreach ($store in @('Cert:\LocalMachine\Root','Cert:\LocalMachine\CA','Cert:\CurrentUser\Root','Cert:\CurrentUser\CA')) {
  foreach ($c in (Get-ChildItem $store -ErrorAction SilentlyContinue)) {
    try {
      $b64 = [Convert]::ToBase64String($c.RawData, 'InsertLineBreaks')
      [void]$sb.AppendLine("# $($c.Subject)")
      [void]$sb.AppendLine('-----BEGIN CERTIFICATE-----')
      [void]$sb.AppendLine($b64)
      [void]$sb.AppendLine('-----END CERTIFICATE-----')
      $n++
    } catch { }
  }
}

[IO.File]::WriteAllText($Out, $sb.ToString())

Write-Output "bundle: $Out"
Write-Output "certificados do Windows adicionados: $n"
Write-Output "tamanho: $((Get-Item $Out).Length) bytes"

if ($n -eq 0) {
  Write-Warning "nenhum certificado do Windows entrou — o bundle ficou igual ao certifi e nao resolve nada"
  exit 1
}
