' Starts the app with no console window. Target of the desktop shortcut.
'
' It no longer opens the browser itself: it used to sleep a fixed 5 seconds and
' then open localhost:8501 regardless of whether anything was serving there —
' which on a slow start gave a connection error, and on a wedged old process gave
' a half-broken app that looked like the address had changed.
' scripts\start-app.ps1 opens the browser only once /_stcore/health answers.
Set WShell = CreateObject("WScript.Shell")
WShell.Run "cmd /c ""%USERPROFILE%\techcolab-backlog\start_app.bat""", 0, False
