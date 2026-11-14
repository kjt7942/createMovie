@echo off
chcp 65001 >nul
title createMovie 공모전 모델 시험 생성
cd /d "%~dp0.."
echo createMovie 서비스의 대기열이 비어 있는지 확인하세요. (GPU를 같이 쓰면 메모리가 부족합니다)
python tools\contest_test.py
pause
