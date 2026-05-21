# FAQ — Techco.lab · Claude Code

Erros recorrentes, gotchas e situações-chave documentados durante o desenvolvimento do Personal Toolkit.

---

## Streamlit

### `st.markdown('<div class="x">`) não envolve `st.columns()`

**Situação:** Tentativa de criar um seletor CSS `.x button { ... }` colocando um `st.markdown('<div class="x">')` antes de `st.columns()`.

**Por que não funciona:** O Streamlit renderiza cada chamada `st.markdown()` e `st.columns()` como elementos **irmãos** no DOM, nunca como pai-filho. A `<div class="x">` fica acima dos botões na árvore, não em volta deles.

**Solução correta:**
- Usar seletores baseados em `data-testid` nativos do Streamlit, ex: `[data-testid="stMainBlockContainer"] > div:first-child button`
- Ou usar HTML puro via `st.markdown()` com `unsafe_allow_html=True` para ter controle real sobre estrutura

---

### `st.header()` vs `<h1>` ficam com tamanhos diferentes

**Situação:** Algumas páginas usavam `st.header("Título")` e outras `st.markdown('<h1>Título</h1>')`. Resultado: fontes e cores inconsistentes entre páginas.

**Por que:** `st.header()` renderiza como `<h2>` no DOM — menor e sem herdar o CSS do `h1`. O `<h1>` HTML herda o gradiente verde da brand CSS.

**Solução:** Padronizar **todas** as páginas com:
```python
st.markdown('<h1 style="margin-bottom:0.4rem">Título</h1>', unsafe_allow_html=True)
```

---

### Sidebar colapsa e some completamente

**Situação:** O botão nativo `«` do Streamlit foi clicado. A sidebar colapsou. O botão para re-expandir estava oculto pelo CSS `overflow: hidden`.

**Por que:** `display: none` aplicado ao `[data-testid="stSidebarCollapseButton"]` ocultou o botão de **ambos** os estados (colapsar e expandir).

**Solução definitiva:** Substituir a sidebar por uma **top nav em HTML puro**, eliminando o problema de vez:
```python
st.markdown('<nav style="...">...</nav>', unsafe_allow_html=True)
```

---

### Top nav com `st.columns()` ocupa muito espaço vertical

**Situação:** Mesmo zerando todos os paddings via CSS (`padding: 0 !important`), a nav continuava grande.

**Por que:** O Streamlit injeta padding estrutural em vários níveis do DOM (`stHorizontalBlock`, `stColumn`, containers internos) que não é totalmente sobrescrevível via CSS externo.

**Solução:** HTML puro com `<nav>` — controle de altura absoluto, sem dependência do sistema de layout do Streamlit:
```python
st.markdown(
    '<nav style="display:flex;align-items:center;padding:5px 16px;'
    'border-bottom:1px solid rgba(0,0,0,0.09)">...</nav>',
    unsafe_allow_html=True
)
```

---

### Routing: `st.session_state` vs `st.query_params`

**Situação:** Com a sidebar, o routing era feito via `st.session_state["page"]` + `st.rerun()`. Com a top nav HTML pura (links `<a>`), os botões não existem mais para chamar `st.rerun()`.

**Solução com HTML nav:** Usar `st.query_params` — cada link vira `<a href="?page=X">` e o Streamlit recarrega automaticamente ao clicar:
```python
page = st.query_params.get("page", "Dashboard")
```

---

### `st.container(height=N, border=False)` para scroll interno

**Solução para listas longas com header fixo:**
```python
# Header FORA do container (fica fixo)
col1, col2 = st.columns([...])
col1.caption("Título")

# Dados DENTRO do container (scroll)
with st.container(height=600, border=False):
    for item in items:
        ...
```

---

### Linha dupla no separador de grupos

**Situação:** Apareciam duas linhas horizontais na To-Do List entre grupos.

**Por que:** O `<hr>` adicionado via `st.markdown()` somava com o `border-top` do CSS do label de grupo.

**Solução:** Remover o `<hr>` — usar apenas o `border-top` do CSS.

---

## CSS

### Comentário com `—` (em-dash) dentro de string Python causa SyntaxError

**Erro:** `SyntaxError: invalid character '—' (U+2014)`

**Por que:** O caractere `—` foi colocado **fora** das aspas de uma string Python, em código que parecia um comentário mas estava sendo interpretado como expressão.

**Solução:** Comentários CSS (`/* ... */`) só podem conter qualquer caractere quando estão **dentro** de uma string Python:
```python
# ERRADO — fora da string:
css = "color: red"
/* comentário — aqui fora quebra */

# CORRETO — dentro da string:
css = "color: red /* comentário — seguro */"
```

---

### Validar sintaxe sem rodar o app

```python
python -c "import ast; ast.parse(open('app.py', encoding='utf-8-sig').read()); print('OK')"
```

---

## Git / PowerShell

### PowerShell nativo do Claude Code falha com exit code 1

**Situação:** O tool `PowerShell` retorna `exit code 1` sem mensagem de erro em qualquer comando.

**Causa:** Problema de sandbox/sessão no tool nativo.

**Solução:** Usar o **Windows MCP PowerShell** (`mcp__Windows-MCP__PowerShell`) — funciona independentemente:
```python
mcp__Windows-MCP__PowerShell(command="cd C:\\...\\techcolab-backlog; git add -A; git commit -m '...'; git push")
```

---

### Commit padrão para fim de sessão

```powershell
cd C:\Users\Kelvin.okuda\techcolab-backlog
git add -A
git commit -m "tipo: descrição curta"
git push
```

Tipos: `feat` (novo), `fix` (bug), `style` (visual), `refactor`, `docs`, `chore`

---

## Backlog / To-Dos

### Status dos itens

| Status | Quando usar |
|---|---|
| `backlog` | Não iniciado |
| `em desenvolvimento` | Em andamento nesta sessão |
| `em validação` | Implementado, aguardando revisão/teste |
| `concluído` | Verificado e fechado |
| `descartado` | Cancelado |

### Marcar to-do como feito

```markdown
- [x] Descrição do to-do ~2026-05-21
```

O campo `~YYYY-MM-DD` registra a data de conclusão.

---

## Sessões

### Como retomar uma sessão de forma eficiente

Cole no início da sessão:
```
Continuando o desenvolvimento do Personal Toolkit · Techco.lab.
Leia o CLAUDE.md do projeto para contexto.
Último commit: [hash] — [mensagem]
O app roda em http://localhost:8501 (iniciar com start_silent.vbs).
Aguarde minha instrução para o foco de hoje.
```

### Como NÃO gastar tokens desnecessariamente

- **Não pedir para ler arquivos JSONL** (histórico de sessões) — são grandes e raramente necessários
- **Não spawnar Agent para buscas simples** — usar Grep/Glob/Read diretamente
- Para compilar FAQ ou resumos: Claude já tem o contexto da sessão atual carregado — não precisa reler nada
- Usar `head_limit` no Grep para limitar output de buscas amplas
