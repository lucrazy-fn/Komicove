@echo off
setlocal
pushd "%~dp0"
title Komicove DEV - codigo atual
set "PYTHONPATH=%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m komicove_app
) else (
  py -m komicove_app
)
if errorlevel 1 pause
popd
