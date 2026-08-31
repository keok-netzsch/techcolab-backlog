# Tutorial — TechColab Backlog CLI

## Pré-requisitos

- Ollama rodando em background
- Terminal aberto em `%USERPROFILE%\techcolab-backlog`

### Verificar e corrigir cada pré-requisito

#### Ollama

```powershell
ollama list
```

| Resultado | O que fazer |
|---|---|
| Lista de modelos aparece | ✅ Tudo certo |
| `connection refused` ou erro | Abra o app **Ollama** pela barra de tarefas ou rode `ollama serve` no terminal |
| `'ollama' is not recognized` | Ollama não está instalado — baixe em [ollama.com/download](https://ollama.com/download) |
| Lista vazia (sem modelos) | Rode `ollama pull llama3.2:3b` para baixar o modelo (~2 GB) |

Após iniciar o Ollama, confirme que o modelo responde:

```powershell
ollama run llama3.2:3b "olá"
```

#### Python e dependências

```powershell
python --version          # deve ser 3.10+
pip show openai pyyaml    # ambos devem aparecer
```

Se algum pacote estiver faltando:

```powershell
cd %USERPROFILE%\techcolab-backlog
pip install -r requirements.txt
```

#### Vault e pasta Notes

```powershell
Test-Path "%USERPROFILE%\OneDrive - NETZSCH\Documents\TechColab_D&A_KO\Notes"
```

Deve retornar `True`. Se retornar `False`, crie a pasta manualmente no Obsidian ou pelo Explorer.

---

## 1. Adicionar novas ideias

### O caminho normal: `create_idea.py` (use este)

Ideia nasce em conversa — no Claude, numa nota, num WhatsApp encaminhado — não dentro do
app. Quando a conversa produzir algo que vale guardar, cadastre direto:

```bash
python ~/techcolab-backlog/agent/create_idea.py --title "..." --description "..." --todo "Primeiro passo"
```

Funciona de qualquer pasta e nas duas contas do CLI (`claude` e `claude-api`): é Python
puro sobre o `BacklogStore`, sem chamada de LLM. O ID é atribuído sozinho e título
duplicado é recusado.

**Nunca escreva `idea-NNN.md` na mão** — é assim que entra divergência de schema e ID
duplicado. Para texto com acento, prefira `--json arquivo.json` em vez das flags: o
quoting do shell no Windows corrompe acentuação vinda de stdin.

Para **mudar o status** de uma ideia que já existe, o script é outro:

```bash
python ~/techcolab-backlog/agent/update_status.py idea-081 "em desenvolvimento"
```

Detalhe completo das flags: `CLAUDE.md`, seção "Capturing a new idea".

### O caminho alternativo: ingestão de notas soltas

Ainda existe, e serve para quando você já escreveu bastante texto livre e quer que o
modelo extraia as ideias. Crie (ou edite) qualquer arquivo `.md` na pasta de notas do
vault:

```
%USERPROFILE%\OneDrive - NETZSCH\Documents\TechColab_D&A_KO\App\Personal toolkit\notes\
```

Escreva livremente — o modelo entende texto não estruturado. Exemplos do que funciona:

```markdown
Ideia: criar pipeline automatizado de ingestão de dados do SAP para o Power BI,
eliminando o processo manual de exportação de relatórios toda segunda-feira.
Impacto alto — economiza ~3h/semana por analista.
```

```markdown
Automatizar envio de relatório de KPIs por e-mail toda sexta às 17h.
Próximos passos: mapear destinatários, definir template, ver se Power Automate resolve.
```

Depois de salvar o arquivo, rode:

```powershell
python main.py ingest
```

O sistema vai:
1. Detectar os arquivos `.md` novos (sem a tag `<!-- techcolab:ingested -->`)
2. Enviar para o modelo Ollama extrair as ideias
3. Salvar cada ideia como `idea-NNN.md` na pasta `backlog items/` do vault
4. Marcar a nota original como processada
5. Regenerar o `_index.md`

> **Nota:** arquivos já processados são ignorados automaticamente. Para reprocessar uma nota, remova a linha `<!-- techcolab:ingested -->` do final do arquivo.

---

## 2. Ver o backlog

### Listar todas as ideias

```powershell
python main.py backlog list
```

Saída:

```
ID      Título                               Status                  Prior.    Criado
------  -----------------------------------  ----------------------  --------  ------------
idea-001  Dashboard de KPIs em tempo real    backlog                 alta      2026-05-15
idea-002  Bloco de Notas com Pendências      backlog                 média     2026-05-15
```

### Filtrar por status

```powershell
python main.py backlog list --status "em análise"
python main.py backlog list --status backlog
```

### Ver detalhes de uma ideia

```powershell
python main.py backlog show idea-001
```

Mostra: título, status, prioridade, área, origem, descrição completa e to-dos.

---

## 3. Atualizar ideias

### Mudar status

```powershell
python main.py backlog update idea-001 --status "em análise"
```

**Fluxo de status válidos:**

```
backlog
  └─► em análise
        ├─► análise - aprovado
        │     └─► aguardando desenvolvimento
        │               └─► em desenvolvimento
        │                         └─► em validação
        │                               ├─► concluído
        │                               └─► descartado
        └─► análise - rejeitado
```

### Mudar prioridade

```powershell
python main.py backlog update idea-001 --priority alta
python main.py backlog update idea-002 --priority baixa
```

Valores válidos: `alta` | `média` | `baixa`

### Mudar área

```powershell
python main.py backlog update idea-001 --area "automação"
```

### Combinar atualizações

```powershell
python main.py backlog update idea-001 --status "em análise" --priority alta --area "dados"
```

---

## 4. Editar uma ideia manualmente

Os arquivos de ideia ficam em:

```
%USERPROFILE%\OneDrive - NETZSCH\Documents\TechColab_D&A_KO\backlog\ideias\
```

Cada arquivo `idea-NNN.md` tem este formato:

```markdown
---
id: idea-001
titulo: "Dashboard de KPIs em tempo real"
status: backlog
prioridade: alta
area: dados
origem: notes/Ideas.md
criado_em: 2026-05-15
atualizado_em: 2026-05-15
---

## Descrição
Descrição gerada pelo modelo.

## To-dos
- [ ] Próximo passo 1
- [x] Próximo passo concluído

## Notas
Observações livres que você queira adicionar manualmente.
```

Você pode editar diretamente no Obsidian — checkboxes de to-do funcionam nativamente.

---

## 5. Reprocessar uma nota já ingerida

Se quiser que o modelo reanalise uma nota (ex: você a atualizou com mais conteúdo):

1. Abra o arquivo `.md` em `Notes/` no Obsidian ou editor de texto
2. Remova a última linha: `<!-- techcolab:ingested -->`
3. Salve o arquivo
4. Rode `python main.py ingest` novamente

> **Atenção:** isso vai criar novas ideias a partir da nota — ideias anteriores geradas por ela **não** são removidas automaticamente. Delete manualmente as duplicadas se necessário.

---

## 6. O loop de decisão — Weekly Brief e Closer (Toolkit 2.0)

Esta é a parte que substituiu o pipeline diário. Vale entender, porque é onde as decisões
acontecem de fato.

**O que morreu:** o `/plan` diário e a seção "Ações propostas" do relatório, com
checkboxes para marcar. Em 86 relatórios ela emitiu 1.986 checkboxes e colheu 32
aprovações (1,6%, nenhuma nas duas últimas semanas). A análise era boa; o mecanismo —
abrir arquivo, marcar caixa, esperar um ciclo — não. **Não reintroduza.**

**O que existe hoje, e como você usa:**

| Quando | O quê | Seu papel |
|---|---|---|
| Diário, 07:00 | Relatório de saúde (`TechColab Backlog Agent`): testes, vault alcançável, itens vencidos/parados, bugs abertos | Nada. Ele **afirma**, não pergunta |
| 1ª execução da semana | **Weekly Brief** em `{VAULT_ROOT}/weekly-briefs/brief-YYYY-Wnn.md`: no máximo 5 itens, cada um uma pergunta com duas opções | Ler |
| Segunda, 08:30 | **Closer** (rotina agendada do Claude): lê o brief + backlog e redige a ação de cada ponto aberto | Responder **em uma linha** |

O Closer entrega cada ponto num de três formatos: `[PRONTO]` (texto pronto para enviar),
`[RECOMENDO]` (decisão com racional) ou `[FEITO]` (status já reconciliado com evidência).

**Como responder:** em conversa, numa linha — *"aprova A e C, descarta B"*. Não existe
caixa para marcar. O que você aprovou é então aplicado com `update_status.py` ou pelas
ferramentas MCP do vault.

Truncamento é sempre reportado: se havia mais de 5 candidatos, o brief diz quantos ficaram
de fora — nunca corta em silêncio.

## 7. Referência rápida de comandos

| Ação | Comando |
|---|---|
| **Cadastrar ideia (caminho normal)** | `python agent/create_idea.py --title "..." --description "..."` |
| Cadastrar com acento/texto longo | `python agent/create_idea.py --json payload.json` |
| Validar sem gravar | `python agent/create_idea.py --json payload.json --dry-run` |
| **Mudar status** | `python agent/update_status.py idea-081 "em validação"` |
| Ingerir novas notas | `python main.py ingest` |
| Preview sem escrever | `python main.py ingest --dry-run` |
| Listar ideias | `python main.py backlog list` |
| Filtrar por status | `python main.py backlog list --status "em análise"` |
| Ver detalhes | `python main.py backlog show idea-001` |
| Atualizar status | `python main.py backlog update idea-001 --status "concluído"` |
| Atualizar prioridade | `python main.py backlog update idea-001 --priority alta` |
| Atualizar área | `python main.py backlog update idea-001 --area "produto"` |
