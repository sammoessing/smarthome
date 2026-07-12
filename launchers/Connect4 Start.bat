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

REM Find a Python that actually runs. Two Windows traps to dodge:
REM  1) the bare "python" is often a Store placeholder stub that only opens
REM     the Store (so "where python" finds it but it can't run anything).
REM  2) the *installed* Microsoft Store build of Python runs fine for
REM     --version but is sandboxed and fails with "Access is denied" when
REM     this script tries to create a venv with it - skip it and use a
REM     real install instead.
set "PY="
set "PY_PATH="
for /f "delims=" %%P in ('where python 2^>nul') do if not defined PY_PATH set "PY_PATH=%%P"
if defined PY_PATH (
  echo %PY_PATH% | find /I "WindowsApps" >nul
  if errorlevel 1 python --version >nul 2>nul && set "PY=python"
)
if not defined PY (
  set "PY_PATH="
  for /f "delims=" %%P in ('where py 2^>nul') do if not defined PY_PATH set "PY_PATH=%%P"
  if defined PY_PATH (
    echo %PY_PATH% | find /I "WindowsApps" >nul
    if errorlevel 1 py --version >nul 2>nul && set "PY=py"
  )
)
if not defined PY (
  echo   X A working Python install is needed ^(the Microsoft Store version
  echo     can't run this app^). A download page will open - run the
  echo     installer and TICK "Add python.exe to PATH" on the first screen,
  echo     then double-click this file again.
  start https://www.python.org/downloads/
  pause
  exit /b 1
)

if not exist "%APP_HOME%\.venv\Scripts\python.exe" (
  echo   Setting up ^(first run only, ~1 minute^)...
  if exist "%APP_HOME%\.venv" rmdir /s /q "%APP_HOME%\.venv"
  %PY% -m venv "%APP_HOME%\.venv"
  if not exist "%APP_HOME%\.venv\Scripts\python.exe" (
    echo.
    echo   X Couldn't set up Python in %APP_HOME%\.venv
    echo     Usually antivirus blocking the folder, or a non-standard Python
    echo     install. Try:
    echo     1^) Briefly pause your antivirus, then double-click this again.
    echo     2^) If that doesn't help, reinstall Python from
    echo        https://www.python.org/downloads/ ^(TICK "Add python.exe to
    echo        PATH"^) and double-click this again.
    pause
    exit /b 1
  )
)
call "%APP_HOME%\.venv\Scripts\activate.bat"
python -m pip install -q -r "%SRC%\requirements.txt"
if errorlevel 1 (
  echo.
  echo   X Couldn't install required packages ^(see error above^).
  echo     Check your internet connection and double-click this again.
  pause
  exit /b 1
)

echo.
echo   Starting! Your browser will open in a moment.
echo   Leave this window open; close it to stop the app.
echo.

start "" /b cmd /c "timeout /t 3 >nul & start http://localhost:8000"
cd /d "%SRC%"
python -m app.launch
pause
