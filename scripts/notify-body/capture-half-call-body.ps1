<#
    Corpo do alerta de gravacao pela metade (perfil capture-half-call do notify.ps1).

    Padrao 12 da ARCHITECTURE.md. O sinal ja existia em dois lugares e nenhum chegava ao
    Kelvin no dia da call: o `*** ALERTA: canal 1 sem fala ***` do capture_multi (log sem
    leitor, desde 27/08) e o gate do relatorio das 07:00 (so na manha seguinte). Em 03/09
    duas calls sairam com o canal do interlocutor zerado e ele descobriu em 04/09, porque
    perguntou.

    Quem dispara: o `autocapture`, logo depois de salvar o .wav. Nao e tarefa agendada.

    CONTRATO com o notify.ps1:
      - escreve o corpo no stdout
      - escreve NADA quando nao ha gravacao meia-conversa nova -> motor silencioso
      - exit 0 quando a consulta funcionou
      - exit != 0 so quando nao deu para saber (pasta ou modulo ausente)

    A regra de "meia conversa" NAO e reimplementada aqui. Ela vive em
    `transcript_quality.canal_mudo`, que o relatorio diario tambem usa. Duas copias da
    mesma regra divergem, e a que fica errada e sempre a que ninguem roda.
#>

$repoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$modulo   = Join-Path $repoRoot "call-recorder\halfcall_notify.py"

if (-not (Test-Path $modulo)) { Write-Host "halfcall_notify.py nao encontrado em $modulo"; exit 1 }

$global:LASTEXITCODE = 0
$saida = & python $modulo 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "halfcall_notify.py saiu com codigo $LASTEXITCODE : $saida"
    exit $LASTEXITCODE
}

$texto = ($saida | Out-String).Trim()
if ([string]::IsNullOrWhiteSpace($texto)) { exit 0 }   # silencio proposital

Write-Output $texto
exit 0
