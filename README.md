# Personal Toolkit · Techco.lab

Aplicativo local de gestão de backlog com inteligência artificial, construído com **Streamlit**, integrado ao **Obsidian** e rodando um modelo de linguagem local via **Ollama**. Roda 100% offline — **nenhuma chave de API externa é necessária**.

> **Repositório PÚBLICO.** Contém apenas código. Os dados (vault Obsidian) vivem separados e nunca são versionados aqui — veja [SECURITY.md](SECURITY.md).

---

## Índice

1. [Pré-requisitos](#pré-requisitos)
2. [Instalação](#instalação)
3. [Configuração](#configuração)
4. [Modelo Ollama](#modelo-ollama)
5. [Iniciando o aplicativo](#iniciando-o-aplicativo)
6. [Estrutura do projeto](#estrutura-do-projeto)
7. [Desenvolvimento](#desenvolvimento)
8. [Solução de problemas](#solução-de-problemas)

---

## Pré-requisitos

| Ferramenta | Versão mínima | Download |
|---|---|---|
| Python | 3.12 | https://www.python.org/downloads/ |
| Ollama | Qualquer recente | https://ollama.com/download |
| Obsidian | Qualquer recente | https://obsidian.md/ |
| Git | Qualquer recente | https://git-scm.com/download/win |

> **Dica:** ao instalar o Python no Windows, marque **"Add Python to PATH"**.

---

## Instalação

```bat
git clone https://github.com/keok-netzsch/techcolab-backlog.git
cd techcolab-backlog
git config core.hooksPath .githooks   REM ativa o guard de segurança (ver SECURITY.md)
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Para o subprojeto **call-recorder** (gravação + transcrição de reuniões), instale também:

```bat
pip install -r call-recorder\requirements.txt
```

> Atalho: `install.bat` automatiza a criação do venv e a instalação das dependências.

---

## Configuração

O caminho do vault Obsidian é lido da variável de ambiente **`TECHCOLAB_VAULT`** (com fallback em `config.py`). Defina-a apontando para a sua área de trabalho do vault:

```powershell
[Environment]::SetEnvironmentVariable("TECHCOLAB_VAULT", "C:\Caminho\Para\Seu\Vault\App\Personal toolkit", "User")
```

`config.py` deriva os demais caminhos a partir dela (`VAULT_BASE`, `TEAM_DIR`, `BACKLOG_DIR`, etc.) e expõe `TECHCOLAB_VAULT_ROOT` para o call-recorder. **Nunca aponte o vault para dentro deste repositório** e não hardcode caminhos pessoais.

---

## Modelo Ollama

```bat
ollama pull llama3.2:3b           REM extração/agente
ollama pull qwen2.5-coder:latest  REM English Coach (saída estruturada)
ollama list
```

---

## Iniciando o aplicativo

- **Duplo clique** em `start_silent.vbs` (ou `start_app.bat`), ou:

```bat
.venv\Scripts\activate
streamlit run app.py
```

Disponível em **http://localhost:8501**.

---

## Estrutura do projeto

```
techcolab-backlog/
├── app.py                # Aplicativo principal (Streamlit) — nav custom via ?page=
├── config.py             # Caminhos do vault (TECHCOLAB_VAULT) e settings
├── agent/                # Agente diário (Fase 1 análise → relatório; status)
├── backlog/              # Camada de dados (store/schema/daily_log) — markdown + YAML
├── ingestion/            # Pipeline de ingestão de notas via Ollama
├── call-recorder/        # Subprojeto: gravação + Whisper STT + Ollama (1on1/English Coach)
├── assets/               # logo.svg + brand.css (carregados pelo app)
├── scripts/              # vault-bootstrap*.ps1, techcolab-brand.css
├── tests/                # pytest (python -m pytest tests/ -v)
├── docs/                 # Documentação (FAQ, propostas de arquitetura)
├── requirements.txt      # Dependências do app
├── pyproject.toml        # Config ruff + pytest (Python >=3.12)
├── SECURITY.md           # Regras de isolamento de dados (repo público)
└── .githooks/pre-commit  # Guard contra commit de dados do vault
```

---

## Desenvolvimento

```bat
ruff check .                          REM lint (E/F/I/UP/B)
python -m pytest tests/ -q            REM testes (requer TECHCOLAB_VAULT setado)
```

Antes de criar qualquer página/seção nova, leia **`DESIGN_SYSTEM.md`** (paleta, tipografia, cards `.cc-*`, regras de minimalismo). Toda UI deve ser em **inglês**.

---

## Solução de problemas

| Sintoma | Solução |
|---|---|
| `Connection refused` / erro de modelo | Inicie o Ollama (bandeja do sistema); confirme em `http://localhost:11434` |
| App exibe dados antigos | F5 no navegador; confirme `TECHCOLAB_VAULT` correto |
| `Port 8501 is already in use` | `netstat -ano \| findstr :8501` + `taskkill /PID <pid> /F`, ou `streamlit run app.py --server.port 8502` |
| `python não é reconhecido` | Reinstale o Python com "Add Python to PATH" |
| Erro no `pip install` | Ative o venv primeiro; `python -m pip install --upgrade pip` |

Erros recorrentes de Streamlit/CSS estão catalogados em `CLAUDE_FAQ.md`.
