@echo off
title createMovie log
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\service.ps1" logs
