---
name: da-compartilhar
description: Compartilha uma decisao, status, aprendizado, processo ou referencia com o vault central D&A a partir da conversa atual ou de um arquivo. Use sempre que alguem disser "compartilhe com o D&A", "salve no 2nd brain", "publique para o time", "registre esta decisao" ou pedir para tornar conhecimento de projeto acessivel ao time. Nao use para notas pessoais, feedback sobre pessoas, compensacao, RH, credenciais ou conteudo ainda especulativo.
---

# Compartilhar com D&A

O chat e a interface; o vault e o registro. A pessoa nao deve abrir Obsidian,
escolher pasta ou escrever frontmatter para compartilhar algo util ao time.

## Fluxo

1. Extraia da conversa ou do arquivo: titulo, resumo, conteudo, tipo e projeto/area provavel.
2. Classifique em exatamente um tipo: `decision`, `status`, `lesson`, `process` ou `reference`.
3. Antes de escrever, faça uma verificacao de seguranca. Pare e explique que nao pode
   compartilhar se houver avaliacao de pessoa, compensacao, dados de RH, credenciais,
   incidente de seguranca nao anunciado ou conteudo pessoal. Ofereca uma versao anonima,
   se isso preservar a utilidade.
4. Mostre uma previa curta: tipo, destino proposto, resumo e nivel de sensibilidade.
   Pergunte apenas: **"Confirmar envio ao D&A?"** Nao escreva sem um sim explicito.
5. Depois da confirmacao, gere um JSON UTF-8 temporario com os campos abaixo e execute
   `python <pasta-da-skill>/scripts/da_intake.py submit --payload <arquivo-json>`.
6. Informe o caminho criado e que a submissao sera revisada pelo dono do projeto/area.

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
  "source": "Claude Code conversation | 2026-09-10",
  "tags": ["okr", "power-bi"]
}
```

`DA_CENTRAL_VAULT` e `DA_CONTRIBUTOR_NAME` precisam estar configuradas na maquina.
Nunca tente adivinhar o caminho do vault. Se a variavel nao existir, explique como
configurar e pare; nao grave uma copia em Downloads, no repositorio ou no vault pessoal.

## Qualidade do conteudo

- Escreva para alguem que nao estava na conversa: contexto, decisao/fato, impacto e proximo passo.
- Diga quando algo e proposta, hipotese ou informacao a verificar.
- Nao invente responsavel, prazo, numero ou aprovacao. Se a fonte nao afirma, deixe como aberto.
- A submissao e uma proposta auditavel; ela nao e a nota oficial.

## Exemplo de resposta antes do envio

> Vou enviar como **decisao** para **OKR 05 - Governanca de Acesso PBI**. Nao detectei
> conteudo sensivel. Resumo: a partir de outubro, o acesso sera gerido pelo grupo Y;
> o impacto esperado e ... Confirmar envio ao D&A?
