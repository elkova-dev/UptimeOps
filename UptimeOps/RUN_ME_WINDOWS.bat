@echo off
setlocal
cd /d "%~dp0"
echo [UptimeOps] Checking Python and dependencies...
if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
  if errorlevel 1 python -m venv .venv
  if errorlevel 1 goto :failed
)
".venv\Scripts\python.exe" -c "import fastapi, uvicorn, httpx, pytest" >nul 2>&1
if errorlevel 1 (
  echo Installing dependencies...
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 goto :failed
)
set "PYTHONPATH=%CD%\src"
echo.
echo Running UptimeOps - http://127.0.0.1:8002
echo To stop, press Ctrl+C.
echo.
".venv\Scripts\python.exe" -m uvicorn uptimeops.api:app --host 127.0.0.1 --port 8002
if errorlevel 1 (
  echo.
  echo Server stopped with an error. Check messages above.
)
pause
exit /b 0
:failed
echo.
echo Setup failed. Install Python 3.11+ and check your internet connection.
pause
exit /b 1
