# FAQ — TechColab Backlog & Agente Diário

Perguntas frequentes e situações recorrentes registradas durante o desenvolvimento.

---

## App / Vault

### Uma ideia criada fora do app não aparece mesmo após "Recarregar vault" + F5

**Causa provável:** o arquivo `.md` foi criado pelo PowerShell sem especificar encoding e saiu com BOM (UTF-8 with BOM ou UTF-16). O `BacklogStore` usa o regex `^---\n` para detectar o frontmatter YAML — bytes de BOM antes do `---` quebram o match e o arquivo é silenciosamente ignorado.

**Como verificar:**
```python
with open("idea-NNN.md", "rb") as f:
    print(list(f.read(5)))  # [239, 187, 191, ...] = BOM UTF-8
```

**Solução:** reescrever o arquivo via Write tool do Claude Code ou via Python:
```python
with open("idea-NNN.md", "w", encoding="utf-8") as f:
    f.write(conteudo)
```

**Regra:** nunca criar arquivos de backlog via PowerShell puro. Usar sempre o Claude Code Write tool ou `store.save()` via Python.

---

### Qual a diferença entre "Recarregar vault", F5 e reiniciar a app?

| Ação | O que faz | Quando usar |
|---|---|---|
| Botão "Recarregar vault" | Recria o `BacklogStore` em memória, relê todos os `.md` do disco | Depois de editar um arquivo existente no Obsidian |
| F5 (browser) | Recarrega a página Streamlit sem reiniciar o processo Python | Atualiza UI, não relê disco |
| Reiniciar a app (atalho/bat) | Mata o processo e reinicia tudo do zero | Depois de mudanças no código (`app.py`, `config.py`, etc.) |

**Nota:** mudanças em código Python exigem reiniciar a app. "Recarregar vault" só relê os arquivos `.md`.

---

### Alterei o `app.py` mas a mudança não aparece

Precisa reiniciar a app completamente. O botão "Recarregar vault" não recarrega código Python — só os dados do vault. Use o atalho da área de trabalho para fechar e reabrir.

---

## PowerShell

### Erro ao escrever arquivo grande com here-string (`ENAMETOOLONG` ou string truncada)

PowerShell tem limite prático para here-strings muito longas (especialmente com HTML). A solução é escrever via Python:

```powershell
python -c "
content = '''...conteudo...'''
with open('arquivo.html', 'w', encoding='utf-8') as f:
    f.write(content)
"
```

Ou criar um script `.py` temporário e executá-lo.

---

### `[System.IO.File]::WriteAllText()` gera arquivo com encoding errado

Sem o terceiro parâmetro de encoding, o método usa o encoding padrão do sistema (pode ser UTF-16 LE com BOM). Sempre especificar:

```powershell
$enc = [System.Text.UTF8Encoding]::new($false)  # false = sem BOM
[System.IO.File]::WriteAllText($path, $content, $enc)
```

Ou, mais simples: delegar para o Claude Code Write tool.

---

## Agente Diário

### O agente marcou to-dos como `[x]` mas o trabalho não foi feito

Isso acontece quando o agente executa ações do relatório diário que listam to-dos — ele pode erroneamente marcar como concluídos itens que apenas "viu" ou "planejou".

**Protocolo correto:**
- `[x]` só deve ser marcado quando o to-do foi **implementado, testado e commitado**
- Ao iniciar trabalho: `python agent/update_status.py <id> "em desenvolvimento"`
- Ao concluir: `python agent/update_status.py <id> "em validação"` (ou `"concluído"`)
- Nunca marcar `[x]` manualmente a menos que o trabalho tenha sido verificado

---

### Como saber se o `execute_agent.bat` funcionou?

O fluxo correto é:
1. `execute_agent.bat` copia o comando para o clipboard
2. Abre o Claude Code na pasta do projeto
3. Você cola o comando: `Execute the approved items from today's agent report`

Se o terminal fechar sem abrir o Claude Code, é o bug registrado em **idea-017** (to-do aberto). Por enquanto: abrir o Claude Code manualmente em `%USERPROFILE%\techcolab-backlog` e colar o comando.

---

### O relatório do Claude Pro Report não atualiza as datas

O `_update_claude_pro_report()` em `agent/daily_report.py` atualiza via regex três pontos do HTML:
1. `Atualizado em: DD/MM/YYYY`
2. `stat-number` antes de `Dias desde adoção`
3. `Relatório atualizado em DD/MM/YYYY` no footer

Se algum desses textos for alterado no HTML (ex: refatoração visual), os regex param de casar silenciosamente. Verificar os padrões em `daily_report.py` se as datas pararem de atualizar.

---

## GitHub / Deploy

### Onde está o Claude Pro Report?

O relatório é uma página nativa do Streamlit — acesse **Claude Pro** no menu lateral do app. Não existe mais HTML estático nem dependência de GitHub Pages. Os dados vêm de `reports/claude-pro-data.json` e `reports/claude-pro-timeline.json`, atualizados automaticamente pelo agente diário.

---

### Ao tentar fazer `git push`, aparece erro de repositório não encontrado

Verificar se o remote correto está configurado:
```bash
git remote -v
# deve apontar para https://github.com/keok-netzsch/techcolab-backlog
```

---

## Obsidian / Vault

### Editei um to-do diretamente no Obsidian mas o app não refletiu

Pressionar "Recarregar vault" na barra lateral do app. O Streamlit não observa o filesystem em tempo real — o reload é manual e intencional.

---

### Como criar uma nova ideia manualmente (fora do app)?

Criar o arquivo `idea-NNN.md` na pasta `Backlog - to do - app/backlog items/` com o frontmatter YAML exato. **Obrigatório:** usar UTF-8 sem BOM. Template mínimo:

```markdown
---
area: ''
atualizado_em: 'YYYY-MM-DD'
criado_em: 'YYYY-MM-DD'
due_date: ''
esforco: medio
id: idea-NNN
impacto: media
origem: entrada direta
prioridade: media
status: backlog
titulo: Titulo da ideia
---

## Descricao
...

## To-dos
- [ ] Primeiro to-do

## Notas
_sem notas_
```

---

---

## To-Do List

### Cliquei no número da ideia na To-Do List mas nada aconteceu

**Causa:** o botão de navegação escrevia em `st.session_state["page"]`, mas a app determina a página via `st.query_params.get("page")` — a session state nunca era lida, então a navegação silenciosamente falhava.

**Correção aplicada (2026-05-27):** o botão agora usa `st.query_params["page"] = "Backlog"`, que atualiza o URL e dispara o rerun com a página correta. O estado de expansão da ideia (`exp_{id}`) é gravado na session state antes da navegação e persiste normalmente.

---

### Adicionei um to-do mas o campo `is_bug` não apareceu no arquivo

O marcador `{bug}` é anexado ao final da linha do to-do no arquivo `.md`. Exemplo:

```
- [ ] Fix crash {bug}
```

Se o to-do foi adicionado via código externo (não pelo app) sem incluir esse sufixo, o campo `is_bug` aparecerá como `False` ao carregar. Corrigir diretamente no arquivo `.md` adicionando `{bug}` ao final da linha.

## Busca no vault (`vaultindex`)

### Como busco algo no vault sem abrir o Obsidian?

```bat
python -m vaultindex search "retenção call recorder"
python -m vaultindex search --json -k 5 "quem é o dono do BIA-019"
```

Cada resultado traz título, `type`, data, caminho e um trecho com os termos marcados em `[ ]`.
A primeira linha diz a idade do índice; a busca já roda um build incremental antes de responder.
Filtros: `--type decision`, `--folder Projects/`, `--since 2026-08-01`, `--until 2026-08-31`.
Na F2 a mesma busca vai estar disponível no chat pelo tool `vault_search` do MCP `techcolab-vault`.

### Sei que a nota existe e ela não aparece

Três causas, nesta ordem:

1. **É sensível.** `Team/`, `Stakeholders/` e notas com `type` de 1:1 ficam fora por padrão. A
   primeira linha da resposta mostra `N nota(s) sensível(is) fora`. Rode de novo com `--sensitive`.
2. **Está numa pasta que o índice ignora:** `Templates/`, `rollback/`, qualquer `backup*`,
   `_attachments/`, `.obsidian/`. Lista em `vaultindex/corpus.py` (`EXCLUDE_DIRS`).
3. **O índice divergiu do disco.** `python -m vaultindex check` lista o que mudou; `build` corrige.

### "Índice não encontrado em ..." (exit 2)

Ainda não existe índice nesta máquina. Rode `python -m vaultindex build`. Leva cerca de 1,5 s
para o vault inteiro. Isso é um erro de propósito: resposta vazia com exit 0 esconderia o problema.

### "outro build está com o índice (PID n)" (exit 3)

Um build está rodando. Espere e rode de novo. Se o PID não existir mais (processo morto), o
próximo `build` remove o lock órfão sozinho.

### Onde fica o índice e posso apagar?

`%LOCALAPPDATA%\techcolab\vault-index\index.sqlite`. Pode apagar a pasta inteira: é derivado do
vault e `python -m vaultindex build --full` refaz em segundos. Fica fora do OneDrive e do repo de
propósito (`docs/vault-index-governanca.md`).

---

*Atualizado em 2026-09-03. Para adicionar entradas, editar `docs/FAQ.md` diretamente.*
