@echo off
rem ============================================================
rem  Smart Travel Planner - start backend + frontend together
rem  Uses the portable Node and Python in the tools\ folder.
rem ============================================================
setlocal
set ROOT=%~dp0
set NODE=%ROOT%tools\node-v22.23.5-win-x64
set PY=%ROOT%tools\python312\python.exe

if not exist "%PY%" (
  echo [!] Python not found at %PY% - run the setup first.
  pause & exit /b 1
)

echo [1/2] Starting FastAPI backend on http://127.0.0.1:8000 ...
start "SmartTravel API" cmd /k "cd /d %ROOT%backend && %PY% -m uvicorn app.main:app --reload --no-access-log --host 127.0.0.1 --port 8000"

echo [2/2] Starting Vite frontend on http://localhost:5173 ...
start "SmartTravel Frontend" cmd /k "cd /d %ROOT%frontend && set PATH=%NODE%;%%PATH%% && npm run dev"

timeout /t 4 >nul
start "" http://localhost:5173
echo Done. Two windows opened - the website should now be in your browser.
