# raycast-launcher.ps1
# Script chamado pelo Raycast para abrir o call-recorder em uma janela PowerShell visível.
# Configure no Raycast: Script Command → PowerShell → apontar para este arquivo.
#
# @raycast.schemaVersion 1
# @raycast.title Call Recorder
# @raycast.mode silent

$script = "C:\Users\Kelvin.okuda\techcolab-backlog\call-recorder\call-recorder.ps1"

Start-Process powershell.exe -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy", "Bypass",
    "-File", "`"$script`""
) -WindowStyle Normal
