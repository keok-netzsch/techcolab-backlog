# raycast-run-agent.ps1
# Roda o agente diário (Fase 1 — gera o relatório do dia).
# Após rodar, abra o relatório no Obsidian, marque os itens aprovados,
# e então use "Executar Agente" para a Fase 2.
#
# @raycast.schemaVersion 1
# @raycast.title Rodar Agente (Techco.lab)
# @raycast.mode silent

$script = "$env:USERPROFILE\techcolab-backlog\run_agent.bat"

Start-Process cmd.exe -ArgumentList @(
    "/k", "`"$script`""
) -WindowStyle Normal
