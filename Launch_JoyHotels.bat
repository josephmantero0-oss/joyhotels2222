@echo off
TITLE JoyHotels Launcher
cd /d "%~dp0"

echo ==========================================
echo    JOYHOTELS SYSTEM IS STARTING...
echo ==========================================

if not exist .venv\Scripts\activate.bat goto ERR_VENV

echo [1/2] Activating environment...
call .venv\Scripts\activate.bat

echo [2/2] Starting server...
:: Open browser
start "" "http://localhost:5000"

echo.
echo System is running! Keep this window open.
echo ------------------------------------------
python app.py
if %ERRORLEVEL% neq 0 goto ERR_RUN
exit /b

:ERR_VENV
echo [ERROR] Virtual environment (.venv) not found.
echo Please follow the SETUP_GUIDE.md.
pause
exit /b

:ERR_RUN
echo.
echo [ERROR] The system stopped or crashed.
pause
exit /b
