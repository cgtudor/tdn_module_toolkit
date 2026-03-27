@echo off
REM Development mode launcher for TDN Module Toolkit
REM Runs backend, frontend dev server, and Electron concurrently

echo ========================================
echo TDN Module Toolkit - Development Mode
echo ========================================
echo.

cd /d "%~dp0"

REM Check if node_modules exists
if not exist "node_modules" (
    echo Installing root dependencies...
    call npm install
    if errorlevel 1 (
        echo ERROR: Failed to install dependencies
        exit /b 1
    )
)

REM Check if frontend node_modules exists
if not exist "frontend\node_modules" (
    echo Installing frontend dependencies...
    cd frontend
    call npm install
    if errorlevel 1 (
        echo ERROR: Failed to install frontend dependencies
        exit /b 1
    )
    cd ..
)

REM Check if backend venv exists
if not exist "backend\venv\Scripts\python.exe" (
    echo ERROR: Backend virtual environment not found.
    echo Please run setup.bat in the backend folder first.
    exit /b 1
)

REM Compile Electron TypeScript
echo Compiling Electron...
call npm run electron:compile
if errorlevel 1 (
    echo ERROR: Electron compile failed
    exit /b 1
)

echo.
echo Starting development servers...
echo   - Backend:  http://127.0.0.1:8000
echo   - Frontend: http://127.0.0.1:5173 (dev server)
echo   - Electron: Will launch after backend is ready
echo.
echo Press Ctrl+C to stop all servers.
echo.

REM Run all three concurrently
REM Note: We start backend first, wait a bit, then start others
call npm run dev
