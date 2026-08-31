# Lembrete de roteamento - call recorder
#
# SUBSTITUICAO APROVADA (P3, PM review 2026-08-29): este script sera absorvido
# pelo motor unico de notificacao do toolkit. NAO investir em melhorias aqui -
# so correcao que o mantenha funcionando ate a troca.
# Plano: vault/pm-review-toolkit-2026-08-29.md
#
# Avisa o Kelvin, de manha, que ha calls transcritas na noite anterior esperando
# destino no vault.
#
# ATENCAO - este script MUDOU DE PAPEL em 2026-08-28.
#
# Ele nascia como um dialogo que classificava a gravacao ali mesmo, num dropdown
# de destino unico, a partir do titulo da janela do Teams. Isso deixou de fazer
# sentido no mesmo dia, por dois motivos:
#
#   1. O titulo traz o assunto AGENDADO, nunca os participantes nem o assunto
#      real. "Power BI Data Export" era o Stefan e a Ana discutindo a politica de
#      export do OKR 05.
#   2. Uma call tem VARIOS assuntos. Uma Daily BIZ com dez minutos do OKR do
#      Daniel e o resto sobre entrega tem DOIS destinos, e um dropdown so
#      escolhe um.
#
# Decidir isso exige LER a transcricao, o que um WinForms nao faz bem e um
# dropdown nao representa. Entao o trabalho passou para route.py, conduzido pela
# rotina `triagem-gravacoes` do Claude as 09:00, que le o conteudo e sugere os
# recortes. Este script ficou sendo o que ainda faz bem: cutucar.
#
# Redundancia proposital (decisao do Kelvin, "prefiro 2x do que nenhuma"): a
# rotina do Claude so roda com o app aberto; esta janela nao depende disso.
#
# Janela, nao toast: a API de toast reportava sucesso em toda execucao enquanto
# o Focus Assist suprimia o banner, entao os lembretes eram perdidos em silencio
# (ver send-evening-push.ps1, 2026-08-11).
#
# Silencioso quando nao ha nada. Lembrete que toca em dia vazio para de ser lido.

Add-Type -AssemblyName System.Windows.Forms

$py    = "python"
$base  = Join-Path $env:USERPROFILE "techcolab-backlog\call-recorder"
$route = Join-Path $base "route.py"

if (-not (Test-Path $route)) { Write-Host "route.py nao encontrado"; exit 1 }

# JSON, nao o texto formatado: a versao anterior raspava a listagem humana com
# regex e passou a achar ZERO itens quando o formato mudou por um espaco -
# falhando exatamente como "nao ha nada a rotear", o pior modo de falha possivel
# para um lembrete.
$json = & $py $route --json 2>&1 | Out-String
try {
    $pend = @($json | ConvertFrom-Json)
} catch {
    Write-Host "Nao consegui ler a lista: $($_.Exception.Message)"
    Write-Host $json
    exit 1
}
if ($pend.Count -eq 0) { Write-Host "Nada a rotear."; exit 0 }

$linhas = $pend | ForEach-Object {
    $titulo = $_.meeting
    if (-not $titulo) { $titulo = $_.id }
    $titulo = $titulo -replace "\s*\|\s*Microsoft Teams", ""
    "  - $titulo"
} | Select-Object -First 8

$corpo = @"
$($pend.Count) call(s) transcrita(s) esperando destino no vault:

$($linhas -join "`n")

Para rotear, peca ao Claude:

  "roteia as gravacoes"

Ele le a transcricao, sugere os assuntos e os destinos, e voce confirma.
Uma call pode ir para VARIOS destinos - cada um recebe so o seu recorte.

Se preferir na mao:

  python "%USERPROFILE%\techcolab-backlog\call-recorder\route.py"
"@

try {
    $form = New-Object System.Windows.Forms.Form
    $form.TopMost = $true
    $form.Opacity = 0
    $form.ShowInTaskbar = $false
    $form.StartPosition = "CenterScreen"
    $form.Size = New-Object System.Drawing.Size(0, 0)
    $form.Show()
    [System.Windows.Forms.MessageBox]::Show($form, $corpo,
        "Call Recorder - gravacoes esperando destino",
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Information) | Out-Null
    $form.Close()
    Write-Host "Lembrete exibido: $($pend.Count) pendente(s)"
} catch {
    Write-Host "MessageBox falhou: $($_.Exception.Message)"
    exit 1
}
