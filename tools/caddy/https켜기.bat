@echo off
set "HERE=%~dp0"
chcp 65001 > nul
title HTTPS (Caddy) - 서버.bat 과 같이 켜 두세요
cd /d "%HERE%"
if not exist "%HERE%caddy.exe" (
  echo.
  echo  caddy.exe 가 없습니다. https://caddyserver.com/download 에서 Windows amd64 를 받아
  echo  이 폴더^(%HERE%^)에 caddy.exe 이름으로 넣으세요.
  echo.
  pause
  exit /b
)
echo.
echo  HTTPS 중계 - Caddyfile 설정대로 443 으로 받아 서버.bat^(8000^)으로 넘깁니다.
echo  서버.bat 이 먼저 켜져 있어야 합니다. 이 창을 닫으면 HTTPS 가 꺼집니다.
echo.
"%HERE%caddy.exe" run --config "%HERE%Caddyfile" --adapter caddyfile
pause
