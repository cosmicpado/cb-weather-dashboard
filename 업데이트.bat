@echo off
chcp 65001 > nul
setlocal EnableExtensions
rem ==========================================================================
rem  상황판 업데이트 (Windows 운영 서버) - GitHub main 의 새 코드를 받아 반영한다.
rem    업데이트.bat            최신 main 반영
rem    업데이트.bat 커밋번호   그 커밋으로 되돌리기(문제가 생겼을 때)
rem  - 처음 실행이면(.git 이 없으면) 이 폴더를 GitHub 저장소에 연결한다.
rem  - .env, .data\(받은 의견), images\radar\ 등 깃에 없는 파일은 건드리지 않는다.
rem  - 수집기가 만든 자료(data.js, 기상 그림, 강수 누적)는 보관했다가 되돌려 놓는다.
rem  - 돌고 있는 서버(서버.bat)를 멈추고, 끝나면 다시 켠다.
rem  Rocky 서버는 tools\server\update-code.sh 를 쓴다(같은 방식).
rem ==========================================================================

rem 반영 중에 이 파일 자신이 바뀌면 배치가 꼬이므로, 임시 폴더에 복사해서 그쪽으로 실행한다
if /i not "%~1"=="__run" (
  copy /y "%~f0" "%TEMP%\cb_update_run.bat" > nul
  "%TEMP%\cb_update_run.bat" __run "%~dp0." %1
  exit /b
)
cd /d "%~2"
set "TARGET=%~3"
if "%TARGET%"=="" set "TARGET=origin/main"
title 상황판 업데이트
set "REPO=https://github.com/cosmicpado/cb-weather-dashboard.git"
rem safe.directory: 다른 PC에서 복사해 온 폴더도 허용 / schannel: 윈도우 인증서 저장소 사용(기관 보안장비 대비)
rem (for /f 안에서는 '=' 가 공백으로 바뀌어 -c 옵션 대신 환경변수로 준다)
set "GIT_CONFIG_COUNT=2"
set "GIT_CONFIG_KEY_0=safe.directory"
set "GIT_CONFIG_VALUE_0=*"
set "GIT_CONFIG_KEY_1=http.sslBackend"
set "GIT_CONFIG_VALUE_1=schannel"
set "G=git"
set "BAK=%TEMP%\cbweather_keep"

echo.
echo  상황판 업데이트 - %CD%
echo.

where git > nul 2> nul
if errorlevel 1 goto :nogit

echo  [1/5] GitHub 에 연결합니다
if exist ".git" goto :hasgit
%G% init -q
%G% remote add origin %REPO%
echo        처음 연결 - 이 폴더를 GitHub 저장소에 연결했습니다
goto :fetch
:hasgit
%G% remote set-url origin %REPO% 2> nul
if errorlevel 1 %G% remote add origin %REPO%

:fetch
echo  [2/5] 새 코드를 받습니다
%G% fetch -q --depth 50 origin main
if errorlevel 1 goto :fetchfail
set "NEW="
for /f %%c in ('%G% rev-parse --verify -q %TARGET%') do set "NEW=%%c"
if not defined NEW goto :badtarget
set "OLD="
for /f %%c in ('%G% rev-parse --verify -q HEAD 2^>nul') do set "OLD=%%c"
if "%OLD%"=="%NEW%" goto :uptodate
if defined OLD (
  echo        바뀌는 내용:
  %G% log --oneline -15 %OLD%..%NEW% 2> nul
)

echo  [3/5] 서버를 잠깐 멈춥니다
if defined CB_UPDATE_TEST goto :stopped
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne $PID -and $_.CommandLine -match 'live_local[.]py|update_data[.]py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
timeout /t 2 /nobreak > nul
:stopped

echo  [4/5] 코드를 바꿉니다 (수집 자료는 보관 후 되돌림)
if exist "%BAK%" rmdir /s /q "%BAK%"
mkdir "%BAK%\images" "%BAK%\.tmp" > nul 2> nul
for %%f in (data.js data-cctv.js images\kma_radar.png images\kma_satellite.png images\kma_warn.png .tmp\rain_history.json) do (
  if exist "%%f" copy /y "%%f" "%BAK%\%%f" > nul
)
%G% checkout -q -f -B main %NEW%
if errorlevel 1 goto :cofail
for %%f in (data.js data-cctv.js images\kma_radar.png images\kma_satellite.png images\kma_warn.png .tmp\rain_history.json) do (
  if exist "%BAK%\%%f" copy /y "%BAK%\%%f" "%%f" > nul
)
rmdir /s /q "%BAK%" 2> nul

rem 파이썬 패키지 목록이 바뀌었거나 처음 연결이면 설치
set "PIP=0"
if not defined OLD set "PIP=1"
if defined OLD (
  %G% diff --quiet %OLD% %NEW% -- requirements.txt 2> nul
  if errorlevel 1 set "PIP=1"
)
if "%PIP%"=="1" (
  echo        파이썬 패키지를 확인합니다
  python -m pip install -q -r requirements.txt truststore
)

echo  [5/5] 서버를 다시 켭니다
if not defined CB_UPDATE_TEST start "" "%CD%\서버.bat"
echo.
for /f "delims=" %%l in ('%G% log --oneline -1') do echo  완료 - %%l
echo  화면은 브라우저 새로고침(F5)으로 바로 보입니다.
if defined OLD echo  되돌리려면: 업데이트.bat %OLD:~0,7%
echo.
pause
exit /b 0

:uptodate
for /f "delims=" %%l in ('%G% log --oneline -1') do echo  이미 최신입니다 - %%l
echo.
pause
exit /b 0

:nogit
echo  Git 이 설치되어 있지 않습니다.
echo  https://git-scm.com 에서 Git for Windows 를 받아 기본값으로 설치한 뒤 다시 실행하세요.
echo.
pause
exit /b 1

:fetchfail
echo.
echo  GitHub 에서 받지 못했습니다. 인터넷 또는 방화벽(github.com 443)을 확인하세요.
echo  지금 돌고 있는 서버는 그대로입니다.
echo.
pause
exit /b 1

:badtarget
echo.
echo  "%TARGET%" 커밋을 찾지 못했습니다. 커밋 번호를 확인하세요.
echo.
pause
exit /b 1

:cofail
echo.
echo  코드를 바꾸지 못했습니다. 이전 상태 그대로 서버를 다시 켭니다.
for %%f in (data.js data-cctv.js images\kma_radar.png images\kma_satellite.png images\kma_warn.png .tmp\rain_history.json) do (
  if exist "%BAK%\%%f" copy /y "%BAK%\%%f" "%%f" > nul
)
if not defined CB_UPDATE_TEST start "" "%CD%\서버.bat"
echo.
pause
exit /b 1
