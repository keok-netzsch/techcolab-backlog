Set WShell = CreateObject("WScript.Shell")
WShell.Run "cmd /c ""C:\Users\Kelvin.okuda\techcolab-backlog\start_app.bat""", 0, False
WScript.Sleep 5000
WShell.Run "http://localhost:8501"
