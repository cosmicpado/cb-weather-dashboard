@echo off
rem 이 파일이 있는 폴더 — chcp 로 글자판을 바꾸기 전에 먼저 잡아 둔다(바꾼 뒤에 읽으면 한글 경로가 꼬일 때가 있다)
set "HERE=%~dp0"
chcp 65001 > nul
title 상황판 서버 (이 PC + 다른 PC 접속)
cd /d "%HERE%"
if not exist "%HERE%tools\live_local.py" goto :nofolder
echo.
echo  상황판 서버 - 이 PC 가 직접 API 로 5분마다 데이터를 모읍니다. (.env 의 API 키 필요)
echo    이 PC 에서   : http://localhost:8000/지도.html
echo    다른 PC 에서 : http://이 PC IP:8000/지도.html  (실제 주소는 아래에 표시)
echo  이 창을 닫으면 서버가 멈춥니다. (처음 실행 때 Windows 방화벽 허용 창이 뜨면 "허용")
echo.
set PYTHONUTF8=1
python "%HERE%tools\live_local.py" --port 8000 --lan --collect
pause
exit /b

:nofolder
echo.
echo  상황판 폴더를 찾지 못했습니다.
echo    이 파일 위치 : %HERE%
echo    지금 폴더    : %CD%
echo  서버.bat 은 상황판 소스 폴더(tools 폴더가 있는 곳) 안에서 실행해야 합니다.
echo  바탕화면에서 켜고 싶으면 서버.bat 을 복사하지 말고, 오른쪽 클릭 - "바로 가기 만들기" 로 만든 것을 옮기세요.
echo.
pause
