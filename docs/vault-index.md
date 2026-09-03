# vaultindex — índice de busca derivado do vault (documentação técnica)

Pacote: `vaultindex/` · ADR: `vault/decisions/2026-09-03-vault-index-busca-hibrida-local.md` · Backlog: idea-097

Tríade (ARCHITECTURE.md, padrão 9): este arquivo é a técnica; negócio em
`docs/vault-index-governanca.md`; usuário em `docs/FAQ.md`, seção "Busca no vault".

## O que é

Um índice SQLite construído a partir dos `.md` do vault. O vault continua sendo a fonte da
verdade; o índice é derivado e pode ser apagado e refeito a qualquer momento (`build --full`
levou 1,3 s em 2026-09-03). Nenhum LLM em nenhum passo. Nada sai da máquina.

F1 (esta versão) entrega o fluxo full-text (FTS5). F2 acrescenta embeddings locais em ONNX,
fusão RRF de dois fluxos e os tools `vault_search` / `vault_briefing` no MCP `techcolab-vault`.

## Onde vive

`config.VAULT_INDEX_DIR` → `%LOCALAPPDATA%\techcolab\vault-index\` (override:
`TECHCOLAB_VAULT_INDEX`; em SO sem `LOCALAPPDATA`, `~/.local/share/techcolab/vault-index`).

| Arquivo | O que é |
|---|---|
| `index.sqlite` (+ `-wal`, `-shm`) | o índice, em modo WAL |
| `index.lock` | PID do build em andamento; some quando o build termina |

Fora do OneDrive (SQLite em WAL dentro de pasta sincronizada corrompe), fora do repo (contém o
texto do vault, e o repo é público), fora do git do vault (é derivado, não conhecimento).

## Comandos

`--root` e `--index-dir` vêm antes do subcomando e trocam vault e índice; é assim que os testes
rodam contra um mini-vault. Sem eles, `config.VAULT_BASE` e `config.VAULT_INDEX_DIR`.

| Comando | Faz | Exit |
|---|---|---|
| `python -m vaultindex build [--full] [--json]` | indexa; incremental por padrão; `--full` apaga o arquivo e refaz | 0 · 3 se outro build segura o lock |
| `python -m vaultindex search "<q>" [--json] [-k N] [--sensitive] [--type T]… [--folder P/] [--since D] [--until D] [--no-refresh]` | busca; antes de responder roda um build incremental (0,1 s sem mudança), a menos que `--no-refresh` | 0 · 2 se não existe índice |
| `python -m vaultindex check [--json]` | leitor independente: re-hasheia todo o vault e compara com o índice | 0 ok · 1 diverge |
| `python -m vaultindex stats` | contagens e metadados em JSON | 0 |

## Corpus (`corpus.py`)

- **Varredura:** todo `.md` sob a raiz, em ordem estável, menos `EXCLUDE_DIRS` (`.git`,
  `.obsidian`, `.trash`, `.smart-env`, `_attachments`, `_obsidian-second-brain-ref`,
  `Templates`, `rollback`, `__pycache__`, `node_modules`) e qualquer pasta cujo nome começa com
  `backup`. Backup e rollback são cópias de notas vivas e apareceriam como resultado concorrente.
- **Frontmatter tolerante:** bloco `---` opcional. YAML inválido vira `{}` com
  `has_frontmatter = 1`; sem bloco, `has_frontmatter = 0`. O lint (F3) é quem nomeia os quebrados.
- **Título:** `title:` → primeiro `# H1` → nome do arquivo.
- **Data:** `date:` → `YYYY-MM-DD` no nome do arquivo → mtime. `date_source` diz qual foi.
- **Sensível:** pasta em `SENSITIVE_FOLDERS` (`Team/`, `Stakeholders/`) ou `type` em
  `SENSITIVE_TYPES` (`1on1`, `1on1-session`, `1on1-log`, `1on1-agenda`, `manager-call`,
  `devolutiva`, `person`). Uma lista, um lugar.
- **Chunk:** corta em H2/H3; teto `CHUNK_MAX = 900` caracteres em fronteira de parágrafo, corte
  duro por espaço se um parágrafo sozinho passa do teto; seção com menos de `CHUNK_MERGE_MIN = 200`
  caracteres funde na anterior quando cabe. Invariante testada: `text == body[char_start:char_end]`.
- **Links:** `[[wikilink]]` no corpo (sem `#âncora` e `|alias`, sem `.md`) e os campos tipados
  do frontmatter `supersedes`, `superseded_by`, `contradicts`, `causes`, `fixes`. Um registro por
  (tipo, alvo) por nota.

## Esquema (`db.py`, `SCHEMA_VERSION = 1`)

```
meta        key, value                       -- schema_version, corpus_root, last_build, notes, chunks
notes       id, rel_path, stem, title, type, date, date_source, tags(json), folder,
            sensitive, pinned, has_frontmatter, sha256, mtime, size, indexed_at
chunks      id, note_id→notes, ord, heading, title, text, char_start, char_end
chunks_fts  FTS5 externo sobre chunks (text, title, heading), tokenizer unicode61 remove_diacritics 2
links       id, from_note→notes, to_title, to_note (nullable), kind
embeddings  chunk_id→chunks, model, dim, vec BLOB              -- vazio até a F2
```

`title` é copiado para cada chunk de propósito: o FTS externo só enxerga colunas da tabela de
conteúdo. `remove_diacritics 2` faz `retencao` achar `retenção`. Índice de schema diferente do
código levanta `SchemaMismatch` nas duas pontas; a saída é `build --full`.

## Build (`IndexWriter`)

1. Lock `index.lock` com o PID. PID vivo → `IndexLocked`. PID morto ou ilegível → lock órfão,
   removido, uma tentativa a mais. No Windows a checagem usa `tasklist`, porque `os.kill(pid, 0)`
   mata o processo.
2. Uma transação para o build inteiro. Falha no meio → rollback, índice anterior intacto.
3. Por nota: `mtime` e `size` iguais aos do índice → nem lê o arquivo. `mtime` diferente com
   sha256 igual (toque do OneDrive) → só atualiza `mtime`. sha256 diferente → apaga os chunks
   antigos do FTS com o comando `'delete'`, apaga a nota (cascata em chunks, links, embeddings) e
   reinsere.
4. Arquivo que sumiu do disco sai do índice.
5. Links resolvem no fim, em Python: stem igual → caminho igual → sufixo `/Nome.md` quando o alvo
   tem `/`. Empate no stem: caminho mais curto, como o Obsidian.
6. Nota que não parseia entra em `report.warnings`; o build segue.
7. Sob pytest, `IndexWriter` recusa o `index_dir` real (`PYTEST_CURRENT_TEST` no ambiente).

## Busca (`search.py`)

1. `fts_match_expression`: tokens `\w+` com 2+ caracteres, cada um entre aspas (assim `and`,
   `or`, `not` são palavras, não operadores), unidos por `OR`. Tokens com 5+ caracteres ganham
   `*`, o prefixo cobre flexão em português sem stemmer.
2. FTS5 `bm25(text=1, title=4, heading=2)`, 60 melhores chunks, `snippet()` da coluna de texto
   com marcadores `[ ]`.
3. Filtros por nota: sensível (fora por padrão; as omitidas são contadas em
   `excluded_sensitive_hits`), `type`, prefixo de pasta, `since`/`until` pela `date`.
4. Fusão RRF (k = 60) por nota, na primeira aparição do chunk. Um fluxo hoje; a F2 soma o vetorial
   sem mexer nesta etapa.
5. Autoridade, um multiplicador limitado a [0,7 · 1,3]:

   | Condição | × |
   |---|---|
   | `type` em decision, adr, person, project, area, reference | 1,15 |
   | `type` em session, daily, agent-report, capture | 0,9 |
   | idem, com `date` há mais de 90 dias | 0,8 a mais |
   | caminho em `Archive/` | 0,85 |
   | `pinned: true` no frontmatter | 1,2 |

6. Saída (`--json`): `query`, `mode` (`fts-only` até a F2), `match`, `last_build`,
   `index_age_seconds`, `embeddings_stale_chunks`, `refreshed`, `filters`, `candidates`,
   `excluded_sensitive_hits`, `excluded_by_filter`, `results[]` com `rank`, `path`, `title`,
   `type`, `date`, `date_source`, `sensitive`, `has_frontmatter`, `score`, `authority`, `why`
   (fluxos que acertaram) e até 2 `snippets` com `heading`.

## Números (vault real, 2026-09-03)

1.069 notas indexadas (1.149 no disco; 80 em pastas excluídas) · 12.728 chunks · 1.952 links,
1.246 resolvidos · 262 sensíveis · 144 sem frontmatter · 422 sem `type` · 15,6 MB ·
build completo 1,3 s · incremental sem mudança 0,08 s · `check` 0,35 s.

## Testes

`tests/test_vaultindex.py`, 25 testes, mini-vault sintético em `tmp_path`. Cobrem: pastas
excluídas, incremental (igual, alterado, apagado, e o FTS acompanhando), `--full`, metadados de
nota sem frontmatter, resolução de links (e alvo inexistente ficando `NULL`), `check` como leitor
independente, sensível fora e dentro, acento, filtros, refresh, índice ausente (exit 2), lock com
PID vivo (exit 3), lock órfão, chunking com offsets, frontmatter quebrado, autoridade.

## Fora desta versão

F2: `embed.py` (ONNX int8, mean pooling, download com sha256 fixo), fluxo vetorial, vizinhança
por wikilink, `bench` com golden set no vault, tools no MCP, `/obsidian-find` chamando o índice,
Task Scheduler noturno. F3: `lint`, `--as-of` via git do vault, corpus da memória do Claude Code.
