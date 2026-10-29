@echo off
rem createMovie PC render worker - run
chcp 65001 >nul
title createMovie render worker
cd /d "%~dp0"
set "PATH=%ProgramFiles%\nodejs;%LOCALAPPDATA%\Microsoft\WinGet\Links;%PATH%"
:loop
node "%~dp0worker.mjs"
rem restart automatically if it stops unexpectedly
timeout /t 10 >nul
goto loop
