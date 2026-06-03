# raycast-close-session.ps1
# Abre o script de encerramento de sessão em janela PowerShell visível.
#
# @raycast.schemaVersion 1
# @raycast.title Encerrar Sessão (Techco.lab)
# @raycast.mode silent

$script = "$env:USERPROFILE\techcolab-backlog\close-session.ps1"

Start-Process powershell.exe -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy", "Bypass",
    "-File", "`"$script`""
) -WindowStyle Normal
