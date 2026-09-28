@echo off
rem Double-click when Iroas says its Claude login expired. Gets a fresh token.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1" -RefreshClaude
pause
