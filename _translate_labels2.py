# -*- coding: utf-8 -*-
"""Second-pass translation for misses from _translate_labels.py"""
with open('app.py', encoding='utf-8') as f:
    c = f.read()

# ── Book titles (simple quoted string values) ─────────────────────────────
c = c.replace('"O Hobbit"',                          '"The Hobbit"')
c = c.replace('"Harry Potter e a Pedra Filosofal"',  '"Harry Potter and the Philosopher\'s Stone"')
c = c.replace('"1984, de Orwell"',                   '"1984 by Orwell"')
c = c.replace('"Guerra e Paz"',                      '"War and Peace"')

# ── Diagnostic tuples (individual strings) ────────────────────────────────
c = c.replace(
    '"**Frequência muito baixa** — {_avg_day:.1f} prompts/dia em média. "',
    '"**Very low frequency** — {_avg_day:.1f} prompts/day on average. "')
c = c.replace(
    '"Claude Code ainda não está integrado ao fluxo diário."',
    '"Claude Code is not yet integrated into the daily workflow."')
c = c.replace(
    '"Traga tarefas menores: revisão de e-mails, rascunhos, análise rápida de dados, geração de scripts. "',
    '"Bring smaller tasks: email reviews, drafts, quick data analysis, script generation. "')
c = c.replace(
    '"O hábito se forma no uso cotidiano, não nos grandes projetos."',
    '"The habit forms through daily use, not just large projects."')
c = c.replace(
    '"**Frequência abaixo do potencial** — {_avg_day:.1f} prompts/dia. "',
    '"**Frequency below potential** — {_avg_day:.1f} prompts/day. "')
c = c.replace(
    '"Há espaço para expandir o uso para mais tipos de tarefa."',
    '"There is room to expand usage to more types of tasks."')
c = c.replace(
    '"Identifique tarefas recorrentes que você ainda faz manualmente e experimente delegar ao Claude."',
    '"Identify recurring tasks you still do manually and try delegating them to Claude."')
c = c.replace(
    '"**Contexto subutilizado** — média de {_avg_tk_per_prompt/1000:.1f}K tokens/prompt. "',
    '"**Underused context** — average {_avg_tk_per_prompt/1000:.1f}K tokens/prompt. "')
c = c.replace(
    '"Sessões muito curtas aproveitam pouco o contexto de 200K disponível."',
    '"Very short sessions make poor use of the 200K context available."')
c = c.replace(
    '"Inclua o arquivo completo, não só o trecho. Descreva o projeto, dê exemplos. "',
    '"Include the full file, not just the snippet. Describe the project, give examples. "')
c = c.replace(
    '"Claude responde proporcionalmente ao contexto que recebe."',
    '"Claude responds proportionally to the context it receives."')
c = c.replace(
    '"**Cache pouco aproveitado** — {_cache_pct_diag}% de eficiência. "',
    '"**Underused cache** — {_cache_pct_diag}% efficiency. "')
c = c.replace(
    '"Poucas sessões reaproveitam contexto de sessões anteriores."',
    '"Few sessions reuse context from previous sessions."')
c = c.replace(
    '"Abra sessões mais longas em vez de várias curtas sobre o mesmo tema. "',
    '"Open longer sessions instead of many short ones on the same topic. "')
c = c.replace(
    '"Use /clear só ao mudar de assunto, não entre subtarefas relacionadas."',
    '"Use /clear only when switching subjects, not between related subtasks."')
c = c.replace(
    '"Usuário faz {_avg_day:.1f} prompts/dia com média de {_avg_tk_per_prompt/1000:.0f}K tokens cada. "',
    '"User makes {_avg_day:.1f} prompts/day with an average of {_avg_tk_per_prompt/1000:.0f}K tokens each. "')
c = c.replace(
    '"Identifique onde sessões mais longas trariam ainda mais valor vs. onde a profundidade atual é suficiente."',
    '"Identify where longer sessions would add even more value vs. where current depth is sufficient."')
c = c.replace(
    '"Cache efficiency de {_cache_pct_diag}%. "',
    '"Cache efficiency at {_cache_pct_diag}%. "')
c = c.replace(
    '"Sugira como estruturar projetos recorrentes para maximizar ainda mais esse padrão."',
    '"Suggest how to structure recurring projects to further maximize this pattern."')
c = c.replace(
    '"Uso distribuído em {len(_cc_projects)} projetos ({_top_proj}). "',
    '"Usage distributed across {len(_cc_projects)} projects ({_top_proj}). "')
c = c.replace(
    '"Identifique se faz sentido centralizar contexto entre projetos ou manter separado."',
    '"Identify whether centralizing context across projects makes sense or if separate is better."')

# ── Diagnostic HTML labels ─────────────────────────────────────────────────
c = c.replace(
    'text-transform:uppercase;letter-spacing:.04em">Problema</span>',
    'text-transform:uppercase;letter-spacing:.04em">Issue</span>')
c = c.replace(
    'text-transform:uppercase;letter-spacing:.04em">Como corrigir</span>',
    'text-transform:uppercase;letter-spacing:.04em">How to fix</span>')

# ── Ollama prompt ─────────────────────────────────────────────────────────
c = c.replace(
    '"Você é um consultor de produtividade com IA. "',
    '"You are an AI productivity consultant. "')
c = c.replace(
    '"Analise o padrão de uso do Claude Code abaixo e forneça insights acionáveis.\\n\\n"',
    '"Analyze the Claude Code usage pattern below and provide actionable insights.\\n\\n"')
c = c.replace(
    'f"Métricas reais (últimos 14 dias):\\n{_metrics_summary}\\n\\n"',
    'f"Real metrics (last 14 days):\\n{_metrics_summary}\\n\\n"')
c = c.replace(
    'f"Oportunidades identificadas:\\n{_opp_ctx}\\n\\n"',
    'f"Identified opportunities:\\n{_opp_ctx}\\n\\n"')
c = c.replace(
    '"Para cada oportunidade: explique quando usar Claude nesse contexto e quando NÃO usar. "',
    '"For each opportunity: explain when to use Claude in that context and when NOT to. "')
c = c.replace(
    '"Seja específico e prático. Máximo 200 palavras no total. Responda em português."',
    '"Be specific and practical. Maximum 200 words total. Respond in English."')
c = c.replace(
    'f"Ollama não disponível (`{OLLAMA_BASE_URL}`). "',
    'f"Ollama not available (`{OLLAMA_BASE_URL}`). "')
c = c.replace(
    '"Inicie o serviço com `ollama serve` para usar esta análise."',
    '"Start the service with `ollama serve` to use this analysis."')

# ── Weekly Brief export / f-strings ──────────────────────────────────────
c = c.replace(
    "f\"vence {i.due_date.strftime('%d/%m')}\"",
    "f\"due {i.due_date.strftime('%d/%m')}\"")
c = c.replace(
    '_export += [f"Último 1-on-1: {_latest[\'date\']}"]',
    '_export += [f"Last 1-on-1: {_latest[\'date\']}"]')
c = c.replace(
    '_export.append(f"Call com {_c[\'member\']} em {_c[\'date\'].strftime(\'%d/%m/%Y\')}")',
    '_export.append(f"Call with {_c[\'member\']} on {_c[\'date\'].strftime(\'%d/%m/%Y\')}")')

# ── English Coach ─────────────────────────────────────────────────────────
c = c.replace(
    '"Nenhuma sessão registrada ainda. "',
    '"No sessions recorded yet. "')
c = c.replace(
    '"Execute **english-coach.ps1** via Raycast (Win+Space → English Coach) para iniciar sua primeira sessão."',
    '"Run **english-coach.ps1** via Raycast (Win+Space → English Coach) to start your first session."')

# ── _metrics_summary Projetos label ──────────────────────────────────────
c = c.replace(
    "f\"Projetos: {', '.join(list(_cc_projects.keys())[:3])}\"",
    "f\"Projects: {', '.join(list(_cc_projects.keys())[:3])}\"")

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(c)

print("Patch 2 applied.")
