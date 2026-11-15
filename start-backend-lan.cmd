@echo off
REM ===========================================================================
REM Start the FastAPI backend bound to your LAN so the Android APK / phone
REM (same Wi-Fi) and other devices can reach it.
REM
REM The backend's CORS list includes https://localhost (the Capacitor APK's
REM origin). Find your PC IP with: ipconfig   ^(IPv4 Address^)
REM The APK must be built with that IP:   set ANDROID_API_BASE_URL=http://YOUR_IP:8000
REM ===========================================================================
setlocal
cd /d "%~dp0"
set PY=tools\python312\python.exe
if not exist "%PY%" ( echo [!] tools\python312 missing - run the setup first & exit /b 1 )
for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "(Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -like '192.168.*' -or $_.IPAddress -like '10.*' -or $_.IPAddress -like '172.16.*' } | Select-Object -ExpandProperty IPAddress -First 1)"`) do set LANIP=%%i
if "%LANIP%"=="" set LANIP=localhost
echo Your PC LAN IP: %LANIP%
echo Phone APK must be built with:  set ANDROID_API_BASE_URL=http://%LANIP%:8000  then build-apk.cmd
REM Allow the phone's Host header (TrustedHost check) for this LAN IP only.
set ALLOWED_HOSTS=localhost,127.0.0.1,%LANIP%
"%PY%" -m uvicorn app.main:app --reload --no-access-log --host 0.0.0.0 --port 8000
endlocal
