@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo First run RUN_ME_WINDOWS.bat to install dependencies.
  pause
  exit /b 1
)
set "PYTHONPATH=%CD%\src"
".venv\Scripts\python.exe" -m pytest -q
pause
