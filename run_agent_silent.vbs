' Runs the daily backlog agent with no visible console window.
' Invoked by the "TechColab Backlog Agent" scheduled task.
'
' bWaitOnReturn (3rd argument) is True on purpose: wscript blocks until the
' agent finishes and hands the agent's exit code back to Task Scheduler.
' With False it returned 0 instantly, so every run showed a green
' "Last Run Result" even when Phase 2 was dead. The task's
' "Stop the task if it runs longer than" setting must be long enough
' for a full run (set to 2 hours).
Set WShell = CreateObject("WScript.Shell")
rc = WShell.Run("cmd /c ""%USERPROFILE%\techcolab-backlog\run_agent.bat""", 0, True)
WScript.Quit rc
