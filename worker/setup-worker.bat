@echo off
rem createMovie PC render worker - one-click setup (details are in setup-worker.ps1)
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup-worker.ps1"
pause
