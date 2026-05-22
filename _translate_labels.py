"""
_translate_labels.py — Translate all Portuguese UI labels to English in app.py.
Run once: python _translate_labels.py
"""
with open('app.py', encoding='utf-8-sig') as f:
    c = f.read()

replacements = [
    # ── Dashboard: CC Activity ─────────────────────────────────────────────────
    ('st.subheader("Atividade no Claude Code")',
     'st.subheader("Claude Code Activity")'),
    ('st.caption("Atividade real baseada nos arquivos de sessão `~/.claude/projects/`")',
     'st.caption("Real activity from session files `~/.claude/projects/`")'),
    # Period filter
    ('if st.button("Todos", type="primary" if _w == 0 else "secondary",',
     'if st.button("All", type="primary" if _w == 0 else "secondary",'),
    # Fun tagline
    ('("O Hobbit")',                        '("The Hobbit")'),
    ('("Harry Potter e a Pedra Filosofal")',  '("Harry Potter and the Philosopher\'s Stone")'),
    ('("1984, de Orwell")',                  '("1984 by Orwell")'),
    ('("Guerra e Paz")',                     '("War and Peace")'),
    ("return f'Você usou ~{_ratio}&times; mais tokens do que <em>{_name}</em>.'",
     "return f'You used ~{_ratio}&times; more tokens than <em>{_name}</em>.'"),
    ("return 'Você acumulou tokens suficientes para escrever um romance.'",
     "return 'You have accumulated enough tokens to write a novel.'"),
    ("return f'Você acumulou {_fmt_tok(total_tokens)} tokens até agora.'",
     "return f'You have accumulated {_fmt_tok(total_tokens)} tokens so far.'"),
    # Stats grid card labels
    ('<div class="cc-sl">Sessões</div>',        '<div class="cc-sl">Sessions</div>'),
    ('<div class="cc-sl">Dias ativos</div>',    '<div class="cc-sl">Active days</div>'),
    ('<div class="cc-sl">Horário de pico</div>','<div class="cc-sl">Peak hour</div>'),
    ('<div class="cc-sl">Eficiência cache</div>','<div class="cc-sl">Cache efficiency</div>'),
    ('<div class="cc-sl">Sequência atual</div>','<div class="cc-sl">Current streak</div>'),
    ('<div class="cc-sl">Maior sequência</div>','<div class="cc-sl">Longest streak</div>'),
    ('<div class="cc-sl">Projetos</div>',       '<div class="cc-sl">Projects</div>'),
    ('<div class="cc-sl">Mensagens</div>',      '<div class="cc-sl">Messages</div>'),
    # Captions
    ('st.caption(f"Projetos: {_proj_str}")',    'st.caption(f"Projects: {_proj_str}")'),
    ('st.caption("ℹ️ Claude Code CLI apenas. Claude.ai web/desktop não deixa log local.")',
     'st.caption("ℹ️ Claude Code CLI only. Claude.ai web/desktop does not leave local logs.")'),
    ('st.info("Nenhum dado encontrado em `~/.claude/`.")',
     'st.info("No data found in `~/.claude/`.")'),
    # Diagnostic labels
    ('"**Frequência muito baixa** — {_avg_day:.1f} prompts/dia em média. "'
     '"Claude Code ainda não está integrado ao fluxo diário."',
     '"**Very low frequency** — {_avg_day:.1f} prompts/day on average. "'
     '"Claude Code is not yet integrated into the daily workflow."'),
    ('"Traga tarefas menores: revisão de e-mails, rascunhos, análise rápida de dados, geração de scripts. "'
     '"O hábito se forma no uso cotidiano, não nos grandes projetos."',
     '"Bring smaller tasks: email reviews, drafts, quick data analysis, script generation. "'
     '"The habit forms through daily use, not just large projects."'),
    ('"**Frequência abaixo do potencial** — {_avg_day:.1f} prompts/dia. "'
     '"Há espaço para expandir o uso para mais tipos de tarefa."',
     '"**Frequency below potential** — {_avg_day:.1f} prompts/day. "'
     '"There is room to expand usage to more types of tasks."'),
    ('"Identifique tarefas recorrentes que você ainda faz manualmente e experimente delegar ao Claude."',
     '"Identify recurring tasks you still do manually and try delegating them to Claude."'),
    ('"**Contexto subutilizado** — média de {_avg_tk_per_prompt/1000:.1f}K tokens/prompt. "'
     '"Sessões muito curtas aproveitam pouco o contexto de 200K disponível."',
     '"**Underused context** — average {_avg_tk_per_prompt/1000:.1f}K tokens/prompt. "'
     '"Very short sessions make poor use of the 200K context available."'),
    ('"Inclua o arquivo completo, não só o trecho. Descreva o projeto, dê exemplos. "'
     '"Claude responde proporcionalmente ao contexto que recebe."',
     '"Include the full file, not just the snippet. Describe the project, give examples. "'
     '"Claude responds proportionally to the context it receives."'),
    ('"**Cache pouco aproveitado** — {_cache_pct_diag}% de eficiência. "'
     '"Poucas sessões reaproveitam contexto de sessões anteriores."',
     '"**Underused cache** — {_cache_pct_diag}% efficiency. "'
     '"Few sessions reuse context from previous sessions."'),
    ('"Abra sessões mais longas em vez de várias curtas sobre o mesmo tema. "'
     '"Use /clear só ao mudar de assunto, não entre subtarefas relacionadas."',
     '"Open longer sessions instead of many short ones on the same topic. "'
     '"Use /clear only when switching subjects, not between related subtasks."'),
    ('"Padrão de sessões profundas"',           '"Deep session pattern"'),
    ('"Usuário faz {_avg_day:.1f} prompts/dia com média de {_avg_tk_per_prompt/1000:.0f}K tokens cada. "'
     '"Identifique onde sessões mais longas trariam ainda mais valor vs. onde a profundidade atual é suficiente."',
     '"User makes {_avg_day:.1f} prompts/day with an average of {_avg_tk_per_prompt/1000:.0f}K tokens each. "'
     '"Identify where longer sessions would add even more value vs. where current depth is sufficient."'),
    ('"Alta reutilização de contexto"',         '"High context reuse"'),
    ('"Cache efficiency de {_cache_pct_diag}%. "'
     '"Sugira como estruturar projetos recorrentes para maximizar ainda mais esse padrão."',
     '"Cache efficiency at {_cache_pct_diag}%. "'
     '"Suggest how to structure recurring projects to further maximize this pattern."'),
    ('"Multi-projeto"',                         '"Multi-project"'),
    ('"Uso distribuído em {len(_cc_projects)} projetos ({_top_proj}). "'
     '"Identifique se faz sentido centralizar contexto entre projetos ou manter separado."',
     '"Usage distributed across {len(_cc_projects)} projects ({_top_proj}). "'
     '"Identify whether centralizing context across projects makes sense or if separate is better."'),
    ('st.markdown(f"**{len(_issues)} problema(s) identificado(s)**")',
     "st.markdown(f\"**{len(_issues)} {'issue' if len(_issues) == 1 else 'issues'} identified**\")"),
    ('st.success("Nenhum problema identificado no padrão de uso atual.")',
     'st.success("No issues found in current usage pattern.")'),
    ('st.markdown(f"**{len(_opps)} oportunidade(s) para análise**")',
     "st.markdown(f\"**{len(_opps)} {'opportunity' if len(_opps) == 1 else 'opportunities'} for analysis**\")"),
    # Diagnostic card labels in HTML
    ('"text-transform:uppercase;letter-spacing:.04em">Problema</span>',
     '"text-transform:uppercase;letter-spacing:.04em">Issue</span>'),
    ('"text-transform:uppercase;letter-spacing:.04em">Como corrigir</span>',
     '"text-transform:uppercase;letter-spacing:.04em">How to fix</span>'),
    # Ollama analysis
    ('with st.expander("Ver análise detalhada (Ollama)", expanded=False):',
     'with st.expander("Detailed analysis (Ollama)", expanded=False):'),
    ('if st.button("Gerar análise", key="cc_ollama_btn"):',
     'if st.button("Run analysis", key="cc_ollama_btn"):'),
    ('"Você é um consultor de produtividade com IA. "',
     '"You are an AI productivity consultant. "'),
    ('"Analise o padrão de uso do Claude Code abaixo e forneça insights acionáveis.\\n\\n"',
     '"Analyze the Claude Code usage pattern below and provide actionable insights.\\n\\n"'),
    ('f"Métricas reais (últimos 14 dias):\\n{_metrics_summary}\\n\\n"',
     'f"Real metrics (last 14 days):\\n{_metrics_summary}\\n\\n"'),
    ('f"Oportunidades identificadas:\\n{_opp_ctx}\\n\\n"',
     'f"Identified opportunities:\\n{_opp_ctx}\\n\\n"'),
    ('"Para cada oportunidade: explique quando usar Claude nesse contexto e quando NÃO usar. "'
     '"Seja específico e prático. Máximo 200 palavras no total. Responda em português."',
     '"For each opportunity: explain when to use Claude in that context and when NOT to. "'
     '"Be specific and practical. Maximum 200 words total. Respond in English."'),
    ('with st.spinner("Ollama analisando..."):',
     'with st.spinner("Ollama analyzing..."):'),
    ('"Projetos: {\'.\'.join(list(_cc_projects.keys())[:3])}"',
     '"Projects: {\'.\'.join(list(_cc_projects.keys())[:3])}"'),
    ('f"Ollama não disponível (`{OLLAMA_BASE_URL}`). "',
     'f"Ollama not available (`{OLLAMA_BASE_URL}`). "'),
    ('"Inicie o serviço com `ollama serve` para usar esta análise."',
     '"Start the service with `ollama serve` to use this analysis."'),

    # ── Backlog cards HTML ─────────────────────────────────────────────────────
    ('<div class="cc-sl">Ativas</div>',        '<div class="cc-sl">Active</div>'),
    ('<div class="cc-sl">Concluídas</div>',    '<div class="cc-sl">Done</div>'),
    ('<div class="cc-sl">To-dos pendentes</div>','<div class="cc-sl">Open to-dos</div>'),
    ('<div class="cc-sl">To-dos feitos</div>', '<div class="cc-sl">Completed to-dos</div>'),
    ('<div class="cc-sl">Bugs abertos</div>',  '<div class="cc-sl">Open bugs</div>'),
    # Expander
    ('with st.expander("Análise detalhada · Relatório", expanded=False):',
     'with st.expander("Detailed analysis · Report", expanded=False):'),

    # ── Backlog page ───────────────────────────────────────────────────────────
    ('if st.button("✨ Sugerir to-dos", key=f"regen_{idea.id}", help="Sugere próximos passos com base no título e descrição"):',
     'if st.button("✨ Suggest to-dos", key=f"regen_{idea.id}", help="Suggests next steps based on title and description"):'),
    ('with st.spinner("Gerando..."):', 'with st.spinner("Generating..."):'),
    ('st.error(f"Ollama indisponível: {e}")',  'st.error(f"Ollama unavailable: {e}")'),
    ('tips_label = "🤖 Regenerar dicas" if current_tips else "🤖 Dicas com Claude"',
     'tips_label = "🤖 Regenerate tips" if current_tips else "🤖 Claude tips"'),
    ('help="Gera dicas de como usar o Claude para desenvolver este item"',
     'help="Generates tips on how to use Claude to develop this item"'),
    ('with st.spinner("Gerando dicas..."):', 'with st.spinner("Generating tips..."):'),
    ('st.warning("Nenhuma dica gerada. Adicione uma descrição ao item.")',
     'st.warning("No tips generated. Add a description to the item.")'),
    ('"**To-dos sugeridos** — marque os que deseja adicionar:"',
     '"**Suggested to-dos** — check the ones you want to add:"'),
    ('if st.button("🕓 Ver histórico", key=f"hist_{idea.id}"):',
     'if st.button("🕓 View history", key=f"hist_{idea.id}"):'),

    # ── Weekly Brief page ──────────────────────────────────────────────────────
    ('st.caption("Painel de preparação para reunião com Alberto Reuters e Stefan Lautenschlager.")',
     'st.caption("Meeting prep panel for Alberto Reuters and Stefan Lautenschlager.")'),
    ('_period = st.slider("Período (dias)", 3, 30, 7, key="wb_period")',
     '_period = st.slider("Period (days)", 3, 30, 7, key="wb_period")'),
    ('_show_team  = _c3.checkbox("👥 Time",   value=True, key="wb_team")',
     '_show_team  = _c3.checkbox("👥 Team",   value=True, key="wb_team")'),
    ("st.caption(f\"Período: **{_start.strftime('%d/%m/%Y')}** → **{date.today().strftime('%d/%m/%Y')}**\")",
     "st.caption(f\"Period: **{_start.strftime('%d/%m/%Y')}** → **{date.today().strftime('%d/%m/%Y')}**\")"),
    ("f\"Período: {_start.strftime('%d/%m/%Y')} → {_today.strftime('%d/%m/%Y')}\", \"\"]",
     "f\"Period: {_start.strftime('%d/%m/%Y')} → {_today.strftime('%d/%m/%Y')}\", \"\"]"),
    ('st.subheader("Desenvolvimentos da semana")',  'st.subheader("Developments")'),
    ('_export.append("## Desenvolvimentos")',        '_export.append("## Developments")'),
    ('st.info("Nenhum desenvolvimento registrado no período.")',
     'st.info("No developments recorded in this period.")'),
    ('_export.append("_Sem desenvolvimentos registrados._")',
     '_export.append("_No developments recorded._")'),
    ('_tipo = "Criada" if e["action"] == "CRIADA" else "Status"',
     '_tipo = "Created" if e["action"] == "CRIADA" else "Status"'),
    ('f\'<th style="{_TH}">Título</th>\'',          'f\'<th style="{_TH}">Title</th>\''),
    ('f\'<th style="{_TH}">Mudança</th>\'',          'f\'<th style="{_TH}">Change</th>\''),
    ('st.subheader("Em andamento")',                 'st.subheader("In progress")'),
    ('_export.append("## Em andamento")',             '_export.append("## In progress")'),
    ('st.info("Nenhum item em andamento no momento.")',
     'st.info("No items currently in progress.")'),
    ('_export.append("_Sem itens em andamento._")',  '_export.append("_No items in progress._")'),
    ('st.caption("Ideias em desenvolvimento")',      'st.caption("Ideas in development")'),
    ('f\'<th style="{_TH2}">Título</th>\'',          'f\'<th style="{_TH2}">Title</th>\''),
    ('st.caption("To-dos em andamento")',            'st.caption("In-progress to-dos")'),
    ('f\'<th style="{_TH2}">Prazo</th>\'',           'f\'<th style="{_TH2}">Due date</th>\''),
    ('st.caption("Vencendo em 7 dias")',             'st.caption("Due in 7 days")'),
    ("f\"vence {i.due_date.strftime('%d/%m')}\"",    "f\"due {i.due_date.strftime('%d/%m')}\""),
    ('f\'<th style="{_TH2}">Vence em</th>\'',        'f\'<th style="{_TH2}">Due</th>\''),
    ('st.subheader("Status do time")',               'st.subheader("Team status")'),
    ('_export.append("## 👥 Time")',                 '_export.append("## 👥 Team")'),
    ("st.caption(f\"{_role + ' — ' if _role else ''}último 1-on-1: {_latest['date']}\")",
     "st.caption(f\"{_role + ' — ' if _role else ''}last 1-on-1: {_latest['date']}\")"),
    ('st.markdown("**Tópicos:**")',                  'st.markdown("**Topics:**")'),
    ('st.markdown("**Action items em aberto:**")',   'st.markdown("**Open action items:**")'),
    ("_export += [f\"Último 1-on-1: {_latest['date']}\"]",
     "_export += [f\"Last 1-on-1: {_latest['date']}\"]"),
    ("st.caption(f\"{_role + ' — ' if _role else ''}sem 1-on-1 registrado\")",
     "st.caption(f\"{_role + ' — ' if _role else ''}no 1-on-1 recorded\")"),
    ("_export.append(f\"### {_m['name']} — sem 1-on-1\")",
     "_export.append(f\"### {_m['name']} — no 1-on-1\")"),
    ('st.subheader("Calls da semana")',              'st.subheader("Calls this week")'),
    ('st.info("Nenhuma call registrada no período.")',
     'st.info("No calls recorded in this period.")'),
    ('_export.append("_Sem calls registradas no período._")',
     '_export.append("_No calls recorded in this period._")'),
    ("_export.append(f\"Call com {_c['member']} em {_c['date'].strftime('%d/%m/%Y')}\")",
     "_export.append(f\"Call with {_c['member']} on {_c['date'].strftime('%d/%m/%Y')}\")"),
    ('st.subheader("Exportar resumo")',              'st.subheader("Export summary")'),
    ('st.download_button("⬇️ Baixar .md", data=_export_md,',
     'st.download_button("⬇️ Download .md", data=_export_md,'),
    ('with st.expander("Prévia do resumo exportado"):',
     'with st.expander("Exported summary preview"):'),

    # ── Claude Pro page ────────────────────────────────────────────────────────
    ('st.caption("Uso do Claude Pro · NBS D&A · Techco.lab")',
     'st.caption("Claude Pro usage · NBS D&A · Techco.lab")'),
    ('st.subheader("Relatório de adoção")',          'st.subheader("Adoption report")'),
    ('st.caption("Cronologia e métricas de adoção · atualizado automaticamente pelo agente diário")',
     'st.caption("Adoption timeline and metrics · auto-updated by the daily agent")'),
    ('if st.button("🔄 Atualizar agora", type="primary", key="cp_update_btn",',
     'if st.button("🔄 Update now", type="primary", key="cp_update_btn",'),
    ('with st.spinner("Atualizando..."):', 'with st.spinner("Updating..."):'),
    ('st.success("✅ Atualizado.")',        'st.success("✅ Updated.")'),
    ('st.error("❌ Falha. Verifique o Git.")', 'st.error("❌ Failed. Check Git.")'),
    ('with st.spinner("Atualizando relatório..."):', 'with st.spinner("Updating report..."):'),
    ("st.caption(f\"ℹ️ Atualizado automaticamente (estava em {_report_date_str or 'data desconhecida'}).\")",
     "st.caption(f\"ℹ️ Auto-updated (was dated {_report_date_str or 'unknown date'}).\")"),
    ('f"Relatório não encontrado em `{CLAUDE_PRO_REPORT_HTML}`. "',
     'f"Report not found at `{CLAUDE_PRO_REPORT_HTML}`. "'),
    ('"Execute o agente diário para gerar o arquivo."',
     '"Run the daily agent to generate the file."'),

    # ── English Coach page ─────────────────────────────────────────────────────
    ('st.caption("Evolução das sessões de prática de inglês · avaliadas por IA")',
     'st.caption("English practice session history · AI-rated")'),
    ('"Nenhuma sessão registrada ainda. "'
     '"Execute **english-coach.ps1** via Raycast (Win+Space → English Coach) para iniciar sua primeira sessão."',
     '"No sessions recorded yet. "'
     '"Run **english-coach.ps1** via Raycast (Win+Space → English Coach) to start your first session."'),
    ('_k1.metric("Sessões", len(_prog_rows))',   '_k1.metric("Sessions", len(_prog_rows))'),
    ('_k2.metric("Nota mais recente", f"{_latest[\'overall\']:.1f}/10")',
     '_k2.metric("Latest score", f"{_latest[\'overall\']:.1f}/10")'),
    ('_k3.metric("Média geral", f"{_avg:.1f}/10")',  '_k3.metric("Overall average", f"{_avg:.1f}/10")'),
    ('_k4.metric("Melhor nota", f"{_best:.1f}/10")', '_k4.metric("Best score", f"{_best:.1f}/10")'),
    ("_k1.caption(f\"Nível atual: **{_latest['level']}**\")",
     "_k1.caption(f\"Current level: **{_latest['level']}**\")"),
    ('st.subheader("Evolução da nota")',             'st.subheader("Score progression")'),
    ('st.subheader("Sessões recentes")',             'st.subheader("Recent sessions")'),
    ('st.info("Nenhum arquivo de sessão encontrado.")',
     'st.info("No session files found.")'),
]

changed = 0
not_found = []
for old, new in replacements:
    if old in c:
        c = c.replace(old, new, 1)
        changed += 1
    else:
        not_found.append(old[:80])

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(c)

print(f"Applied {changed}/{len(replacements)} replacements.")
if not_found:
    print(f"\nNOT FOUND ({len(not_found)}):")
    for s in not_found:
        print(f"  - {s!r}")
