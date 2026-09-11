# D&A Share — contribuição por Claude Code

## Por que existe

O vault central nao deve exigir que cada pessoa aprenda Obsidian, pastas, nomes de arquivo e
frontmatter antes de conseguir compartilhar uma decisao ou aprendizado. Claude Code e a
interface que o time ja usa; o vault continua sendo o registro institucional.

## Experiência do colaborador

No terminal, a pessoa abre Claude Code e escreve algo como:

> Compartilhe esta decisao com o D&A: a partir de outubro, o acesso PBI da BU X sera tratado pelo grupo Y.

`/da-compartilhar` cria uma previa, verifica sensibilidade e pede uma confirmacao explicita.
Com o "sim", cria uma submissao imutavel em `Intake/YYYY-MM/`. A pessoa nao abre Obsidian e
nao escolhe uma pasta de destino.

## Experiência do dono

O dono abre Claude Code e pede: `revise as submissões pendentes do D&A`.
`/da-revisar` apresenta cada item e espera uma instrucao explicita. Publicar cria uma nota
oficial nova no projeto/area e um recibo em `Intake/Receipts/`; nada e movido, editado ou apagado.

## Governança

- O autor confirma o envio; o modelo nao compartilha sozinho.
- O dono do projeto/area aprova a publicacao no seu escopo. Kelvin decide excecoes,
  conteudo sensivel, areas sem dono e mudancas de estrutura.
- Informacao pessoal, RH, compensacao, credenciais e incidentes nao anunciados nao entra.
- A skill nao le, guarda ou transmite API keys. A chave continua configurada apenas no Claude Code da pessoa.
- `DA_CENTRAL_VAULT` aponta para a copia sincronizada do SharePoint. Sem essa variavel, o
  programa falha; nao ha caminho padrao perigoso.

## Instalação piloto

Cada participante recebe as pastas `.claude/skills/da-compartilhar/` e
`.claude/skills/da-revisar/`, mais `scripts/da_intake.py`, em sua configuracao local de Claude.
Na maquina, configure uma unica vez:

```powershell
[Environment]::SetEnvironmentVariable('DA_CENTRAL_VAULT', 'C:\caminho\sincronizado\10_2ndBrain', 'User')
[Environment]::SetEnvironmentVariable('DA_CONTRIBUTOR_NAME', 'Nome Sobrenome', 'User')
```

Reabra o terminal depois de configurar as variaveis. A API key existente do Claude Code e suficiente.

## Como criar hábito

O sistema deve ser inserido em momentos que ja acontecem, nao lembrado como uma tarefa extra:

1. Ao fechar uma reuniao: quem tomou uma decisao manda uma frase ao Claude.
2. Na sexta-feira: cada dono revisa a fila do proprio projeto em no maximo cinco minutos.
3. Quem contribuiu recebe a confirmacao com o caminho publicado. A recompensa precisa ser visivel.
4. O digest semanal mostra contribuicoes e lacunas por projeto, sem constrangimento publico.

Meta do piloto de 30 dias: cada dono publica ou revisa pelo menos uma entrada por semana. Meça
tempo entre submissao e resposta, percentagem publicada/devolvida e quantos projetos tiveram
atualizacao. Se o fluxo exigir explicacao recorrente, simplifique a skill; nao cobre disciplina extra.
