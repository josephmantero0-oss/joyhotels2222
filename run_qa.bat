@echo off
echo ==============================================
echo       JoyHotels Quality Assurance Suite
echo ==============================================

echo.
echo [1] Running Automated Tests...
call .\.venv\Scripts\pytest.exe tests/ -v --cov=app

echo.
echo [2] Running Linter (Flake8)...
call .\.venv\Scripts\flake8.exe app.py --count --select=E9,F63,F7,F82 --show-source --statistics

echo.
echo QA Check Complete!
pause
