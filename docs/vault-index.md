# vaultindex — índice de busca derivado do vault (documentação técnica)

Pacote: `vaultindex/` · ADR: `vault/decisions/2026-09-03-vault-index-busca-hibrida-local.md` · Backlog: idea-097

Tríade (ARCHITECTURE.md, padrão 9): este arquivo é a técnica; negócio em
`docs/vault-index-governanca.md`; usuário em `docs/FAQ.md`, seção "Busca no vault".

## O que é

Um índice SQLite construído a partir dos `.md` do vault. O vault continua sendo a fonte da
verdade; o índice é derivado e pode ser apagado e refeito a qualquer momento. Dois fluxos de
recuperação, full-text (FTS5) e vetorial (embeddings ONNX rodando dentro do processo, CPU),
fundidos por RRF. Nenhum LLM em nenhum passo. Nada sai da máquina: a única chamada de rede é o
download único dos arquivos do modelo, com sha256 fixo.

Fases entregues em 2026-09-03: F1 (FTS), F2 (vetores, bench, tools no MCP, tarefa noturna) e F3
(lint, `--as-of`, corpus da memória do Claude Code). Fora: tela Streamlit (freeze até 25/09).

## Onde vive

`config.VAULT_INDEX_DIR` → `%LOCALAPPDATA%\techcolab\vault-index\` (override:
`TECHCOLAB_VAULT_INDEX`; em SO sem `LOCALAPPDATA`, `~/.local/share/techcolab/vault-index`).

| Caminho | O que é |
|---|---|
| `index.sqlite` (+ `-wal`, `-shm`) | o índice, em modo WAL |
| `index.lock` | PID do build em andamento; some quando o build termina |
| `models/<nome>/model.onnx`, `tokenizer.json` | modelo de embedding, int8, hash conferido a cada carga |
| `..\memory-index\` | segundo índice, para `--corpus memory` |

Fora do OneDrive (SQLite em WAL dentro de pasta sincronizada corrompe), fora do repo (contém o
texto do vault, e o repo é público), fora do git do vault (é derivado, não conhecimento).

## Comandos

`--root`, `--index-dir` e `--corpus` vêm antes do subcomando. Sem eles, `config.VAULT_BASE` e
`config.VAULT_INDEX_DIR`. `--corpus memory` aponta os dois para a memória do Claude Code
(`~/.claude/projects/<projeto>/memory/` → `memory-index`), mesmo código.

| Comando | Faz | Exit |
|---|---|---|
| `build [--full] [--embed] [--model M]` | indexa; incremental por padrão; `--full` apaga e refaz; `--embed` gera os vetores que faltam para o modelo ativo | 0 · 3 se outro build segura o lock |
| `embed [--model M] [--force] [--no-activate]` | vetores para os chunks sem embedding desse modelo; ao terminar, o modelo vira o ativo da busca (salvo `--no-activate`) | 0 |
| `search "<q>" [-k N] [--sensitive] [--type T]… [--folder P/] [--since D] [--until D] [--as-of D] [--streams fts,vec] [--model M] [--no-neighbours] [--no-refresh]` | busca híbrida; antes de responder roda um build incremental (0,1 s sem mudança) | 0 · 2 se não há índice |
| `check` | leitor independente: re-hasheia o corpus e compara com o índice | 0 ok · 1 diverge |
| `stats` | contagens, modelo ativo, vetores por modelo, chunks sem vetor | 0 |
| `bench [--golden F] [--model M]… [--modes fts,vec,hybrid] [--k 5] [--details]` | hit@1, hit@k e MRR contra o golden set | 0 |
| `briefing [--days N] [--sensitive]` | abertura de sessão sem LLM (markdown; `--json` para o dado cru) | 0 |
| `lint [--no-write] [--stdout]` | saúde estrutural → `_reports/Vault-Lint.md` | 0 |

Todos aceitam `--json` (flag global). O MCP `techcolab-vault` expõe `search` e `briefing` como
`vault_search` e `vault_briefing`. Ele importa este pacote **em processo** (o venv dele tem
`onnxruntime`, `tokenizers`, `numpy`), então o modelo carrega uma vez por vida do servidor: a
subida pré-carrega as bibliotecas (~2 s), a primeira busca leva ~2 s e as seguintes ~0,4 s. Sem essas dependências, cai para um subprocess
com o Python do `.venv` do repo (~12 s por chamada, o custo de importar e carregar o modelo a
cada processo) e diz qual caminho usou no campo `bridge`. Na CLI, uma busca híbrida fria custa
esses ~12 s; `--streams fts` responde em ~0,3 s. Quem embutir este pacote em outro servidor
stdio: importar numpy/onnxruntime/tokenizers no main thread antes do event loop e fixar
`OPENBLAS_NUM_THREADS=1`, senão o primeiro import trava (OpenBLAS cria threads no `DllMain`;
visto em 2026-09-03, ADR §8).

## Corpus (`corpus.py`)

- **Varredura:** todo `.md` sob a raiz, em ordem estável, menos `EXCLUDE_DIRS` (`.git`,
  `.obsidian`, `.trash`, `.smart-env`, `_attachments`, `_obsidian-second-brain-ref`,
  `Templates`, `rollback`, `__pycache__`, `node_modules`) e qualquer pasta cujo nome começa com
  `backup`. Backup e rollback são cópias de notas vivas e apareceriam como resultado concorrente.
- **Frontmatter tolerante:** bloco `---` opcional. YAML inválido vira `{}` com
  `has_frontmatter = 1`; sem bloco, `has_frontmatter = 0`. O `lint` é quem nomeia os quebrados.
- **Título:** `title:` → `titulo:` (schema PT das ideias do backlog) → primeiro `# H1` → nome do arquivo.
- **Data:** `date:` → `YYYY-MM-DD` no nome do arquivo → mtime. `date_source` diz qual foi.
- **Sensível:** pasta em `SENSITIVE_FOLDERS` (`Team/`, `Stakeholders/`) ou `type` em
  `SENSITIVE_TYPES` (`1on1`, `1on1-session`, `1on1-log`, `1on1-agenda`, `manager-call`,
  `devolutiva`, `person`). Uma lista, um lugar.
- **Chunk:** corta em H2/H3; teto `CHUNK_MAX = 600` caracteres em fronteira de parágrafo, corte
  duro por espaço se um parágrafo sozinho passa do teto; seção com menos de `CHUNK_MERGE_MIN = 200`
  caracteres funde na anterior quando cabe. Invariante testada: `text == body[char_start:char_end]`.
  600 venceu 900 no bench (híbrido hit@5 0,763 vs 0,684): a janela do modelo ativo é de 128
  tokens e um chunk de 900 perdia a cauda. `TECHCOLAB_CHUNK_MAX` existe só para experimento; todo
  build de um índice tem que usar o mesmo valor, senão o próximo `--full` re-chunka tudo e derruba
  todos os vetores.
- **Links:** `[[wikilink]]` no corpo (sem `#âncora` e `|alias`, sem `.md`) e os campos tipados
  do frontmatter `supersedes`, `superseded_by`, `contradicts`, `causes`, `fixes` (aceitam
  `[[Nota]]` com ou sem aspas). Um registro por (tipo, alvo) por nota.

## Esquema (`db.py`, `SCHEMA_VERSION = 2`)

```
meta        key, value              -- schema_version, corpus_root, last_build, notes, chunks, embedding_model
notes       id, rel_path, stem, title, type, date, date_source, tags(json), folder,
            sensitive, pinned, has_frontmatter, sha256, mtime, size, indexed_at
chunks      id, note_id→notes, ord, heading, title, text, char_start, char_end
chunks_fts  FTS5 externo sobre chunks (text, title, heading), tokenizer unicode61 remove_diacritics 2
links       id, from_note→notes, to_title, to_note (nullable), kind
embeddings  (chunk_id→chunks, model) PK, dim, vec BLOB float32     -- dois modelos convivem para o bench
```

`title` é copiado para cada chunk de propósito: o FTS externo só enxerga colunas da tabela de
conteúdo. `remove_diacritics 2` faz `retencao` achar `retenção`. Índice de schema diferente do
código levanta `SchemaMismatch` nas duas pontas; a saída é `build --full`. v1 → v2 mudou a chave
de `embeddings` para `(chunk_id, model)`.

## Build (`IndexWriter`)

1. Lock `index.lock` com o PID. PID vivo → `IndexLocked`. PID morto ou ilegível → lock órfão,
   removido, uma tentativa a mais. No Windows a checagem usa `tasklist`, porque `os.kill(pid, 0)`
   mata o processo.
2. Uma transação para o build do corpus. Falha no meio → rollback, índice anterior intacto.
3. Por nota: `mtime` e `size` iguais aos do índice → nem lê o arquivo. `mtime` diferente com
   sha256 igual (toque do OneDrive) → só atualiza `mtime`. sha256 diferente → apaga os chunks
   antigos do FTS com o comando `'delete'`, apaga a nota (cascata em chunks, links, embeddings) e
   reinsere. Nota reescrita perde os vetores junto com os chunks; o próximo `embed` repõe.
4. Arquivo que sumiu do disco sai do índice.
5. Links resolvem no fim, em Python: stem igual → caminho igual → sufixo `/Nome.md` quando o alvo
   tem `/`. Empate no stem: caminho mais curto, como o Obsidian.
6. `--embed`: sob o mesmo lock, `embed_missing` gera os vetores dos chunks sem embedding para o
   modelo (ativo, ou o padrão), com commit a cada 256 chunks; ao terminar grava
   `meta.embedding_model`.
7. Nota que não parseia entra em `report.warnings`; o build segue.
8. Sob pytest, `IndexWriter` recusa o `index_dir` real (`PYTEST_CURRENT_TEST` no ambiente).

## Embeddings (`embed.py`)

- Dois candidatos em `MODELS`, ambos exportações int8 (`onnx/model_quint8_avx2.onnx`) da
  sentence-transformers, com sha256 do modelo e do tokenizer fixos no código:
  `all-MiniLM-L6-v2` (23 MB, janela 256 tokens, EN) e `paraphrase-multilingual-MiniLM-L12-v2`
  (118 MB, janela 128, 50 línguas). `DEFAULT_MODEL` (override `TECHCOLAB_EMBED_MODEL`) é o que
  `embed` usa quando não há modelo ativo; a escolha e os números estão no ADR §8.
- `ensure_model` baixa o que falta por HTTPS direto e confere o hash a cada carga; hash errado
  apaga o arquivo e levanta `ModelUnavailable`. Sem arquivo e com download desligado (caso da
  busca), a busca segue em `fts-only` e diz isso em `note`.
- `Embedder`: tokenizer da `tokenizers` (truncamento na janela do modelo, padding por lote),
  sessão `onnxruntime` CPU, `last_hidden_state` → média ponderada pela máscara → L2. O texto
  embutido de um chunk é `título \n heading \n texto`, para o vetor carregar o contexto que uma
  fatia de 900 caracteres sozinha não tem.
- `load_vectors` traz todos os vetores do modelo como matriz numpy (17 mil × 384 float32 ≈
  26 MB, 0,3 s); o cosseno é um produto de matriz. Sem `sqlite-vec`.

## Busca (`search.py`)

1. `fts_match_expression`: tokens `\w+`, cada um entre aspas (assim `and`, `or`, `not` são
   palavras), unidos por `OR`. Tokens de 2 letras (`do`, `de`, `em`) caem quando existe token
   maior; sozinhos só trazem ruído. Tokens com 5+ caracteres ganham `*` (prefixo cobre flexão
   em português sem stemmer).
2. Fluxo `fts`: FTS5 `bm25(text=1, title=4, heading=2)`, 60 melhores chunks, `snippet()` com
   marcadores `[ ]`. Fluxo `vec`: embedding da query, cosseno contra todos os vetores do modelo
   ativo, 60 melhores chunks. `--streams` liga e desliga cada um.
3. Filtros por nota: sensível (fora por padrão; as omitidas são contadas em
   `excluded_sensitive_hits`), `type`, prefixo de pasta, `since`/`until`/`as_of` pela `date`.
4. Fusão RRF com **k = 20**, por nota, na primeira aparição do chunk em cada fluxo. k pequeno de
   propósito: com k = 60 as posições 1 e 3 diferem 3 % e qualquer multiplicador reordena o topo;
   com k = 20 a diferença é 9 %, e um empurrão de 8 % passa uma decisão da posição 2 para a 1,
   mas não da 3 para a 1.
5. Vizinhança por wikilink: uma nota ligada (em qualquer direção) a uma nota classificada acima
   dela, entre as 5 primeiras, recebe ×1,05 e `link` em `why`. Só entre notas já recuperadas;
   não cria candidato novo.
6. Autoridade, multiplicador limitado a [0,8 · 1,2]:

   | Condição | × |
   |---|---|
   | `type` em decision, adr, person, project, area, reference | 1,08 |
   | `type` em session, daily, agent-report, capture | 0,95 |
   | idem, com `date` há mais de 90 dias | 0,9 a mais |
   | caminho em `Archive/` | 0,95 |
   | `pinned: true` no frontmatter | 1,1 |

   Os valores do ADR (1,15 / 0,72 / [0,7 · 1,3]) eram fortes demais para a curva do RRF; foram
   reduzidos na execução e o ADR registra a mudança.
7. `--as-of D`: notas datadas até D e, quando a raiz do corpus é um repositório git, cada
   resultado traz `changed_since_as_of` (houve commit no arquivo depois de D). Aproximado por
   desenho: a `date` é do frontmatter, o histórico é do git.
8. Saída (`--json`): `query`, `mode` (`hybrid` | `fts-only` | `vec-only`), `model`, `match`,
   `last_build`, `index_age_seconds`, `embeddings_stale_chunks`, `refreshed`, `filters`,
   `streams`, `candidates` por fluxo, `excluded_sensitive_hits`, `excluded_by_filter`, `note`
   (quando um fluxo não rodou, e por quê) e `results[]` com `rank`, `path`, `title`, `type`,
   `date`, `date_source`, `sensitive`, `has_frontmatter`, `score`, `authority`, `why`, `vec_sim`
   (quando o vetor achou) e até 2 `snippets` com `heading` e `from` (`fts` | `vec`).

## Bench (`bench.py`)

Golden set JSONL em `App/Personal toolkit/bench/golden.jsonl` (vault, nunca repo): `{"q", "expect"}`,
38 perguntas reais em 2026-09-03, várias em PT sobre notas com título em EN de propósito. Para
cada modelo e modo (`fts`, `vec`, `hybrid`), `hit@1`, `hit@k`, `mrr`, `missed`, e o rank de cada
pergunta com `--details`. Roda com `include_sensitive=True`: mede recuperação, não política.

## Briefing (`briefing.py`)

Zero LLM. Última sessão em `AI/sessions/` (último bloco `# Session` do arquivo mais recente:
contexto para a próxima sessão, threads abertos, itens `- [ ]`), ledger via `agent.pending` em
processo (mesmo `_load` e mesmo filtro do `list`; o CLI por subprocess é o fallback), notas com mtime
nos últimos N dias (fora `Daily/` e sessões), decisões (`type` decision/adr) dos últimos 30 dias,
ideias do backlog que mexeram, estado do índice. Sensível fora, salvo `--sensitive`. Cabeçalhos
de seção em EN ou PT são reconhecidos (`SECTION_ALIASES`).

## Lint (`lint.py`)

Só lê o índice; grava `_reports/Vault-Lint.md` (frontmatter `type: lint-report`), a menos que
`--no-write`. Seções: wikilinks quebrados (por alvo, com fontes), notas sem frontmatter, com
frontmatter mas sem `type` (por pasta), nomes de arquivo duplicados (o Obsidian resolve
`[[Nome]]` para um só), marcadores `as of YYYY-MM` com mais de 6 meses, ligações tipadas com
resolução e contradições em aberto (`contradicts` cujo alvo ou origem não foi superado), e notas
sensíveis só pelo `type` fora de `Team/` e `Stakeholders/`. A contradição semântica continua
sendo do `/obsidian-reconcile`.

## Números (vault real, 2026-09-03)

1.071 notas indexadas (~80 em pastas excluídas) · 16.960 chunks de até 600 caracteres · 1.995
links, 1.248 resolvidos · 262 sensíveis · 144 sem frontmatter · índice de 52 MB com um modelo ·
build completo 1,3 s com cache de arquivo quente, ~28 s frio · incremental sem mudança 0,08 s ·
`check` 0,35 s · busca `fts` 0,3 s · busca híbrida fria na CLI ~12 s (carga do modelo), ~1 s no
MCP depois da primeira · embedding completo 11m09 (16.960 chunks, multilíngue) · bench: híbrido
hit@1 0,289 · hit@5 0,763 · MRR 0,486 sobre 38 perguntas (FTS puro 0,237 · 0,605 · 0,394).
Tabela completa e comparação de modelos: ADR §8.

## Testes

`tests/test_vaultindex.py` (25) e `tests/test_vaultindex_hybrid.py` (17), mini-vault sintético em
`tmp_path`, embedder falso (bag of words com hash) para a plumbing vetorial. Cobrem: pastas
excluídas, incremental (igual, alterado, apagado, FTS acompanhando), `--full`, metadados sem
frontmatter, resolução de links, `check` independente, sensível fora e dentro, acento, filtros,
refresh, índice ausente (exit 2), lock (exit 3), lock órfão, chunking com offsets, frontmatter
quebrado, autoridade, `embed_missing` idempotente, dois modelos convivendo, modos `hybrid` /
`vec-only` / `fts-only` com `note`, vizinhança, `as_of`, bench por modo, extração da última
sessão, briefing com ledger injetado, lint com relatório.

## Operação

Tarefa agendada `TechColab Vault Index` (diária 18:00, `scripts/vault-index-nightly.ps1`,
instalada por `scripts/install-vault-index-task.ps1`) roda `build --embed` e depois `lint` com o
`.venv` do repo e loga em `logs/vault-index-YYYY-MM.log`. Registrada em
`docs/scheduled-automation.md`. A busca
também refresca o FTS antes de responder; só os vetores das notas novas esperam a noite, e a
resposta diz quantos chunks estão sem vetor.
