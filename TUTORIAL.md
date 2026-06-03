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

Crie (ou edite) qualquer arquivo `.md` na pasta do vault:

```
%USERPROFILE%\OneDrive - NETZSCH\Documents\TechColab_D&A_KO\Notes\
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
3. Salvar cada ideia como `idea-NNN.md` na pasta `backlog/ideias/`
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

## 6. Referência rápida de comandos

| Ação | Comando |
|---|---|
| Ingerir novas notas | `python main.py ingest` |
| Preview sem escrever | `python main.py ingest --dry-run` |
| Listar ideias | `python main.py backlog list` |
| Filtrar por status | `python main.py backlog list --status "em análise"` |
| Ver detalhes | `python main.py backlog show idea-001` |
| Atualizar status | `python main.py backlog update idea-001 --status "concluído"` |
| Atualizar prioridade | `python main.py backlog update idea-001 --priority alta` |
| Atualizar área | `python main.py backlog update idea-001 --area "produto"` |
