@echo off
rem Double-click to check that Claude, Telegram and Hevy are all working.
cd /d "%~dp0"
".venv\Scripts\python.exe" doctor.py
pause
