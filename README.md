# Personal Toolkit · Techco.lab

Toolkit local de backlog e memória de trabalho sobre um vault **Obsidian**, operado por **CLI e por conversa**, com modelo de linguagem local via **Ollama**. Roda 100% offline — **nenhuma chave de API externa é necessária**.

> **O app Streamlit foi aposentado em 2026-08-31.** Ele mostrava dado de pessoas desatualizado (PDI vencido a 0%, agenda de 1:1 escrita por um modelo 7B) ao lado de um ciclo de performance já apurado — tela confiante sobre número velho é pior que tela nenhuma. O que ficou é o produto de verdade: o BacklogStore, o CLI e o agente. Restaurar: `git checkout app-streamlit-final -- app.py views components backlog/cache.py`.

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

## Como usar

```bash
# cadastrar uma ideia (caminho normal)
python agent/create_idea.py --title "..." --description "..." --todo "Primeiro passo"

# mudar status
python agent/update_status.py idea-081 "em validação"

# ingerir notas soltas do vault
python main.py ingest
```

Detalhes e o loop de decisão (weekly brief + Closer): `TUTORIAL.md`.

---

## Estrutura do projeto

```
techcolab-backlog/
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
| Ideia não aparece / caminho errado | confirme `TECHCOLAB_VAULT`; o status canônico é o idea file, mudado só por `update_status.py` |
| `python não é reconhecido` | Reinstale o Python com "Add Python to PATH" |
| Erro no `pip install` | `python -m pip install --upgrade pip` |

`CLAUDE_FAQ.md` guarda o histórico de erros do app Streamlit — mantido só como registro;
o app não existe mais desde 2026-08-31.
