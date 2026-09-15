@echo off
setlocal
if "%~1"=="" (
  echo Uso: restore_server.bat caminho-do-backup.zip
  exit /b 2
)
if not exist ".venv\Scripts\python.exe" (
  echo Crie a .venv antes de executar.
  exit /b 2
)
".venv\Scripts\python.exe" -m panel_backend.server_backup restore "%~1"
