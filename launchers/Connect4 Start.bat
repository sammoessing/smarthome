@echo off
REM Connect4 Home Assistant - double-click launcher for Windows.
REM Downloads the latest app, sets it up, starts it, and opens your browser.
setlocal
title Connect4 Home Assistant

set "APP_HOME=%USERPROFILE%\Connect4SmartHome"
set "SRC=%APP_HOME%\src"
set "ZIP_URL=https://github.com/sammoessing/smarthome/archive/HEAD.zip"

echo.
echo   Connect4 Home Assistant
echo.

if not exist "%APP_HOME%" mkdir "%APP_HOME%"

echo   Getting the latest app...
powershell -NoProfile -Command "try { Invoke-WebRequest -Uri '%ZIP_URL%' -OutFile '%TEMP%\connect4.zip' -UseBasicParsing; if (Test-Path '%TEMP%\connect4x') { Remove-Item -Recurse -Force '%TEMP%\connect4x' }; Expand-Archive '%TEMP%\connect4.zip' '%TEMP%\connect4x'; if (Test-Path '%SRC%') { Remove-Item -Recurse -Force '%SRC%' }; Move-Item (Get-ChildItem '%TEMP%\connect4x' | Select-Object -First 1).FullName '%SRC%'; exit 0 } catch { exit 1 }"
if errorlevel 1 (
  if exist "%SRC%" (
    echo   (couldn't check for updates - starting the version you already have^)
  ) else (
    echo   X No internet connection and no downloaded copy yet.
    echo     Connect to WiFi and double-click this again.
    pause
    exit /b 1
  )
)

REM Find a Python that actually runs. The bare "python" on Windows is often
REM a Microsoft Store placeholder that only opens the Store (so "where python"
REM finds it but it can't run anything) - verify it really works.
set "PY="
python --version >nul 2>nul && set "PY=python"
if not defined PY py --version >nul 2>nul && set "PY=py"
if not defined PY (
  echo   X Python isn't installed yet. The Microsoft Store will open -
  echo     click Get / Install, wait for it to finish, then double-click
  echo     this file again.
  start ms-windows-store://search/?query=Python
  pause
  exit /b 1
)

if not exist "%APP_HOME%\.venv" (
  echo   Setting up ^(first run only, ~1 minute^)...
  %PY% -m venv "%APP_HOME%\.venv"
)
call "%APP_HOME%\.venv\Scripts\activate.bat"
python -m pip install -q -r "%SRC%\requirements.txt"

echo.
echo   Starting! Your browser will open in a moment.
echo   Leave this window open; close it to stop the app.
echo.

start "" /b cmd /c "timeout /t 3 >nul & start http://localhost:8000"
cd /d "%SRC%"
python -m app.launch
pause
