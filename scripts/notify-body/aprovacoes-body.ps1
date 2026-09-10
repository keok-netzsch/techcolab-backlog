<#
    Corpo do lembrete de aprovacoes pendentes (perfil aprovacoes-pendentes do notify.ps1).

    Existe por um pedido do Kelvin em 2026-09-04: "essas tasks de aprovacao que sao
    recorrentes estejam em rotinas, com o lembrete no horario". Ele ja tinha pontuado
    antes. O que faltava nao era mecanismo de aprovacao, era ele SABER que tem algo
    esperando: a rotina pendencias-do-kelvin monta o painel as 08:30 dentro do Claude,
    e se ele nao abrir o app naquele momento o painel nao existe para ele.

    O caso que provou a lacuna: a semana 2026-W35 do Team Memory Agent foi aprovada em
    27/08 e o destino no vault central (10_2ndBrain\Team Memory) seguia VAZIO em 04/09.
    A aprovacao semanal nunca entrou no ledger, entao nenhuma rotina a mostrava, e a
    unica forma de aprovar era editar frontmatter no Obsidian - que e exatamente o que
    a regra global proibe.

    CONTRATO com o notify.ps1:
      - escreve o corpo no stdout (Write-Output)
      - escreve NADA quando nao ha nada esperando -> o motor fica silencioso
      - exit 0 sempre que a consulta funcionou
      - exit != 0 so quando nao deu para saber (ledger ausente ou ilegivel)

    Le o SISTEMA DE ARQUIVOS, nunca a saida formatada de um script. Duas fontes de
    proposito: o ledger (canonico) e os drafts do TMA (rede de seguranca). Se a rotina
    team-memory-alerta falhar em registrar a semana, o lembrete ainda avisa - o modo de
    falha "ninguem foi avisado" e o unico que nao pode acontecer aqui.
#>

$ErrorActionPreference = 'Stop'

$vault = Join-Path $env:USERPROFILE "OneDrive - NETZSCH\Documents\TechColab_D&A_KO\App\Personal toolkit"
$ledger = Join-Path $vault "pendencias.json"
if (-not (Test-Path $ledger)) { Write-Host "ledger nao encontrado em $ledger"; exit 1 }

$hoje = Get-Date -Format "yyyy-MM-dd"
$linhas = @()

# --- 1. ledger: o que esta aberto e nao adiado --------------------------------------
try {
    $dados = Get-Content $ledger -Raw -Encoding UTF8 | ConvertFrom-Json
} catch {
    Write-Host "ledger ilegivel: $($_.Exception.Message)"; exit 1
}

$abertas = @($dados.itens | Where-Object {
    -not $_.resolvida_em -and
    (-not $_.adiada_ate -or $_.adiada_ate -le $hoje)
})

if ($abertas.Count -gt 0) {
    $alta  = @($abertas | Where-Object { $_.prioridade -eq 'alta' }).Count
    $velha = @($abertas | Where-Object {
        $_.criada_em -and ([datetime]$hoje - [datetime]$_.criada_em).Days -gt 14
    }).Count

    $resumo = "$($abertas.Count) esperando voce"
    if ($alta -gt 0)  { $resumo += ", $alta de prioridade alta" }
    if ($velha -gt 0) { $resumo += ", $velha parada(s) ha mais de 14 dias" }
    $linhas += $resumo
    $linhas += ""

    # As 3 mais antigas, para o lembrete dizer DO QUE se trata. Um numero sozinho vira
    # ruido de fundo; o assunto e o que faz ele abrir o painel.
    foreach ($p in ($abertas | Sort-Object criada_em | Select-Object -First 3)) {
        $txt = ($p.texto -replace '\s+', ' ')
        if ($txt.Length -gt 90) { $txt = $txt.Substring(0, 90) + "..." }
        $linhas += "  $($p.id) [$($p.tipo)] $txt"
    }
    if ($abertas.Count -gt 3) { $linhas += "  (+ $($abertas.Count - 3) outras)" }
}

# --- 2. Team Memory: semana com draft e sem aprovacao -------------------------------
# Rede de seguranca. O caminho normal e a rotina team-memory-alerta registrar isso no
# ledger; esta checagem existe para o dia em que ela nao rodar.
$store = Join-Path $env:USERPROFILE "TeamMemoryAgent"
if (Test-Path $store) {
    # O .md de revisao e escrito no VAULT, nao em 02_Drafts (la ficam so os sidecars
    # .json). Errar essa pasta faz a checagem devolver "nada pendente" para sempre.
    $drafts   = Join-Path $env:USERPROFILE "OneDrive - NETZSCH\Documents\TechColab_D&A_KO\Areas\Team Memory\_Review"
    $aprovado = Join-Path $store "03_Approved"

    $semAprovacao = @()
    if (Test-Path $drafts) {
        foreach ($d in (Get-ChildItem $drafts -Filter "*-team-progress-draft.md" -ErrorAction SilentlyContinue)) {
            $semana = $d.Name -replace '-team-progress-draft\.md$', ''
            $alvo = Join-Path $aprovado "$semana-team-progress.md"
            if (-not (Test-Path $alvo)) { $semAprovacao += $semana }
        }
    }

    foreach ($s in $semAprovacao) {
        # Nao repetir o que o ledger ja cobre.
        $jaNoLedger = @($abertas | Where-Object { $_.texto -match [regex]::Escape($s) }).Count -gt 0
        if (-not $jaNoLedger) {
            if ($linhas.Count -gt 0) { $linhas += "" }
            $linhas += "Team Memory: a semana $s tem draft e nenhuma aprovacao."
            $linhas += "Enquanto ela nao for aprovada, o registro do time no vault central nao recebe nada."
        }
    }
}

if ($linhas.Count -eq 0) { exit 0 }

$linhas += ""
$linhas += "O painel clicavel esta no Claude (rotina pendencias-do-kelvin, 08:30)."
$linhas += "Ou responda por aqui: abra o Claude e peca 'mostra minhas pendencias'."

Write-Output ($linhas -join "`r`n")
exit 0
