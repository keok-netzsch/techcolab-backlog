# Índice de busca do vault — governança

Dono: Kelvin Okuda · Desde: 2026-09-03 · Decisão: `vault/decisions/2026-09-03-vault-index-busca-hibrida-local.md`
(aprovada em 2026-09-03) · Backlog: idea-097 · Par técnico: `docs/vault-index.md`

## Por que existe

O vault tem 1.069 notas indexáveis e, até hoje, a recuperação era `grep` feito pelo Claude, nota
por nota. O diagnóstico de junho ("capture-rich, retrieval-poor") não mudou. Este índice dá busca
por texto agora e busca por sentido na F2, sem LLM, sem API e sem servidor.

## O que ele lê

Todo `.md` do vault, menos `Templates/`, backups, rollback e pastas de sistema. Só leitura.
Nunca escreve, move ou apaga nota.

## O que ele guarda, e onde

Uma cópia do texto do vault, fatiada em trechos, em
`%LOCALAPPDATA%\techcolab\vault-index\index.sqlite` (15,6 MB em 2026-09-03).

- Mesmo disco, mesmo usuário Windows, mesma proteção que a cópia local do OneDrive já tem.
- Fora do OneDrive: não sincroniza para lugar nenhum. A máquina nova refaz com `build --full`.
- Fora do repositório público: o arquivo nunca fica dentro do repo, então nenhuma regra de
  `.gitignore` precisa protegê-lo.
- Retenção: é derivado. Apagar a pasta não perde nada; refazer leva segundos.

## Dado de pessoa

`Team/`, `Stakeholders/` e notas com `type` de 1:1 (`1on1`, `1on1-session`, `1on1-log`,
`1on1-agenda`, `manager-call`, `devolutiva`, `person`) são indexados, mas ficam fora de qualquer
resultado por padrão. Só entram quando quem chama pede: `--sensitive` na CLI,
`include_sensitive=True` no MCP (F2). A resposta diz quantas notas sensíveis foram omitidas, para
que ausência não pareça inexistência.

Por que indexar em vez de excluir: em 29/08 o Kelvin decidiu que a memória inteira, inclusive
RH, fica visível nas duas contas do CLI (ADR doc-triad, item 6). A busca segue a mesma regra, com
opt-in explícito por chamada. É o mesmo contrato do `vault_get_context_for_idea`, que já existe.

## O que nunca sai da máquina

A query, o texto das notas e, na F2, os vetores. Sem API, sem gateway NETZSCH. O modelo de
embedding roda dentro do processo; o único download é o arquivo do modelo, com sha256 fixo.

## O que ele não faz

Não captura sessão, não escreve nota, não consolida, não decide, não aprende. Não é servidor.
Não tem usuário além do dono. O que vira registro no vault continua passando pelos gates que já
existem (`process.py review`, TMA semanal, `obsidian-handoff` com o Kelvin no loop).

## Riscos aceitos

| Risco | Tratamento |
|---|---|
| Resultado velho com cara de novo | toda resposta traz `index_age_seconds` e, na F2, quantos chunks ainda não têm embedding; `search` roda um build incremental antes de responder |
| Índice ausente devolvendo vazio | não devolve: levanta `IndexMissing`, exit 2, com o comando que resolve |
| Dois builds ao mesmo tempo | um escritor, lock com PID, exit 3 para o segundo |
| Texto sensível fora do vault | derivado, apagável, mesmo disco e usuário; kit de migração não o copia |
| Nota sensível fora de `Team/`/`Stakeholders/` e sem `type` de 1:1 | escapa do filtro; a regra é por pasta e por `type`, e vive numa lista só (`corpus.py`); ampliar a lista é uma linha |
| Modelo de embedding em inglês num vault PT/EN (F2) | o bench com 30 perguntas reais decide o modelo; FTS-only é o piso |

## Mudanças que pedem nova decisão do Kelvin

- Indexar algo fora do vault (a memória do Claude Code está prevista na F3 do ADR).
- Mudar o padrão de sensível (hoje: fora, com opt-in).
- Levar o índice para outro disco, rede ou máquina.
- Qualquer escrita no vault a partir deste pacote.
