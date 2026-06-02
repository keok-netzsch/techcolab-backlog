# raycast-execute-agent.ps1
# Fase 2 do agente: copia o comando certo para o clipboard e abre o Claude Code.
# Depois de abrir o Claude Code, basta colar (Ctrl+V) e pressionar Enter.
#
# @raycast.schemaVersion 1
# @raycast.title Executar Agente (Techco.lab)
# @raycast.mode silent

# Copia o comando para o clipboard
$cmd = "Execute the approved items from today's agent report"
Set-Clipboard -Value $cmd

# Abre o execute_agent.bat (que abre o Claude Code no diretório correto)
$script = "C:\Users\Kelvin.okuda\techcolab-backlog\execute_agent.bat"
Start-Process cmd.exe -ArgumentList @(
    "/k", "`"$script`""
) -WindowStyle Normal
