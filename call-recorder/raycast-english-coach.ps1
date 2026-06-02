# raycast-english-coach.ps1
# Gera o relatório semanal do English Coach manualmente (sem esperar segunda-feira).
# Varre o vault pelos últimos 7 dias com lang: en e chama Ollama.
#
# @raycast.schemaVersion 1
# @raycast.title English Coach Report (Techco.lab)
# @raycast.mode silent

$script = "C:\Users\Kelvin.okuda\techcolab-backlog\run_english_coach.bat"

Start-Process cmd.exe -ArgumentList @(
    "/k", "`"$script`""
) -WindowStyle Normal
