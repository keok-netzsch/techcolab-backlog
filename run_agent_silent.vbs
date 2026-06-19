' Runs the daily backlog agent with no visible console window.
' Invoked by the "TechColab Backlog Agent" scheduled task.
Set WShell = CreateObject("WScript.Shell")
WShell.Run "cmd /c ""%USERPROFILE%\techcolab-backlog\run_agent.bat""", 0, False
