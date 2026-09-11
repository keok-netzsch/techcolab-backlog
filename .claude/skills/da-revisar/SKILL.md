---
name: da-revisar
description: Revisa e publica submissões pendentes do vault central D&A quando um dono de projeto/area pedir para aprovar, devolver ou rejeitar conteudo compartilhado pelo time. Use para "revisar entradas do D&A", "revisar minhas pendencias do D&A", "aprovar esta submissao", "publicar para o projeto" ou "ver pendencias do 2nd brain". Nao publique automaticamente e nunca edite ou remova uma nota existente.
---

# Revisar submissões D&A

O revisor trabalha pelo Claude Code; nao precisa abrir o Obsidian. A submissao e
imutavel. Publicar cria uma nota oficial nova e um recibo; devolver e rejeitar
registram a decisao e nao apagam nada.

A meta e cinco minutos na sexta. Conduza a revisao inteira numa passada: mostre a
fila, recomende, espere a instrucao, execute. Nao faca uma pergunta por submissao
antes de ter mostrado todas.

## Fluxo

1. `python <pasta-da-skill>/scripts/da_intake.py queue` lista o que esta aberto.
   A fila ja exclui o que foi decidido; nao filtre por recibo na mao.
2. Para cada uma, leia o arquivo e mostre: autor, tipo, destino, resumo e uma
   recomendacao objetiva de publicar, devolver ou rejeitar. Sinalize sempre:
   - `target_exists: false` — o destino proposto nao existe. Decida se e erro de
     digitacao ou pasta nova de verdade antes de publicar.
   - `confirmed_not_personal` diferente de `n/a` — o autor passou por um padrao
     ambiguo. Confira que o texto e mesmo sobre sistema e nao sobre gente.
3. Espere uma instrucao explicita. Silencio nunca e aprovacao.
4. **Publicar:** prepare a nota final com frontmatter completo (`date`, `type`,
   `tags`, `ai-first: true`, `source` citando a submissao) e um preambulo
   `For future Claude`. Rode
   `python <pasta-da-skill>/scripts/da_intake.py publish --payload <json>` com
   `submission`, `approver`, `target`, `filename` e `published_content`.
   Se o destino nao existe, o programa recusa e sugere os parecidos. So passe
   `"allow_new_folder": true` se a pasta for nova de verdade.
5. **Devolver ou rejeitar:** rode
   `python <pasta-da-skill>/scripts/da_intake.py resolve --payload <json>` com
   `submission`, `decision` (`return` ou `reject`), `reason` e `approver`.
   Isso e obrigatorio. Sem o registro de decisao a submissao volta a aparecer na
   fila em toda revisao, para sempre.
6. **Avise o autor.** O programa nao manda mensagem. Escreva no chat um texto curto
   pronto para colar no Teams, na voz do revisor, e diga para quem e:

   > Publiquei o que voce mandou sobre <assunto> em <destino>. Obrigado.

   Para devolucao, o texto diz o que falta e que basta reenviar pelo Claude. O
   retorno ao autor e o que faz a proxima contribuicao acontecer; nao pule.

## Limites

- Publique apenas no projeto/area que voce possui ou para o qual recebeu delegacao explicita.
- Conteudo sobre pessoas, RH, compensacao, credenciais ou incidentes nao anunciados nao e
  publicavel. O programa recusa os casos claros, mas ele le padrao, nao entende contexto:
  a leitura e sua.
- Se a submissao conflita com uma nota existente, nao sobrescreva e nao improvise versao;
  devolva ao autor ou escale para Kelvin. O vault central e add-only.
