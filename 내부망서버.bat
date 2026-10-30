@echo off
chcp 65001 > nul
title 상황판 내부망 서버 (다른 PC 접속 · 의견 받기)
cd /d "%~dp0"
echo.
echo  상황판 내부망 서버 - 다른 PC 에서 http://이 PC IP:8000/지도.html 로 접속
echo  직원 의견(💬)은 feedback 폴더에 쌓이고, 이 PC 에서 http://localhost:8000/의견함.html 로 봅니다.
echo  이 창을 닫으면 서버가 멈춥니다. (처음 실행 때 Windows 방화벽 허용 창이 뜨면 "허용")
echo.
set PYTHONUTF8=1
python tools\live_local.py --port 8000 --lan
pause
