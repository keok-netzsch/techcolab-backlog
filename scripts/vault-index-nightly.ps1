# Runner da tarefa agendada "TechColab Vault Index" (diaria, 18:00).
#
# Roda `python -m vaultindex build --embed` com o Python do .venv do repo (que tem
# onnxruntime e tokenizers) e anexa a saida JSON num log mensal em logs\. O build e
# incremental; os embeddings so sao gerados para os chunks que ainda nao tem vetor.
# Na noite tipica isso leva segundos. Um build completo leva ~2 s + o tempo de embutir
# tudo (minutos), e so acontece quando o indice foi apagado ou o schema mudou.
#
# Sai com o codigo do Python: 0 ok, 2 indice ausente (o proprio build cria), 3 outro
# build segurando o lock (busca com refresh no mesmo instante; tenta de novo amanha).
#
# Doc: docs/vault-index.md · docs/scheduled-automation.md · ADR 2026-09-03.

$repo = Join-Path $env:USERPROFILE "techcolab-backlog"
$py = Join-Path $repo ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }
$logDir = Join-Path $repo "logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$log = Join-Path $logDir ("vault-index-" + (Get-Date -Format "yyyy-MM") + ".log")

Set-Location $repo
# O Python escreve UTF-8; sem isto o PowerShell 5.1 grava o log em ANSI e os acentos viram lixo.
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$PSDefaultParameterValues["Add-Content:Encoding"] = "utf8"
$stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path $log -Value "=== $stamp build --embed"
& $py -m vaultindex --json build --embed 2>&1 | Add-Content -Path $log
$code = $LASTEXITCODE
Add-Content -Path $log -Value "=== exit $code"

# Lint depois do build: so le o indice e regrava _reports/Vault-Lint.md (2 s). Roda mesmo
# se o build saiu 3 (lock ocupado): o indice existente ainda vale um relatorio datado.
# Saida humana de proposito (2 linhas de resumo); cortar o JSON com Select-Object fechava o
# pipe e o Python saia com -1 no primeiro teste manual.
if ($code -ne 2) {
    Add-Content -Path $log -Value "=== lint"
    & $py -m vaultindex lint 2>&1 | Add-Content -Path $log
    Add-Content -Path $log -Value "=== lint exit $LASTEXITCODE"
}
exit $code
