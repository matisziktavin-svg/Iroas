@echo off
rem Double-click to run Iroas. Keep this window open (minimizing is fine).
cd /d "%~dp0"
title Iroas - personal trainer bot
if not exist ".venv\Scripts\python.exe" (
  echo Iroas is not installed yet. Double-click setup.bat first.
  pause
  exit /b 1
)
:loop
".venv\Scripts\python.exe" bot.py
if %errorlevel%==2 (
  echo Setup is not finished - double-click setup.bat first.
  pause
  exit /b 1
)
if %errorlevel%==3 (
  echo Iroas is already running in another window.
  pause
  exit /b 0
)
echo.
echo Iroas stopped. Restarting in 30 seconds - close this window to stop it for good.
timeout /t 30
goto loop
