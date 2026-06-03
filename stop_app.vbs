Set WShell = CreateObject("WScript.Shell")
WShell.Run "cmd /c ""%USERPROFILE%\techcolab-backlog\stop_app.bat""", 0, True
