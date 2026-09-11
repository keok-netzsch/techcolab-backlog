---
name: da-revisar
description: Revisa e publica submissões pendentes do vault central D&A quando um dono de projeto/area pedir para aprovar, devolver ou rejeitar conteudo compartilhado pelo time. Use para "revisar entradas do D&A", "aprovar esta submissao", "publicar para o projeto" ou "ver pendencias do 2nd brain". Nao publique automaticamente e nunca edite ou remova uma nota existente.
---

# Revisar submissões D&A

O revisor trabalha pelo Claude Code; nao precisa abrir o Obsidian. A submissao e
imutavel. Publicar cria uma nota oficial nova e um recibo; rejeitar nao apaga nada.

## Fluxo

1. Liste `Intake/<mes>/` no caminho indicado por `DA_CENTRAL_VAULT` e leia somente as
   submissões ainda sem recibo correspondente em `Intake/Receipts/`.
2. Para cada uma, mostre: autor, tipo, destino proposto, resumo, risco de sensibilidade e
   uma recomendacao objetiva: publicar, devolver para ajuste ou rejeitar.
3. Espere uma instrucao explicita do revisor. Silencio nunca e aprovacao.
4. Ao publicar, prepare a nota final com frontmatter completo (`date`, `type`, `tags`,
   `ai-first: true`, `source`) e uma preambulo `For future Claude`. Cite a submissao.
5. Monte o payload de publicacao e rode `python <pasta-da-skill>/scripts/da_intake.py publish --payload <arquivo-json>`.
   O programa so cria arquivo novo no destino e um recibo; ele nunca move, edita ou remove.
6. Informe autor, caminho publicado e recibo criado. Ao devolver/rejeitar, explique o motivo
   no chat e registre uma pendencia para o autor pela ferramenta de comunicacao combinada.

## Limites

- Publique apenas no projeto/area que voce possui ou para o qual recebeu delegacao explicita.
- Conteudo sobre pessoas, RH, compensacao, credenciais ou incidentes nao anunciados nao e publicavel.
- Se a submissao conflita com uma nota existente, nao sobrescreva e nao improvise versao; devolva
  ao autor ou escale para Kelvin.
