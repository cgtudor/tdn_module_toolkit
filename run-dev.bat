@echo off
echo Starting TDN Module Toolkit (Development Mode)...
echo.
echo This mode runs both servers with hot-reload enabled.
echo Use this for development. For normal use, use run.bat instead.
echo.

:: Check if Python is installed
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Python is not installed or not in PATH
    pause
    exit /b 1
)

:: Check if Node.js is installed
where node >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Node.js is not installed or not in PATH
    pause
    exit /b 1
)

:: Get the directory of this script
set SCRIPT_DIR=%~dp0

:: Install backend dependencies if needed
echo Checking backend dependencies...
cd /d "%SCRIPT_DIR%backend"
if not exist "venv" (
    echo Creating Python virtual environment...
    python -m venv venv
)
call venv\Scripts\activate.bat
pip install -r requirements.txt -q

:: Install frontend dependencies if needed
echo Checking frontend dependencies...
cd /d "%SCRIPT_DIR%frontend"
if not exist "node_modules" (
    echo Installing frontend dependencies...
    call npm install
)

:: Start backend in a new window
echo Starting backend server...
cd /d "%SCRIPT_DIR%backend"
start "TDN Module Toolkit - Backend" cmd /k "call venv\Scripts\activate.bat && python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload"

:: Wait a moment for backend to start
timeout /t 3 /nobreak >nul

:: Start frontend in a new window
echo Starting frontend server...
cd /d "%SCRIPT_DIR%frontend"
start "TDN Module Toolkit - Frontend" cmd /k "npm run dev"

:: Wait a moment then open browser
timeout /t 5 /nobreak >nul
echo Opening browser...
start http://localhost:5173

echo.
echo TDN Module Toolkit is running in DEVELOPMENT MODE!
echo - Backend: http://127.0.0.1:8000 (API docs: http://127.0.0.1:8000/docs)
echo - Frontend: http://localhost:5173 (with hot reload)
echo.
echo Close the terminal windows to stop the servers.
pause
