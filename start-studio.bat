@echo off
title H3 Studio
cd /d "%~dp0studio"
python server.py
if errorlevel 1 (
  echo.
  echo H3 Studio failed to start. If it is already running, open http://127.0.0.1:7870
  pause
)
