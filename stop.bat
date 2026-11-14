@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\service.ps1" stop
pause
