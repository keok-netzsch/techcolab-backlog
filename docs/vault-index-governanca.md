# Índice de busca do vault — governança

Dono: Kelvin Okuda · Desde: 2026-09-03 · Decisão: `vault/decisions/2026-09-03-vault-index-busca-hibrida-local.md`
(aprovada em 2026-09-03) · Backlog: idea-097 · Par técnico: `docs/vault-index.md`

## Por que existe

O vault tem 1.070 notas indexáveis e, até hoje, a recuperação era `grep` feito pelo Claude, nota
por nota. O diagnóstico de junho ("capture-rich, retrieval-poor") não mudou. Este índice dá busca
por texto e por sentido, sem LLM, sem API e sem servidor.

## O que ele lê

Todo `.md` do vault, menos `Templates/`, backups, rollback e pastas de sistema. Só leitura.
Nunca escreve, move ou apaga nota. A única escrita dentro do vault é o relatório do `lint` em
`_reports/Vault-Lint.md`, que é saída gerada por código, como o `Action-Dashboard.md`.

Com `--corpus memory`, lê também a memória do Claude Code (`~/.claude/projects/<projeto>/memory/`),
num segundo índice separado. Previsto no ADR (F3).

## O que ele guarda, e onde

Uma cópia do texto do vault, fatiada em trechos, mais um vetor de 384 números por trecho, em
`%LOCALAPPDATA%\techcolab\vault-index\index.sqlite`. Os arquivos do modelo de embedding ficam em
`models\` ao lado.

- Mesmo disco, mesmo usuário Windows, mesma proteção que a cópia local do OneDrive já tem.
- Fora do OneDrive: não sincroniza para lugar nenhum. A máquina nova refaz com `build --full`
  e `embed` (minutos).
- Fora do repositório público: o arquivo nunca fica dentro do repo, então nenhuma regra de
  `.gitignore` precisa protegê-lo.
- Retenção: é derivado. Apagar a pasta não perde nada.

## Dado de pessoa

`Team/`, `Stakeholders/` e notas com `type` de 1:1 (`1on1`, `1on1-session`, `1on1-log`,
`1on1-agenda`, `manager-call`, `devolutiva`, `person`) são indexados, mas ficam fora de qualquer
resultado por padrão. Só entram quando quem chama pede: `--sensitive` na CLI,
`include_sensitive=True` nos tools `vault_search` e `vault_briefing`. A resposta diz quantas notas
sensíveis foram omitidas, para que ausência não pareça inexistência. O bench roda com sensível
ligado porque mede recuperação, não política; o golden set fica no vault.

Por que indexar em vez de excluir: em 29/08 o Kelvin decidiu que a memória inteira, inclusive
RH, fica visível nas duas contas do CLI (ADR doc-triad, item 6). A busca segue a mesma regra, com
opt-in explícito por chamada. É o mesmo contrato do `vault_get_context_for_idea`, que já existe.

## O que nunca sai da máquina

A query, o texto das notas e os vetores. Sem API, sem gateway NETZSCH. O modelo de embedding roda
dentro do processo; o único download é o arquivo do modelo (HuggingFace, HTTPS, sha256 fixo no
código, conferido a cada carga). O tool do MCP consulta o índice na mesma máquina, em processo
ou por subprocess local; o processo do MCP com o modelo carregado ocupa ~520 MB de RAM enquanto o
Claude Desktop ou o Claude Code estiver aberto (`TECHCOLAB_VAULT_MCP_INPROC=0` desliga e volta ao
subprocess, ~12 s por chamada).

## O que ele não faz

Não captura sessão, não escreve nota, não consolida, não decide, não aprende. Não é servidor.
Não tem usuário além do dono. O que vira registro no vault continua passando pelos gates que já
existem (`process.py review`, TMA semanal, `obsidian-handoff` com o Kelvin no loop). O `briefing`
só junta o que já está escrito.

## Riscos aceitos

| Risco | Tratamento |
|---|---|
| Resultado velho com cara de novo | toda resposta traz `index_age_seconds` e `embeddings_stale_chunks`; `search` roda um build incremental antes de responder; a noite repõe os vetores |
| Índice ausente devolvendo vazio | não devolve: `IndexMissing`, exit 2, com o comando que resolve |
| Modelo ausente ou corrompido | busca segue em `fts-only` e diz por quê em `note`; hash errado apaga o arquivo e pede novo download |
| Dois builds ao mesmo tempo | um escritor, lock com PID, exit 3 para o segundo |
| Texto sensível fora do vault | derivado, apagável, mesmo disco e usuário; kit de migração não o copia |
| Nota sensível fora de `Team/`/`Stakeholders/` e sem `type` de 1:1 | escapa do filtro; a regra vive numa lista só (`corpus.py`); o `lint` lista as sensíveis só por `type`, para revisar a lista |
| Modelo de embedding em inglês num vault PT/EN | o bench com perguntas reais decide o modelo; FTS-only é o piso |
| Tarefa noturna falhando em silêncio | log mensal em `logs/`; exit code na tarefa; `stats` mostra `embeddings_stale_chunks` |

## Mudanças que pedem nova decisão do Kelvin

- Indexar um terceiro corpus além do vault e da memória do Claude Code.
- Mudar o padrão de sensível (hoje: fora, com opt-in).
- Levar o índice para outro disco, rede ou máquina.
- Qualquer escrita no vault a partir deste pacote além do relatório de lint.
- Trocar o modelo de embedding por um que exija API ou GPU.
