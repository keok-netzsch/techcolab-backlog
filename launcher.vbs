Set WShell = CreateObject("WScript.Shell")
tb = WShell.ExpandEnvironmentStrings("%USERPROFILE%\techcolab-backlog")
WShell.Run "powershell.exe -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & tb & "\launcher.ps1""", 0, False
