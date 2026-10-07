@echo off
TITLE Hotel Najuka System
cd /d "%~dp0"

echo ==========================================
echo    HOTEL NAJUKA SYSTEM IS STARTING...
echo ==========================================

if not exist .venv\Scripts\python.exe (
    echo [ERROR] Virtual environment (.venv) not found.
    pause
    exit /b 1
)

:: Check if port 5000 is already active
netstat -ano | findstr /R /C:":5000 .*LISTENING" >nul 2>&1
if %ERRORLEVEL%==0 (
    echo Server is already running. Opening browser...
    start "" "http://localhost:5000"
    timeout /t 2 >nul
    exit /b 0
)

echo [1/2] Launching Hotel Najuka App Server...
start "" powershell -Command "$null = Start-Sleep -Milliseconds 1500; Start-Process 'http://localhost:5000'"

echo [2/2] Keeping server active...
echo System is running at http://localhost:5000 (Keep this window open)
echo ------------------------------------------
.venv\Scripts\python.exe app.py

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] The system stopped or crashed.
    pause
    exit /b 1
)


