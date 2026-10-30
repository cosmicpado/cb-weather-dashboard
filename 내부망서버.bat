@echo off
chcp 65001 > nul
title 상황판 내부망 서버 (다른 PC 접속)
cd /d "%~dp0"
echo.
echo  상황판 내부망 서버 - 다른 PC 에서 http://이 PC IP:8000/지도.html 로 접속
echo  이 창을 닫으면 서버가 멈춥니다. (처음 실행 때 Windows 방화벽 허용 창이 뜨면 "허용")
echo.
set PYTHONUTF8=1
python tools\live_local.py --port 8000 --lan
pause
