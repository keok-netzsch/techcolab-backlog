---
name: da-compartilhar
description: Compartilha uma decisao, status, aprendizado, processo ou referencia com o vault central D&A a partir da conversa atual ou de um arquivo. Use sempre que alguem disser "compartilhe com o D&A", "salve no 2nd brain", "publique para o time", "registre esta decisao" ou pedir para tornar conhecimento de projeto acessivel ao time. Tambem responde "o que aconteceu com o que eu enviei". Nao use para notas pessoais, feedback sobre pessoas, compensacao, RH, credenciais ou conteudo ainda especulativo.
---

# Compartilhar com D&A

O chat e a interface; o vault e o registro. A pessoa nao deve abrir Obsidian,
escolher pasta ou escrever frontmatter para compartilhar algo util ao time.

Uma coisa por vez. Se a conversa tem tres assuntos que valem guardar, envie o mais
util e diga quais ficaram de fora. Submissao longa nao e revisada em cinco minutos,
e revisao que nao cabe em cinco minutos nao acontece na sexta.

## Fluxo

1. Extraia da conversa ou do arquivo: titulo, resumo, conteudo, tipo e projeto/area provavel.
2. Classifique em exatamente um tipo: `decision`, `status`, `lesson`, `process` ou `reference`.
3. O autor e `DA_CONTRIBUTOR_NAME`. Nao pergunte o nome dele.
4. Escolha o destino a partir das pastas que EXISTEM. Liste `Projects/` e `Areas/` no
   caminho de `DA_CENTRAL_VAULT` antes de propor. Nunca invente nome de projeto; se
   nenhum servir, proponha `Resources` e diga isso na previa.
5. Mostre uma previa curta: tipo, destino, resumo. Pergunte apenas:
   **"Confirmar envio ao D&A?"** Nao escreva sem um sim explicito.
6. Gere um JSON UTF-8 temporario e rode
   `python <pasta-da-skill>/scripts/da_intake.py submit --payload <arquivo-json>`.
7. Informe o caminho criado e que o dono do projeto/area revisa a submissao.

## Campos do payload

```json
{
  "author": "Nome Sobrenome",
  "kind": "decision",
  "title": "Titulo claro",
  "summary": "2-4 frases autoexplicativas",
  "body": "Conteudo pronto para revisao em Markdown",
  "proposed_target": "Projects/OKR 05 - Governanca de Acesso PBI",
  "sensitivity": "none",
  "source": "Claude Code conversation | 2026-09-11",
  "tags": ["okr", "power-bi"]
}
```

`DA_CENTRAL_VAULT`, `DA_CONTRIBUTOR_NAME` e `DA_SHARE_SCRIPT` precisam estar
configuradas. Nunca tente adivinhar o caminho do vault. Se faltar variavel, mande a
pessoa rodar `install-da-share.ps1` e pare; nao grave copia em Downloads, no
repositorio ou no vault pessoal.

## O programa recusa, e a recusa e a resposta certa

O vault central e uma pasta do SharePoint que todo o time le. O programa verifica o
texto antes de gravar e devolve exit 2 com a linha que causou a recusa.

- **Recusa sem saida** quando o texto toca dinheiro de pessoa, saude, identidade ou
  credencial. Nao existe flag para contornar. Diga isso com todas as letras, ofereca
  uma versao anonima que carregue o aprendizado sem o caso, e nao tente outra
  formulacao para passar pelo filtro.
- **Pede confirmacao** quando o vocabulario e ambiguo: `promotion` de pipeline,
  `headcount` como coluna de dashboard, `politica`. Pergunte a pessoa se aquilo e
  sobre sistema ou sobre gente. Se for sobre sistema, reenvie com
  `"confirm_not_personal": true`. A confirmacao fica gravada para o revisor ver.
- **Recusa destino inexistente** na publicacao e sugere os parecidos.

Nunca reescreva o conteudo so para escapar de um padrao. Se o assunto e sensivel, o
lugar dele nao e o vault central.

## Qualidade do conteudo

- Escreva para alguem que nao estava na conversa: contexto, decisao/fato, impacto e proximo passo.
- Diga quando algo e proposta, hipotese ou informacao a verificar.
- Nao invente responsavel, prazo, numero ou aprovacao. Se a fonte nao afirma, deixe como aberto.
- A submissao e uma proposta auditavel; ela nao e a nota oficial.

## "O que aconteceu com o que eu mandei?"

`python <pasta-da-skill>/scripts/da_intake.py queue --author "<DA_CONTRIBUTOR_NAME>" --all`

Mostra cada submissao da pessoa e o estado: `pending`, `publish`, `return` ou
`reject`. Para devolvida ou rejeitada, leia o arquivo de decisao em
`Intake/_decisions/` e diga o motivo no chat, com as palavras do revisor.
