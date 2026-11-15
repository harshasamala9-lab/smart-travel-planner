@echo off
REM ===========================================================================
REM Build the Android APK (debug, installable).
REM Prerequisites (one time):  powershell -File tools\setup_android_sdk.ps1
REM
REM Usage:
REM   build-apk.cmd                          - APK calls http://10.0.2.2:8000 (PC loopback
REM                                            from the Android emulator)
REM   set ANDROID_API_BASE_URL=http://192.168.1.5:8000 && build-apk.cmd
REM                                          - APK calls your PC on the LAN (real phone,
REM                                            same Wi-Fi). Find your IP with ipconfig.
REM ===========================================================================
setlocal
cd /d "%~dp0"

set NODE_DIR=%CD%\tools\node-v22.23.5-win-x64
set JDK_DIR=%CD%\tools\jdk21
set SDK_DIR=%CD%\tools\android-sdk

if not exist "%NODE_DIR%\node.exe" ( echo [!] tools\node-v22.23.5-win-x64 missing & exit /b 1 )
if not exist "%JDK_DIR%\bin\java.exe" ( echo [!] Run: powershell -File tools\setup_android_sdk.ps1 & exit /b 1 )
if not exist "%SDK_DIR%\platforms\android-36" ( echo [!] Run: powershell -File tools\setup_android_sdk.ps1 & exit /b 1 )

set PATH=%NODE_DIR%;%PATH%
set JAVA_HOME=%JDK_DIR%
set ANDROID_HOME=%SDK_DIR%

if "%ANDROID_API_BASE_URL%"=="" set ANDROID_API_BASE_URL=http://10.0.2.2:8000
echo [1/3] Building web app with API base %ANDROID_API_BASE_URL% ...
cd frontend
set VITE_API_BASE_URL=%ANDROID_API_BASE_URL%
call cmd /c "npm run build" || exit /b 1

echo [2/3] Syncing web app into the Android project ...
call cmd /c "npx cap sync android" || exit /b 1

echo [3/3] Building debug APK (first run downloads Gradle + libraries) ...
cd android
call gradlew.bat assembleDebug || exit /b 1
cd ..\..

echo.
echo APK ready:  frontend\android\app\build\outputs\apk\debug\app-debug.apk
echo Install:    copy it to your phone, open it, allow "install unknown apps".
echo Backend:    start it with start-backend-lan.cmd so the phone can reach it.
endlocal
