@echo off
chcp 65001 > nul
title 상황판 로컬 서버 (운영 데이터 자동 받기)
cd /d "%~dp0"
echo.
echo  상황판 로컬 서버 - http://localhost:8000/지도.html
echo  운영 서버가 올린 최신 데이터를 1분마다 받아 옵니다. 이 창을 닫으면 멈춥니다.
echo  (8000 포트를 이미 다른 서버가 쓰고 있으면 데이터만 받습니다)
echo.
set PYTHONUTF8=1
python tools\live_local.py --port 8000
pause
