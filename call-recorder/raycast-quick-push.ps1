# raycast-quick-push.ps1
# Commit e push rápido nos dois repos — sem testes, sem prompts.
# Use durante o desenvolvimento para salvar progresso no GitHub.
#
# @raycast.schemaVersion 1
# @raycast.title Push Rápido (Techco.lab)
# @raycast.mode silent

Start-Process powershell.exe -ArgumentList @(
    "-ExecutionPolicy", "Bypass",
    "-File", "$env:USERPROFILE\techcolab-backlog\quick-push.ps1"
) -WindowStyle Normal
