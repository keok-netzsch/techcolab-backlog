# vaultsources — conhecimento externo, camada de conceito e QA de consistência

> Documento de uso. A decisão de arquitetura está em
> `vault/decisions/2026-09-10-vaultsources-conhecimento-externo.md` (vault, local).
> A visão de conjunto do toolkit está em `ARCHITECTURE.md`.

## O que é

Em 2026-09-10 o vault tinha 1129 notas indexadas e **zero** vindas de fora. Este
pacote é o cano que resolve isso, mais a camada onde uma posição amadurece
(`Concepts/`), mais o QA que confere se a documentação deste ambiente continua
verdadeira.

Não são três integrações (YouTube, TikTok, LinkedIn). É **um cano com quatro
adaptadores**, porque as duas peças caras já estavam na máquina: `yt-dlp` e o
Whisper local do call-recorder.

## Instalação e pré-requisitos

```bash
python -m pip install -U yt-dlp youtube-transcript-api openpyxl
pwsh -File scripts/build-ca-bundle.ps1
```

O bundle de CAs não é opcional nesta rede. A NETZSCH inspeciona TLS, e sem ele toda
saída externa morre com `CERTIFICATE_VERIFY_FAILED`. O `yt-dlp` precisa ser o
**módulo Python**, não o `.EXE`: o executável congelado carrega o `certifi` embutido
e ignora `SSL_CERT_FILE`.

Confira tudo de uma vez:

```bash
python -m vaultsources qa --only deps --all
```

## O fluxo do dia a dia

### Trazer uma fonte que você já tem na mão

```bash
python -m vaultsources fetch "https://youtu.be/..." --question "por que isto importa"
```

Grava `Sources/<data>-<slug>.md` com `analysis: pending`. Transcrição acima de 4000
caracteres vai para `Sources/_transcripts/`. O `--question` é o que impede a pasta
de virar pilha de "ler depois": ela registra qual pergunta aberta puxou a fonte.

Funciona com YouTube, TikTok, Instagram, Vimeo, X e artigo web. **LinkedIn não**,
e o erro explica por quê.

### LinkedIn

```bash
python -m vaultsources clip --url "<url do post>" --title "<titulo>" \
  --author "<autor>" --text-file rascunho.txt
```

O texto vem da sessão que leu a página. Não há API aberta e raspar página logada
quebra a cada release deles.

### Assinar canal e playlist

```bash
python -m vaultsources watch add UCxxxxxxxxxxxxxxxxxxxxxx --label "IBM Technology" --topic governanca
python -m vaultsources watch add "https://www.youtube.com/@algumcanal"   # resolve o UC... sozinho
python -m vaultsources poll
python -m vaultsources queue --approve <video_id>
python -m vaultsources ingest
```

Playlist também tem RSS. É a porta de menor atrito: salvar na playlist pelo celular
e deixar o `poll` propor de manhã.

O score é determinístico e explica a escolha. Ele casa o título e a descrição contra
as **perguntas abertas** do sistema, não contra "relevância" genérica.

### Fechar a análise

```bash
python -m vaultsources analyse --list
python -m vaultsources analyse --apply analise.json
```

Formato do `analise.json` em `.claude/commands/youtube.md`. Cada `impact` com
`concept` vira proposta em `Concepts/_proposals/`.

### Fechar a análise

```bash
python -m vaultsources analyse --next 2                  # as mais antigas sem análise
python -m vaultsources analyse --show <arquivo.md>       # a nota e o texto, sem timestamps
python -m vaultsources analyse --apply analise.json
```

`--show` acha o texto onde quer que ele esteja: na própria nota, no sidecar de
transcrição, ou no cache local de quem foi gravado com `--no-raw`. Ele tira os
timestamps, que são cerca de 15% de uma legenda e não ajudam a decidir tese.

Antes de escrever a análise, rode `brief` no tema. É esse passo que torna
contradição possível: sem ele sai resumo, e resumo não muda decisão.

Cada `impact` com `concept` vira proposta em `Concepts/_proposals/`. Quem aprova é
o Kelvin, na rotina de sexta.

A rotina `analise-de-fontes` (diária, 17:00) faz isso sozinha, duas por dia.

### Conceitos

```bash
python -m vaultsources concept new --name "..." --stance "..." --why "..."
python -m vaultsources concept list
python -m vaultsources concept accept --file <proposta.json>
python -m vaultsources concept reject --file <proposta.json> --why "..."
```

### LinkedIn: métrica e matéria-prima

```bash
python -m vaultsources linkedin import          # lê o .xlsx mais recente de ~/Downloads
python -m vaultsources linkedin candidates --days 21
```

`import` reescreve o bloco gerado de `Areas/LinkedIn/performance-log.md`. Até
2026-09-10 aquela seção pedia digitação manual dentro do Obsidian e por isso ficou
com 3 posts em 3 meses.

`candidates` devolve **matéria-prima**, nunca post pronto. Texto assinado como
Kelvin passa pelo voice-gate, e o voice-gate mora na sessão.

### Dossiê antes da reunião

```bash
python -m vaultsources dossier "Stefan Lautenschlager"
python -m vaultsources dossier "Ana Leite" --json
```

Monta a matéria-prima do dossiê só com o que já está escrito: último 1:1 e seus
tópicos, compromissos em aberto com prazo, itens do ledger que citam a pessoa, o
que mudou desde o último encontro, projetos onde o nome aparece.

Determinístico de propósito. Nada aqui resume ou opina sobre pessoa: saída de
modelo que descreve gente propõe, não afirma (padrão 2 do `ARCHITECTURE.md`).

Consumidor: a rotina `dossie-do-dia` (dias úteis 07:45) lê a agenda e chama isto
para cada reunião com pessoa que o vault conhece. Tudo local — é conteúdo de
`Team/` e `Stakeholders/`, que o `governance.py` classifica como origem `vault` e
nunca deixa sair para provedor externo.

## O QA

```bash
python -m vaultsources qa            # só os erros
python -m vaultsources qa --all      # com os avisos
python -m vaultsources qa --json
python -m vaultsources qa --only refs,folders --offline
```

| Check | O que ele acha |
|---|---|
| `refs` | caminho citado em doc ou comando que não existe |
| `folders` | pasta descrita no Folder Map que não existe, e afirmação de vacuidade que envelheceu |
| `deadloops` | produtor declarado que não produz há N dias |
| `notes` | frontmatter incompleto, `text-sha256` que não bate, análise pendente há muito tempo |
| `placeholders` | `[data]`, `TBD`, `{{…}}` esquecidos no registro |
| `deps` | yt-dlp, legenda, whisper e a CA da rede corporativa |
| `governance` | purpose usado e não declarado, rede sem guarda, pergunta sensível na fila externa |
| `inbox` | captura parada esperando triagem |
| `duplicates` | arquivos com o mesmo nome (o Obsidian resolve `[[X]]` para um só) |

Saída em `_reports/Sources-QA.md`. Exit code 2 quando há achado de severidade `erro`.

**Por que este QA existe:** o braço de pesquisa ficou meses quebrado porque cinco
comandos apontavam para um repo inexistente. O código estava certo. Nenhum teste
pega isso.

## O tester

```bash
python -m vaultsources tester --limit 2
python -m vaultsources tester --dry-run
python -m vaultsources tester --search "data mesh governance"
```

Diferente da suíte de `tests/`, que roda offline com fixture: o tester sai na rede,
lê as perguntas abertas do Kelvin, **vai buscar material real** no YouTube e passa
o processo inteiro por oito estágios.

```
deps · questions · discover · fetch · roundtrip · concept · governance · qa
```

É também a forma de alimentar o cano no começo, quando a watchlist ainda está vazia.

## Quem lê o resultado

Padrão 12 do `ARCHITECTURE.md`: detector sem consumidor não protege nada.

| Saída | Consumidor |
|---|---|
| `_reports/Sources-QA.md` | rotina Claude `fontes-semanal` (sexta 16:15) |
| erros do QA | `scripts/notify.ps1 -Profile sources-qa` (dias úteis 08:50) |
| `Concepts/_proposals/` | a mesma rotina semanal, apresentada no chat para aprovação em uma linha |
| candidatos da fila | `python -m vaultsources queue`, apresentado no chat |

## Fronteira de dado

`vaultsources/governance.py`. A regra é sobre a **origem** do payload, não o destino.

| Provedor | Aceita |
|---|---|
| `local` | public, user, vault |
| `netzsch-gateway` | public, user, vault |
| `xai`, `perplexity` | public, user |

Buscar dado público de fora é seguro. Mandar texto do vault para fora não é.
`/research-deep` varre o vault e manda contexto para a Perplexity: está fora do
allowlist e a chamada é recusada, não degradada.

## Estado e quem escreve

| Arquivo | Escritor único |
|---|---|
| `Sources/_watchlist.json` | `python -m vaultsources watch` |
| `Sources/_queue.json` | `python -m vaultsources poll/queue/ingest` |
| `Concepts/_proposals/*.json` | `analyse --apply` e `concept propose` |
| `Areas/LinkedIn/_metrics.json` | `linkedin import` |
| `_reports/Sources-QA.md` | `qa` (saída gerada, reescrita do zero) |

Nenhum deles se edita à mão.

## Armadilhas conhecidas

| Sintoma | Causa |
|---|---|
| `CERTIFICATE_VERIFY_FAILED` | bundle ausente ou desatualizado depois de `pip install -U certifi`; rode `build-ca-bundle.ps1` |
| yt-dlp falha só quando chamado pelo `.EXE` | o executável congelado ignora `SSL_CERT_FILE`; use o módulo |
| `ParseError` na legenda | `youtube-transcript-api` antigo; a 1.0.3 quebrava e o código lia como "sem legenda" |
| Fonte cai no Whisper sem motivo | não deveria: falha técnica de legenda levanta `FetchError` de propósito |
| QA acusa hash divergente | alguém editou a transcrição depois de gravada |
