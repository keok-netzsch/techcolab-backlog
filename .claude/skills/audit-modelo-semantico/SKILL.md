---
name: audit-modelo-semantico
description: Audita um modelo semântico do Power BI (.pbix) contra o checklist de curadoria do time D&A — rode um passe automatizado + revisão assistida por Claude, e devolva um score por categoria com o que precisa mudar. Use quando o usuário anexar ou apontar um arquivo .pbix e pedir para auditar, avaliar, revisar ou dar score no modelo semântico.
---

# Auditoria de Modelo Semântico (Power BI)

Você está avaliando um arquivo `.pbix` contra o **Guia de Curadoria de Modelo Semântico** do time D&A
(`docs/guia-curadoria-modelo-semantico.md`, neste mesmo repo). Leia esse arquivo inteiro antes de
prosseguir — ele é a fonte de verdade dos critérios, exemplos e do porquê de cada regra.

## Passo 1 — Localizar o arquivo

O usuário deve ter anexado o `.pbix` na conversa, ou apontado um caminho. Se não houver um caminho
de arquivo `.pbix` claro, peça para o usuário anexar o arquivo ou informar o caminho — não invente
um caminho nem prossiga sem ele.

## Passo 2 — Rodar o script automatizado

Rode, a partir da raiz deste repo (`techcolab-backlog/`):

```bash
python scripts/audit_semantic_model.py "<caminho do .pbix>" --json
```

Se o comando falhar por falta da lib `pbixray`, instale com `pip install pbixray` e rode de novo.

O script devolve um JSON com 3 categorias (A. Fundamentos, B. Curadoria para negócio,
C. AI-readiness/Copilot), cada uma com uma lista de `checks`. Cada check tem:

- `automated: true` + `score` — verificado objetivamente pela metadata do modelo. Use o score como está.
- `automated: false` + `score: null` — **não dá pra verificar só com metadata**. O script traz em
  `detail` e `note` o contexto necessário (nomes de tabela candidatas, listas de medidas, contagens
  etc.) para você aplicar julgamento.

**Não trate os itens `automated: false` como reprovados por padrão.** Avalie cada um usando o
`detail` fornecido e os critérios do guia (Bloco 1/2/3, conforme a categoria). Alguns exemplos de
como julgar:

- **A1 (grão consistente):** olhe os nomes das tabelas em `fact_table_candidates` — pelo nome e
  pelas colunas, dá pra inferir se a tabela parece ter um grão único (ex.: uma linha por pedido)?
  Se o nome/estrutura sugerir mistura de grãos (ex.: coluna de "mês" E coluna de "dia" ambas como
  chave), sinalize.
- **A3 (bidirecional):** se `bidirectional_relationships` estiver vazio, dê o ponto cheio. Se não,
  julgue pelo nome das tabelas envolvidas se bidirecional faz sentido ali (ex.: entre duas
  dimensões correlacionadas costuma ser aceitável; entre fato e dimensão é mais arriscado).
- **B2 (medidas nomeiam o resultado):** olhe a lista `measure_names` — nomes como "Soma de Valor",
  "Calc1", "Medida (2)" são maus sinais; nomes como "Faturamento", "Ticket Médio" são bons sinais.
- **B4 (hierarquias):** zero hierarquias só é um problema se o modelo tiver atributos óbvios de
  drill-down (ano/mês/dia, categoria/subcategoria) que não foram organizados em hierarquia — olhe
  os nomes de coluna disponíveis para decidir.
- **C2/C3/C4:** normalmente ficam como "não verificado — pendente de checagem manual no Power BI",
  a menos que o `detail` traga evidência clara o suficiente para julgar.

## Passo 3 — Montar o relatório final

Produza um relatório no mesmo formato do checklist do guia:

```markdown
## Auditoria — <nome do arquivo>

**Score:** X/100 (Y automatizados + Z julgados)
**Faixa:** Pronto para publicar / Publicável com ressalvas / Não publicar ainda

### A. Fundamentos (X/25)
- [x ou ' '] <item> — <score>/<max> — <observação, se houver>
...

### B. Curadoria para negócio (X/45)
...

### C. AI-readiness / Copilot (X/30)
...

### O que priorizar corrigir primeiro
1. <item de maior impacto/pontos perdidos>
2. ...

### Itens que só dá pra confirmar manualmente
- <lista dos itens automated:false que você não teve confiança suficiente pra julgar — sinalize
  para o analista verificar diretamente no Power BI Desktop>
```

Seja honesto sobre a origem de cada número: não misture "verificado pelo script" com "julgamento
do Claude" sem deixar claro qual é qual — a credibilidade da ferramenta depende disso.

## Restrições

- Não abra nem modifique o `.pbix` diretamente — a única interação com o arquivo é via o script.
- Não reescreva os critérios do checklist "de cabeça" — sempre releia
  `docs/guia-curadoria-modelo-semantico.md` antes de julgar, os critérios podem mudar entre versões.
- Este é um PoC — se o script travar num arquivo real (formato inesperado, versão antiga do PBIX,
  etc.), reporte o erro exato ao usuário em vez de inventar um score.
