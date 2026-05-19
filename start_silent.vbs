Set WShell = CreateObject("WScript.Shell")
WShell.Run "cmd /c """"C:\Users\Kelvin.okuda\techcolab-backlog\start_app.bat"""" >> """"C:\Users\Kelvin.okuda\techcolab-backlog\streamlit.log"""" 2>&1", 0, False
