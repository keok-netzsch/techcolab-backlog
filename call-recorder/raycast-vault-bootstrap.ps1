# raycast-vault-bootstrap.ps1
# Copia o contexto do vault para o clipboard via Local REST API.
# Assign a hotkey via Raycast ou atalho Windows (Ctrl+Alt+B).
#
# @raycast.schemaVersion 1
# @raycast.title Vault Bootstrap
# @raycast.mode silent

Start-Process powershell.exe -ArgumentList @(
    "-ExecutionPolicy", "Bypass",
    "-WindowStyle", "Hidden",
    "-File", "`"$env:USERPROFILE\techcolab-backlog\scripts\vault-bootstrap-clipboard.ps1`""
) -WindowStyle Hidden
