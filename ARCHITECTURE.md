# ARCHITECTURE.md — leia antes de construir qualquer coisa

Este é o documento canônico do toolkit do Kelvin. Ele existe porque em 2026-08-31 três
sessões de Claude trabalharam no mesmo dia sem saber uma da outra e o resultado foi:
um gate de aprovação construído contra uma regra que o Kelvin já tinha dado, um app
removido por leitura errada de uma frase, e uma pendência marcada como "a decidir" quando
a decisão estava tomada havia sete semanas num arquivo que ninguém abriu.

Nenhum desses erros foi de código. Todos foram de **não saber o que já existia**.

## Como usar

**Antes de criar qualquer coisa nova** — script, tela, rotina agendada, comando, notificação,
skill, arquivo de estado — passe por aqui:

1. **Já existe?** Seção *O que existe*. Estender o que está lá ganha de criar um paralelo.
2. **Que padrão isso tem que seguir?** Seção *Padrões*. Eles não são estilo; cada um veio de
   um estrago concreto e evita a repetição dele.
3. **Isso contradiz uma decisão?** Seção *Decisões*. Se contradiz, **pare e pergunte** —
   não decida sozinho que a decisão envelheceu.
4. **Terminou?** Seção *Depois de construir*. Registre, ou a próxima sessão repete o ciclo.

> Se você leu este arquivo e ele está errado ou desatualizado, **corrigir faz parte da
> tarefa** — não é escopo separado. Documento que mente é pior que documento ausente,
> porque a próxima sessão confia nele.

---

## O que existe

Não são vinte ferramentas soltas. São **quatro trabalhos**, e quase toda peça serve a um:

| Trabalho | O que resolve | Peças |
|---|---|---|
| **Memória** | nada do que acontece se perde | `call-recorder/`, `~/TeamMemoryAgent/`, vault, `~/voice-dictate/` |
| **Decisão** | decido rápido, com estado único | `backlog/` (BacklogStore), `agent/` (CLI + brief + Closer), `agent/pending.py`, app Streamlit |
| **Entrega** | produzo material com marca | skill `techcolab-deck`, `Resources/loop-export`, Timeline |
| **Aprendizado** | aprendo com cadência | `agent/english_coach.py`, skills `cdmp`/`deutsch`/`study` |

### Onde o estado vive (e quem manda)

| Estado | Fonte da verdade | Quem escreve |
|---|---|---|
| Backlog / status de ideia | `{VAULT_ROOT}/backlog items/idea-NNN.md` | **só** `create_idea.py` e `update_status.py` |
| Pendências do Kelvin | `agent/pending.py` (JSON) → visão .md gerada | `pending.py`; nunca editar o .md |
| Fatia acionável do backlog | derivada, não armazenada — `agent/curadoria.py` | ninguém escreve: lê o BacklogStore e reusa `weekly_brief.collect_decisions` |
| Compromissos extraídos de call | notas roteadas → `_reports/Action-Dashboard.md` | a **sessão** das 09:00 escreve nas notas; `process.py dashboard` consolida |
| Verdade sobre uma pessoa | `Team/<Pessoa>/PDI.md`, `OKR.md`, `Overview.md` | **só via gate** (`process.py review --approve`) |
| Log de sessão 1:1 | `Team/<Pessoa>/1on1.md` | `process.py` direto (é log, não afirmação) |
| Registro do time | `10_2ndBrain/Team Memory/Topics/` | **só via gate** do TMA (aprovação semanal) |
| Plano de estudo (sessões, prazos, next_focus) | `{VAULT_ROOT}/vault/study-tools/study/study-plan.json` | **só** `study-log.ps1` (sessions/next_focus) e a skill `/study` (areas/deadlines) |
| Trackers de estudo por área (SRS, scores) | `{VAULT_ROOT}/vault/study-tools/<área>/` — `cdmp/cdmp-tracker.json`, `deutsch/deutsch-tracker.json`, … | **só** o recorder da área (`cdmp-record-answer.ps1`, `deutsch-record.ps1`); o monitor `/study` lê tudo e não escreve em nenhum |

### O que roda sozinho

`docs/scheduled-automation.md` é a lista completa e é **obrigatório atualizá-la** no mesmo
commit em que uma tarefa nasce, muda de horário ou morre. Se não está lá, ninguém sabe que
existe.

---

## Padrões — replique estes

### 1. O vault é registro; o chat é interação
**Regra global**, em `~/.claude/CLAUDE.md`, vale em qualquer projeto e qualquer sessão.
Nunca instrua o Kelvin a abrir, editar, ticar ou aprovar algo dentro do Obsidian. Se o
mecanismo que você construiu **só** funciona com ele editando arquivo à mão, o mecanismo
está errado — dê um caminho por CLI/chat/app.
*Custo que gerou a regra:* um gate de aprovação inteiro entregue em 31/08 exigindo trocar
`status: draft` no frontmatter. Refeito no mesmo dia.

### 2. Nada vira fato sobre uma pessoa sem alguém dizer que é
Saída de modelo que descreve gente **propõe**, não afirma. Vai para uma área de revisão e
só entra no arquivo real por ação humana explícita.
*Custo:* um modelo local de 7B inventou uma "Daniela" como responsável por um objetivo, a
partir de uma call sobre outro projeto, e o pipeline gravou isso no PDI, OKR, Overview,
1on1 e no dashboard de uma pessoa do time. Ficou quase três meses e a tela exibia como fato.
Implementação de referência: `GATED_BLOCKS` em `call-recorder/process.py` e o gate semanal
do Team Memory Agent.

### 3. Silêncio não é consentimento
Proposta não aprovada **nunca** é aplicada — nem por timeout, nem por lote, nem por
"provavelmente está ok". E descartar guarda (`_rejected/`), não apaga.

### 4. Determinismo onde a verdade importa
Consolidação e publicação são código, não modelo. O LLM entra na captura e na proposta;
nunca na linha que vira registro. É o que garante que toda linha publicada rastreia até uma
fonte datada. Ver o docstring de `tma_consolidate.py`.
Corolário (revisto 2026-09-02): **dado de pessoa vai ao gateway NETZSCH para `oneonone`, `manager` e `agenda`** — decisão do Kelvin, motivada por RAM. Continuam locais `note`, `capture` e `transcript`: o Inbox recebe conteúdo da transição não anunciada e o gateway é logado pelo empregador (ADR 2026-08-31, decisão 4). Antes disso a única exceção era o English Coach
(gateway NETZSCH), e ela é forçada por `purpose` em `coach_llm.py` — não por env var.

### 5. Erro tem que parecer erro
Falha de processamento nunca vai para um campo que o consumidor renderiza como conteúdo.
*Custo:* `_fallback_1on1` escrevia `(auto) Modelo nao estruturou em blocos` **como tópico**,
e a aba Team mostrava isso como o assunto do último 1:1. Hoje é um marcador
`<!-- unparsed -->` e quem consome diz "não processada".

*Custo 2 (2026-09-01):* `config.py` caía num caminho placeholder quando `TECHCOLAB_VAULT`
não estava definida. O arquivo do ledger não era encontrado, `pending.py list` imprimia
"Nada esperando você" e saía com **código 0**, com três pendências abertas de verdade.
Apareceu quando uma sessão de nuvem rodou o toolkit pela ponte de device e não herdou o
ambiente do usuário. Escrita nunca teve o problema (estoura com `FileNotFoundError`), só a
leitura mentia. Hoje `config.py` levanta erro no import e não existe fallback. Vale a regra
geral: **default de conveniência em caminho de dado é uma resposta errada esperando
acontecer** — quem chama de fora do ambiente do dono é quem paga.

### 6. Dado velho tem que se declarar velho
Se a tela mostra número, ela mostra **de quando é**. Tela confiante sobre número velho é
pior que tela nenhuma — o leitor não tem como saber.
*Custo:* PDI com prazo vencido havia dois meses exibido a 0% como situação atual, ao lado de
um ciclo de performance já fechado. Ver `_pdi_freshness` em `views/team.py`.

### 7. Fonte única, cópia derivada
Nada de duas cópias editáveis da mesma coisa. Uma canônica, o resto sincronizado por script
com modo `-Check` que falha se divergir. Ver `da-management-skills/scripts/sync-techcolab-deck.ps1`.

### 8. Lembrete novo é perfil, não script novo
`scripts/notify.ps1 -Profile <nome>` + `notify-config.json`. Não escreva o quinto script de
toast. Modo `messagebox` para o que não pode ser perdido (o Focus Assist engolia toasts em
silêncio enquanto a API reportava sucesso); `balloon` só para o dispensável. Gerador que não
imprime nada **não abre janela** — lembrete que toca em dia vazio para de ser lido.

### 9. Toda mudança atualiza a tríade
Técnica (como funciona) · Negócio (por que existe, risco, dono) · Usuário (como usar).
No `call-recorder/` são três arquivos e é obrigatório mexer nos três na mesma entrega.

### 10. Teste não escreve no vault real
A guarda vai **na fonte**, não só no arquivo de teste: `pending._save` levanta erro se
`PYTEST_CURRENT_TEST` está no ambiente e o alvo é o ledger real. Fixture `autouse` protege
só o arquivo onde ela mora — e o ledger é chamado por *código de produção*
(`_stage_for_review`), então esse caminho volta a ser exercitado por testes que ainda nem
existem. Use as duas: guarda na fonte, fixture por conveniência.
*Custo:* testes do gate criaram duas pendências reais no ledger do Kelvin (P-013, P-014).

### 11. Antes de escrever "aguarda o Kelvin", procure se ele já decidiu
Uma pendência falsa custa mais que nenhuma: ele olha a lista, não reconhece o item e passa
a duvidar da lista inteira. Cabeçalho `OPEN` num documento **não é evidência** de questão
aberta — pode ser texto que envelheceu.
*Custo:* em 31/08 esta sessão leu um `GOVERNANCE.md` desatualizado e abriu `P-004` para o
consentimento do autocapture, decidido pelo Kelvin em 26/08 e já registrado no `CLAUDE.md`.
Removida com `pending.py remove --motivo`, que existe exatamente para isso.

---

## Decisões — não reabrir sem perguntar

| Data | Decisão | Onde está registrada |
|---|---|---|
| 2026-08-26 | Toolkit 2.0: pipeline diário `/plan` morto; captura → estado único → Closer semanal | ADR `2026-08-27-toolkit-closer-sprint.md` |
| 2026-08-26 | Call Recorder 2.0: 2 canais, captura automática, classificação depois | `call-recorder/CLAUDE.md` |
| 2026-08-26 | Autocapture ligado por padrão; o Kelvin divulga a gravação caso a caso | `call-recorder/GOVERNANCE.md` |
| 2026-08-28 | Roteamento por assunto, depois da transcrição — uma call tem N destinos | ADR `2026-08-28-roteamento-por-assunto.md` |
| 2026-08-29 | Daily BIZ/PM são território do TMA, não do roteamento direto | `ROUTING_RULES` em `route.py` |
| 2026-08-31 | **Log semanal do time NÃO gradua para o vault central.** Palavras dele: *"isso é de minha propriedade (vault pessoal). para o central, devem ir as notas já categorizadas, não o log"* | ledger P-002 |
| 2026-08-31 | Retenção do call recorder confirmada: 7 dias para áudio transcrito, indefinido para transcript. *"por mim ok"* | ledger P-005, `call-recorder/GOVERNANCE.md` |
| 2026-09-01 | **Objeção do interlocutor: manter e marcar.** Palavras dele: *"manter e marcar"* — o áudio não é apagado nem transcrito; `<base>.no-consent.json` e `process.py objecao` | ledger P-017, `call-recorder/GOVERNANCE.md` |
| 2026-08-31 | Compromissos e oportunidades saem da call na sessão das 09:00 — `- [ ] (Dono) … @data` nas notas, oportunidade em `em análise` | `EXTRACT_CONTRACT` em `route.py` |
| 2026-08-29 | Produção = local-por-design ou SharePoint. **Nunca free tier externo** para dado NETZSCH | ADR `2026-08-29-doc-triad-e-producao.md` |
| 2026-08-29 | Tudo compartilhado entre as 2 contas do CLI; artefato vive no filesystem | idem, ponto 6 |
| 2026-08-31 | **O app Streamlit fica.** O problema é utilidade, não existência | `2026-08-31-app-streamlit-diagnostico.md` |
| 2026-08-31 | O vault é registro; a interação é no chat | `~/.claude/CLAUDE.md` (global) |
| 2026-08-31 | PDI/OKR/Overview só recebem texto de modelo via gate | `call-recorder/GOVERNANCE.md` |
| 2026-08-31 | **Uma sessão por vez tocando o repo e o vault.** Rotinas fundidas para reduzir sessão automática | `vault/auditoria-tokens-2026-08-31.md` |
| 2026-08-31 | Sistema de estudo MDM: estado no vault com 1 escritor por arquivo; monitor `/study` read-only sobre trackers; conteúdo da transição (não anunciada) nunca roda no gateway — só na conta Max; áudio de alemão é o P6 (deutsch v2), não uma 2ª solução | ADR `2026-08-31-sistema-de-estudo-mdm.md` |

**Decisão de ciclo de pessoas não se retoma aqui.** Mérito, bônus, promoção e IDP do FY26
estão em `Team/FY26 - Assessment Findings & Cross-Manager Calibration.md`, com a seção
"Carry to FY27". Leia antes de escrever que algo "depende de decisão do Kelvin" — em 31/08
uma sessão marcou como pendente o que já estava decidido desde julho.

---

## Antes de construir

- [ ] Li *O que existe* — não estou criando um paralelo do que já tem dono
- [ ] O que eu vou construir pede algo do Kelvin? Então tem caminho por chat/CLI/app, **não** por Obsidian
- [ ] Escreve algo sobre uma pessoa? Passa por gate
- [ ] Cria estado novo? Justifique por que não cabe no BacklogStore ou no ledger
- [ ] Roda sozinho? Vai para `docs/scheduled-automation.md` no mesmo commit
- [ ] Notifica? É perfil no `notify-config.json`
- [ ] Toca `call-recorder/`? Atualiza a tríade

## Depois de construir

- [ ] Testes passando (`python -m pytest tests/ -q`) e commit + push
- [ ] Docs afetadas atualizadas **no mesmo commit**
- [ ] Ficou algo esperando o Kelvin? → `python agent/pending.py add --tipo decisao --texto "..." --origem "..." [--ref <arquivo>]`
- [ ] Decisão estrutural nova? → ADR em `vault/decisions/YYYY-MM-DD-<slug>.md` **e** uma linha na tabela acima
- [ ] Outra sessão trabalha no mesmo arquivo? Avise (as sessões conversam entre si)

## Limites que não são negociáveis

- **Este repo é PÚBLICO.** Nunca commitar `Team/`, `Stakeholders/`, PDI, OKR, performance,
  1:1 ou compensação. O hook `.githooks/pre-commit` barra; não contorne.
- **O vault é git local-only.** Nunca `push`, nunca `git add .`.
- **Nunca hardcodar chave.** Ambiente, sempre.
- **Confirme a data real** com `Get-Date` antes de nomear arquivo ou ADR — o relógio já
  esteve dois dias fora e os mtimes vieram com a mesma defasagem.
