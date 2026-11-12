@echo off
cd /d "%~dp0"
rem Runs hidden in background. Logs: server.log. Stop: end the python process on port 5100.
powershell -NoProfile -Command "Start-Process python -ArgumentList server.py -WorkingDirectory (Get-Location) -WindowStyle Hidden -RedirectStandardOutput server.log -RedirectStandardError server.err.log"
