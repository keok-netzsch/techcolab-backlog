---
type: guia
owner: Kelvin Okuda
created: 2026-07-19
status: draft
audience: analistas-dados-time-da
tags: [power-bi, modelo-semantico, curadoria, boas-praticas, ai-readiness, copilot]
source_of_truth: "Editado no vault pessoal do Kelvin (OneDrive, local-only); esta é a cópia sincronizada pro time via techcolab-backlog. Atualizações: editar a versão do vault, depois copiar aqui e dar push."
---

> Guia de referência para os analistas de dados do time D&A construírem modelos semânticos curados — não só dashboards. Consolida boas práticas oficiais (Microsoft Learn, SQLBI, Tabular Editor) em formato prático de aplicar.
> Usado pela skill `audit-modelo-semantico` (`.claude/skills/audit-modelo-semantico/`) e pelo script `scripts/audit_semantic_model.py` deste repo.

# Guia de Curadoria de Modelo Semântico — Power BI

## Por que isso importa

Construir um dashboard é fácil. Construir um **modelo semântico que o usuário de negócio entende sozinho** — sem perguntar "o que é essa coluna?" ou tirar a métrica errada porque o relacionamento estava mal desenhado — é outra habilidade. É recorrente vermos modelos que funcionam tecnicamente mas confundem quem consome. Este guia existe para fechar esse gap.

Assume que você já conhece os fundamentos de modelagem dimensional (fact/dimension, relacionamentos, DAX básico). O foco é no que **costuma sair errado na prática** — e em como preparar o modelo tanto para o usuário humano quanto para o Copilot.

## Como usar este guia

3 blocos + 1 checklist de auditoria no final:
1. **Fundamentos que sustentam a curadoria** — a base técnica que, se estiver errada, nenhuma nomenclatura bonita resolve.
2. **Curadoria para usuários de negócio** — o que o usuário realmente vê e usa.
3. **AI-readiness (Copilot)** — a mesma disciplina do bloco 2, com alguns requisitos extras.

Rode o **checklist de auditoria** antes de publicar/certificar qualquer modelo novo ou revisão relevante de um existente. Um primeiro passe automatizado está disponível via a skill `audit-modelo-semantico` — ela cobre os itens objetivamente verificáveis e sinaliza os que exigem julgamento humano.

---

## Bloco 1 — Fundamentos que sustentam a curadoria

### 1.1 Star schema é a base, sempre
- Toda tabela do modelo é **dimensão** (filtra/agrupa) ou **fato** (soma/agrega) — nunca as duas coisas misturadas na mesma tabela.
- Regra de ouro: **oculte todas as colunas técnicas da tabela fato**; o usuário só deve ver medidas nela. Os atributos visíveis ficam nas dimensões.
- A cardinalidade do relacionamento é o que define o papel da tabela: lado "um" = dimensão, lado "muitos" = fato.

### 1.2 Relacionamentos e propagação de filtro
- Filtros fluem de dimensão → fato. Evite relacionamentos bidirecionais a menos que você entenda exatamente o impacto (eles podem propagar filtro em direções não óbvias e confundir o próprio usuário de negócio).
- **Dimensões role-playing** (ex.: uma tabela Data que filtra Data do Pedido, Data de Envio e Data de Entrega): não acumule relacionamentos inativos + `USERELATIONSHIP` em cada medida — isso é tedioso de manter e polui o painel de campos com medidas duplicadas. Prefira criar uma tabela de dimensão por papel (`Data Pedido`, `Data Envio`, `Data Entrega`), cada uma com relacionamento único e ativo, e colunas com nomes autoexplicativos (`Ship Year`, não `Year` repetido).
- **Muitos-para-muitos entre dimensões**: use uma tabela-ponte (factless fact table) — é a prática recomendada, não o relacionamento M:N direto.

### 1.3 Granularidade e chaves
- Toda tabela fato precisa carregar dados num **grão único e consistente**. Misturar grãos na mesma fato (ex.: linhas por pedido e linhas por mês no mesmo campo) quebra qualquer agregação de negócio.
- Quando a fonte não tem uma chave única natural, adicione uma surrogate key (coluna de índice) — é o que sustenta o relacionamento 1:N.

### 1.4 Snowflake vs. tabela única desnormalizada
- Prefira consolidar uma dimensão em **uma única tabela desnormalizada** em vez de espelhar o snowflake da fonte. Ganhos: menos tabelas no painel (menos confusão pro usuário), cadeia de propagação de filtro mais curta, e a possibilidade de criar uma hierarquia que atravesse toda a dimensão (ex.: Categoria → Subcategoria → Produto) — isso só é possível dentro de uma única tabela.
- Só quebre essa regra se o volume de dados tornar a tabela única proibitivamente grande.

---

## Bloco 2 — Curadoria para usuários de negócio

### 2.1 Nomenclatura
- Nome de negócio, nunca técnico: `Cliente`, não `DIM_Cliente`; `Faturamento`, não `FACT_Faturamento`.
- Sem abreviações nem siglas não óbvias (`Margem Padrão`, não `Mrg. Pad.`) — se uma sigla for necessária, defina-a na descrição do campo.
- Nomes com espaço e capitalização legível (`Status do Pedido`), nunca `camelCase` ou `snake_case`.
- Sem emojis, símbolos ou formatação excessiva no nome do campo.
- **Medidas nomeiam o resultado, não o cálculo**: `Faturamento`, não `Soma de Valor`. Padronize sufixos de período e comparação de forma consistente em todo o modelo (`Faturamento MTD`, `Faturamento (AA)` para ano anterior) — a convenção exata importa menos do que a consistência.

### 2.2 Organização visual — display folders
- Agrupe medidas e colunas em pastas de exibição por **conceito de negócio** (`Indicadores de Vendas`, `Detalhes do Cliente`), não por agrupamento técnico.
- Centralize as medidas numa tabela de medidas dedicada (desconectada, só para organização) quando o modelo crescer.
- Escolha uma convenção de nomes de pasta e mantenha — o que quebra a experiência é a inconsistência, não a convenção escolhida.

### 2.3 Hierarquias
- Sempre que fizer sentido para o negócio, crie hierarquias (`Ano → Trimestre → Mês → Dia`, `Categoria → Subcategoria → Produto`) em vez de deixar atributos soltos na dimensão.
- Depois de criar a hierarquia, **oculte os atributos individuais** que a compõem — isso só é possível se a dimensão estiver numa única tabela (ver 1.4).

### 2.4 Ocultar o que não serve ao usuário de negócio
- Toda coluna técnica da tabela fato (chaves, IDs) fica oculta — só medidas visíveis (reforça 1.1).
- Oculte colunas que existem só para ordenação (`Mês (Ordem de Classificação)` etc.) — elas servem ao modelo, não ao usuário.
- **Nunca deixe nomes de campo duplicados entre tabelas** (`Nome` na tabela Cliente e `Nome` na tabela Loja) — confunde o usuário de negócio e, adiante, confunde o Copilot também.

### 2.5 Medidas explícitas vs. implícitas
- Quando uma coluna só faz sentido ser agregada de um jeito específico (ex.: `Preço Unitário` nunca deveria ser somado, só ter média/mín/máx), oculte a coluna e exponha só as medidas explícitas corretas. Isso evita que o usuário some algo que estatisticamente não faz sentido.

### 2.6 Descrições
- Preencha a descrição de tabelas, colunas e medidas — o padrão de referência é: **o usuário deveria entender o elemento só pela descrição, sem perguntar a ninguém**.
- Priorize medidas complexas e colunas-chave — são as que mais geram dúvida.

### 2.7 Format string e data category
- Toda coluna/medida numérica tem um **format string** explícito (moeda, %, milhar) — sem isso o usuário de negócio vê números crus e interpreta errado (ex.: 0.15 em vez de 15%).
- Use **data category** para campos que representam algo específico (ex.: marcar uma coluna de país/cidade como Geografia, uma coluna de link como URL) — isso habilita visuais nativos (mapas) e ajuda ferramentas a interpretar o campo corretamente, incluindo o Copilot (ver Bloco 3).

---

## Bloco 3 — AI-readiness (Copilot)

Preparar o modelo para o Copilot **não é um trabalho extra** — é essencialmente o Bloco 2 bem feito, mais alguns requisitos específicos. A lista oficial de "grounding data" que o Copilot usa é: DAX de medidas, descrições, tipo de dado, **format string** e **data category** (2.7), e sinônimos.

### 3.1 Descrições como grounding do Copilot
- O Copilot usa a descrição de medidas e colunas-chave como contexto — em pelo menos uma das experiências de Copilot (DAX query view), a descrição é **truncada nos primeiros 200 caracteres**. Escreva a informação mais importante logo no início, em frase natural e específica — vale como boa prática para todas as experiências de Copilot, não só essa.

### 3.2 Sinônimos
- Configure sinônimos para os termos alternativos que o negócio usa pra mesma coisa (`Receita`, `Faturamento`, `Vendas` apontando pra mesma medida).
- Use sinônimo em vez de renomear um campo quando o nome atual já sustenta relatórios existentes — sinônimo não quebra nada rio abaixo.

### 3.3 Simplificar o schema exposto à IA
- Remova objetos não usados (tabelas, colunas, medidas órfãs) — cada objeto extra é ambiguidade a mais para o modelo de IA resolver.
- Use o recurso **Prep data for AI** (Power BI Desktop/serviço) para restringir explicitamente quais tabelas/campos a IA pode usar — reduzir o escopo melhora a precisão e a latência da resposta.

### 3.4 Testar com o Copilot antes de publicar
- Faça perguntas de negócio reais (as que o usuário faria) e valide a resposta antes de liberar.
- Só marque o modelo como **"Approved for Copilot"** depois desse teste — é o sinal formal de que o modelo foi preparado, não um checkbox de conveniência.

> ⚠️ **Nota de estabilidade (jul/2026):** "Prep data for AI" e "Approved for Copilot" são recursos marcados **preview** pela própria Microsoft no momento em que este guia foi escrito. Nome, comportamento e disponibilidade podem mudar — trate os passos 3.3/3.4 como o *objetivo* (simplificar o schema exposto à IA, sinalizar prontidão), não como um caminho de UI fixo. Revalidar a cada trimestre.

---

## Checklist de Auditoria — Fase 1 (autoavaliação do analista)

Rode antes de publicar/certificar. Pontuação de 0 a 100 — marque cada item cumprido.

**A. Fundamentos — 25 pts**
- [ ] Toda tabela fato tem grão único e consistente *(10)*
- [ ] Relacionamentos são 1:N, filtro flui dimensão → fato; nenhum M:N direto sem tabela-ponte; dimensões role-playing resolvidas com tabelas separadas (não pilha de relações inativas + `USERELATIONSHIP`) *(10)*
- [ ] Bidirecional usado só onde necessário e o impacto foi entendido/documentado *(5)*

**B. Curadoria para negócio — 45 pts**
- [ ] Nomes de tabelas/colunas/medidas em linguagem de negócio, sem prefixo técnico ou sigla não definida *(10)*
- [ ] Medidas nomeiam o resultado, com período/unidade padronizados no modelo inteiro *(5)*
- [ ] Todas as colunas técnicas da tabela fato ocultas — só medidas visíveis *(5)*
- [ ] Hierarquias criadas onde faz sentido, com atributos individuais ocultos *(5)*
- [ ] Medidas organizadas em display folders por conceito de negócio *(5)*
- [ ] Nenhum nome de campo duplicado entre tabelas *(5)*
- [ ] Descrições preenchidas em tabelas, colunas e medidas principais *(5)*
- [ ] Format string e data category preenchidos nos campos relevantes (moeda, %, geografia, URL) *(5)*

**C. AI-readiness / Copilot — 30 pts**
- [ ] Medidas e colunas-chave têm descrição clara e específica nos primeiros 200 caracteres *(10)*
- [ ] Sinônimos configurados para os termos alternativos usados pelo negócio *(5)*
- [ ] Schema exposto à IA simplificado (Prep data for AI rodado, campos irrelevantes ocultos) *(10)*
- [ ] Modelo testado com perguntas reais no Copilot antes de marcar "Approved for Copilot" *(5)*

**Leitura do score:**
| Faixa | Status |
|---|---|
| 90–100 | Pronto para publicar |
| 70–89 | Publicável com ressalvas — corrigir os itens faltantes na próxima iteração |
| < 70 | Não publicar ainda — revisar antes de levar para a revisão final do Kelvin |

A revisão final (segunda camada de auditoria) é feita pelo Kelvin, sem formato definido ainda — a definir quando este checklist estiver validado em uso real.

---

## Fase 2 — auditoria automatizada (PoC entregue)

A skill `audit-modelo-semantico` (`.claude/skills/audit-modelo-semantico/`) + o script `scripts/audit_semantic_model.py` fazem um primeiro passe automatizado deste checklist direto do arquivo `.pbix`, via a lib [`pbixray`](https://github.com/Hugoberry/pbixray) (lê o modelo sem precisar de Power BI Desktop nem Tabular Editor instalado).

**Importante:** nem todo item do checklist é verificável só pela metadata do modelo — coisas como "o grão é semanticamente consistente" ou "foi testado no Copilot" exigem julgamento humano. A skill sinaliza claramente o que foi verificado automaticamente vs. o que precisa de revisão manual/LLM — não finge um score 0–100 automático completo.

Caminho considerado (não construído ainda) pra uma versão mais madura: **Best Practice Analyzer (BPA) do Tabular Editor** — motor de regras open-source já estabelecido para esse propósito, com regras oficiais no GitHub (`TabularEditor/BestPracticeRules`).

---

## Fontes

- [Understand star schema and the importance for Power BI — Microsoft Learn](https://learn.microsoft.com/en-us/power-bi/guidance/star-schema)
- [Copilot in Power BI Tutorial: Prepare Semantic Model for AI — Microsoft Learn](https://learn.microsoft.com/en-us/power-bi/create-reports/tutorial-copilot-power-bi-prepare-model)
- [Use Copilot with Semantic Models in Power BI — Microsoft Learn](https://learn.microsoft.com/en-us/power-bi/create-reports/copilot-semantic-models) — fonte do limite de 200 caracteres em descrições (grounding data da DAX query view) e da lista de grounding data (descrições, tipo de dado, format string, data category, sinônimos)
- [Naming conventions for Power BI semantic models — Tabular Editor](https://tabulareditor.com/blog/naming-conventions-for-power-bi-semantic-models)
- [The importance of star schemas in Power BI — SQLBI](https://www.sqlbi.com/articles/the-importance-of-star-schemas-in-power-bi/)
- [Organize Your Power BI Model with Measure Tables and Display Folders — Not a Pickle](https://notapickle.blog/2025/09/17/organize-your-power-bi-model-with-measure-tables-and-display-folders/)
- [Using the Best Practice Analyzer — Tabular Editor Documentation](https://docs.tabulareditor.com/en/features/using-bpa.html)
- [TabularEditor/BestPracticeRules — GitHub](https://github.com/TabularEditor/BestPracticeRules)
- [PBIXRay — Python parser for .pbix files](https://github.com/Hugoberry/pbixray)
