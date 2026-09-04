<#
    Corpo do alerta de saude do Team Memory Agent (perfil tma-health do notify.ps1).

    Existe por causa do padrao 12 da ARCHITECTURE.md: detector sem consumidor nomeado nao
    protege nada. Em 04/09 o parser do Facilitator devolveu ZERO secoes porque o documento
    veio com os cabecalhos em ListBullet maiusculo. A guarda que rejeita documento vazio
    escrevia ERROR no log — e o log do TMA nao tem leitor. Mesmo modo de falha das 7
    gravacoes pela metade em 7 dias.

    CONTRATO com o notify.ps1:
      - escreve o corpo no stdout (Write-Output)
      - escreve NADA quando esta tudo certo -> o motor fica silencioso
      - exit 0 sempre que a consulta funcionou
      - exit != 0 so quando nao deu para saber (pasta do store ausente)

    Consulta o SISTEMA DE ARQUIVOS, nunca a saida formatada de um script: o triage-body
    aprendeu isso apanhando — a versao que raspava texto com regex passou a achar ZERO
    itens quando o formato mudou por um espaco, falhando como "nao ha nada", que e o pior
    modo de falha para um lembrete.
#>

$store = Join-Path $env:USERPROFILE "TeamMemoryAgent"
if (-not (Test-Path $store)) { Write-Host "TeamMemoryAgent nao encontrado em $store"; exit 1 }

$daily    = Join-Path $store "01_Daily"
$rejected = Join-Path $store "_rejected"

# --- 1. documentos que o parser nao conseguiu ler -----------------------------------
$falhas = @()
if (Test-Path $rejected) {
    $falhas = @(Get-ChildItem $rejected -Filter *.docx -ErrorAction SilentlyContinue |
                Where-Object { $_.LastWriteTime -gt (Get-Date).AddDays(-14) })
}

# Dia sem registro NAO e alertado (decisao do Kelvin, 2026-09-04: "pule os dias sem dados").
# Sem fonte de calendario, feriado, ferias e dia sem daily eram indistinguiveis de perda real,
# e o alerta tocaria errado com frequencia suficiente para deixar de ser lido — que e
# exatamente o modo de falha que o padrao 12 descreve. Fica so o sinal inequivoco: documento
# que existiu e o parser nao conseguiu ler.
$semRegistro = @()

if ($falhas.Count -eq 0) { exit 0 }   # silencio proposital

$partes = @()

if ($falhas.Count -gt 0) {
    $lista = ($falhas | Select-Object -First 5 | ForEach-Object { "  - $($_.Name)" }) -join "`n"
    $partes += @"
$($falhas.Count) documento(s) que o parser nao conseguiu ler:

$lista

O Facilitator mudou a estrutura do documento. Os arquivos estao guardados em
_rejected\ (nada foi apagado). Peca ao Claude:

  "o TMA rejeitou documento, ve o que mudou"
"@
}

if ($semRegistro.Count -gt 0) {
    $partes += @"
$($semRegistro.Count) dia(s) util(eis) sem registro: $($semRegistro -join ', ')

Provavel: ninguem pediu o documento ao Facilitator naquele dia, e nao havia
transcript do call recorder para cobrir. Se houve reuniao, o dia se perdeu.
"@
}

Write-Output ($partes -join "`n`n---`n`n")
exit 0
