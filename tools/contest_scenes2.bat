@echo off
chcp 65001 >nul
title createMovie 공모전 장면 재생성 v2
cd /d "%~dp0.."
echo createMovie 서비스의 대기열이 비어 있는지 확인하세요. (GPU를 같이 쓰면 메모리가 부족합니다)
python tools\contest_scenes2.py scenes_v2 01,03,05,06,07,09,10
pause
