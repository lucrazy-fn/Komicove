@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m komicove_app
) else (
  py -m komicove_app
)
if errorlevel 1 pause
