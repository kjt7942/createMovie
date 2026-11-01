@echo off
title createMovie
cd /d "%~dp0"
python server.py
if errorlevel 1 (
  echo.
  echo createMovie failed to start. If tools are missing, run setup.bat. If it is already running, open http://127.0.0.1:5000
  pause
)
