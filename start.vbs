' Starts createMovie with no window at all. Stop with stop.bat, read the log with logs.bat.
Set fso = CreateObject("Scripting.FileSystemObject")
script = fso.BuildPath(fso.GetParentFolderName(WScript.ScriptFullName), "tools\service.ps1")
CreateObject("WScript.Shell").Run "powershell -NoProfile -ExecutionPolicy Bypass -File """ & script & """ start", 0, False
