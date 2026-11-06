@echo off
chcp 65001 > nul
title 상황판 서버 (이 PC + 다른 PC 접속)
cd /d "%~dp0"
echo.
echo  상황판 서버 - 이 PC 가 직접 API 로 5분마다 데이터를 모읍니다. (.env 의 API 키 필요)
echo    이 PC 에서   : http://localhost:8000/지도.html
echo    다른 PC 에서 : http://이 PC IP:8000/지도.html  (실제 주소는 아래에 표시)
echo  이 창을 닫으면 서버가 멈춥니다. (처음 실행 때 Windows 방화벽 허용 창이 뜨면 "허용")
echo.
set PYTHONUTF8=1
python tools\live_local.py --port 8000 --lan --collect
pause
