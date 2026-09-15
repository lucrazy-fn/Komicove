@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m panel_app
) else (
  py -m panel_app
)
if errorlevel 1 pause
