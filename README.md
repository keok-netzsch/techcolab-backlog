# Personal Toolkit · Techco.lab

Aplicativo local de gestao de backlog com inteligencia artificial, construido com **Streamlit**, integrado ao **Obsidian** e rodando um modelo de linguagem local via **Ollama**. Nenhuma chave de API externa e necessaria.

---

## Indice

1. [Pre-requisitos](#pre-requisitos)
2. [Instalacao](#instalacao)
3. [Configuracao](#configuracao)
4. [Download do modelo Ollama](#download-do-modelo-ollama)
5. [Iniciando o aplicativo](#iniciando-o-aplicativo)
6. [Solucao de problemas](#solucao-de-problemas)
7. [Estrutura do projeto](#estrutura-do-projeto)

---

## Pre-requisitos

Instale os itens abaixo antes de prosseguir:

| Ferramenta | Versao minima | Download |
|---|---|---|
| Python | 3.10 | https://www.python.org/downloads/ |
| Ollama | Qualquer recente | https://ollama.com/download |
| Obsidian | Qualquer recente | https://obsidian.md/ |
| Git (opcional) | Qualquer recente | https://git-scm.com/download/win |

> **Dica:** Ao instalar o Python no Windows, marque a opcao **"Add Python to PATH"** antes de clicar em Install Now.

---

## Instalacao

### Opcao 1 — Usando o script automatico (recomendado)

1. Abra a pasta do projeto no Explorer.
2. De duplo clique em **`install.bat`**.
3. Aguarde a instalacao das dependencias. Ao final, uma mensagem de confirmacao sera exibida.

### Opcao 2 — Instalacao manual

Abra o Prompt de Comando (cmd) ou PowerShell na pasta do projeto e execute os comandos abaixo em sequencia:

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

---

## Configuracao

Abra o arquivo **`config.py`** em qualquer editor de texto (Notepad, VS Code, etc.) e ajuste a variavel `VAULT_ROOT` para apontar para a pasta raiz do seu cofre (vault) do Obsidian:

```python
# Caminho para a raiz do seu cofre (vault) do Obsidian
VAULT_ROOT = r"C:\Users\SeuUsuario\Documents\MeuVault"
```

**Como encontrar o caminho do vault:**

1. Abra o Obsidian.
2. Va em **Configuracoes** (icone de engrenagem) > **Sobre** > **Vault path**.
3. Copie o caminho exibido e cole no campo `VAULT_ROOT` entre aspas, precedido de `r` (raw string), conforme o exemplo acima.

> **Atencao:** Use `r"..."` antes das aspas (raw string) para evitar problemas com barras invertidas no Windows. Exemplo correto: `r"C:\Users\Kelvin\Documents\Vault"`.

---

## Download do modelo Ollama

O aplicativo utiliza o modelo **llama3.2:3b** por padrao. Para baixa-lo, abra o Prompt de Comando e execute:

```bat
ollama pull llama3.2:3b
```

O download pode levar alguns minutos dependendo da sua conexao. O modelo ocupa aproximadamente **2 GB** em disco.

Para verificar se o modelo foi instalado corretamente:

```bat
ollama list
```

O modelo `llama3.2:3b` deve aparecer na lista.

---

## Iniciando o aplicativo

### Opcao 1 — Duplo clique (mais facil)

De duplo clique no arquivo **`start_app.bat`** na pasta do projeto. O navegador sera aberto automaticamente com o aplicativo em execucao.

### Opcao 2 — Linha de comando

Abra o Prompt de Comando na pasta do projeto e execute:

```bat
.venv\Scripts\activate
streamlit run app.py
```

O aplicativo ficara disponivel em: **http://localhost:8501**

---

## Solucao de problemas

### Ollama nao esta rodando

**Sintoma:** O aplicativo exibe erro de conexao com o modelo ou mensagem como `Connection refused`.

**Solucao:**
1. Abra o menu Iniciar e procure por **Ollama**.
2. Inicie o aplicativo Ollama — ele ficara na bandeja do sistema (proximo ao relogio).
3. Aguarde alguns segundos e recarregue a pagina do aplicativo.

Voce pode confirmar que o Ollama esta ativo abrindo o navegador em: `http://localhost:11434`

---

### O aplicativo exibe dados antigos ou desatualizados

**Sintoma:** Itens do backlog nao refletem as alteracoes feitas no Obsidian.

**Solucao:**
1. Clique no botao **Recarregar** ou **Atualizar** dentro do proprio aplicativo (se disponivel).
2. Caso nao haja botao, pressione **F5** no navegador para forcar o recarregamento.
3. Verifique se o caminho `VAULT_ROOT` em `config.py` aponta para a pasta correta do vault.

---

### Porta 8501 ja esta em uso

**Sintoma:** Ao iniciar o app, aparece o erro `Port 8501 is already in use`.

**Solucao A — Encerrar o processo que ocupa a porta:**

```bat
netstat -ano | findstr :8501
taskkill /PID <numero_do_pid> /F
```

Substitua `<numero_do_pid>` pelo numero exibido na coluna final do resultado do `netstat`.

**Solucao B — Iniciar em outra porta:**

```bat
streamlit run app.py --server.port 8502
```

---

### Erro "python nao e reconhecido como comando"

O Python nao esta no PATH do sistema. Reinstale o Python marcando a opcao **"Add Python to PATH"** durante a instalacao, ou adicione manualmente o caminho do Python nas variaveis de ambiente do Windows.

---

### Erro ao instalar dependencias (pip)

Verifique se o ambiente virtual foi ativado antes de rodar o `pip install`:

```bat
.venv\Scripts\activate
pip install -r requirements.txt
```

Se o erro persistir, tente atualizar o pip primeiro:

```bat
python -m pip install --upgrade pip
pip install -r requirements.txt
```

---

## Estrutura do projeto

```
techcolab-backlog/
├── app.py               # Aplicativo principal (Streamlit)
├── config.py            # Configuracoes (VAULT_ROOT, etc.)
├── requirements.txt     # Dependencias Python
├── install.bat          # Script de instalacao automatica
├── start_app.bat        # Script para iniciar o aplicativo
└── README.md            # Este arquivo
```

---

## Suporte

Em caso de duvidas, verifique se todos os pre-requisitos estao instalados corretamente e se o Ollama esta em execucao antes de iniciar o aplicativo.
