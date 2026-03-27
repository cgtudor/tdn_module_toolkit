@echo off
echo Starting TDN Module Toolkit...
echo.

:: Get the directory of this script
set SCRIPT_DIR=%~dp0

:: Check if setup has been run
if not exist "%SCRIPT_DIR%frontend\dist\index.html" (
    echo ERROR: Frontend has not been built.
    echo.
    echo Please run setup.bat first to complete initial setup.
    echo.
    pause
    exit /b 1
)

if not exist "%SCRIPT_DIR%backend\venv" (
    echo ERROR: Python environment has not been set up.
    echo.
    echo Please run setup.bat first to complete initial setup.
    echo.
    pause
    exit /b 1
)

:: Start the backend server (serves both API and frontend)
cd /d "%SCRIPT_DIR%backend"
call venv\Scripts\activate.bat

echo Server starting at http://localhost:8000
echo.
echo Opening browser in 2 seconds...
echo Press Ctrl+C or close this window to stop the server.
echo.

:: Open browser after delay (in background)
start /b cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:8000"

:: Run the server (this blocks until Ctrl+C)
python -m uvicorn main:app --host 127.0.0.1 --port 8000
