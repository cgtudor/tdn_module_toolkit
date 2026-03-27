@echo off
setlocal enabledelayedexpansion

echo ===============================================
echo   TDN Module Toolkit - First Time Setup
echo ===============================================
echo.

:: Get the directory of this script
set SCRIPT_DIR=%~dp0

:: Check Python version
echo Checking Python installation...
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Python is not installed or not in PATH.
    echo.
    echo Please install Python 3.10 or later from:
    echo   https://www.python.org/downloads/
    echo.
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

:: Check Python version is 3.10+
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYTHON_VERSION=%%v
for /f "tokens=1,2 delims=." %%a in ("!PYTHON_VERSION!") do (
    set MAJOR=%%a
    set MINOR=%%b
)
if !MAJOR! LSS 3 (
    echo ERROR: Python 3.10+ is required. Found: !PYTHON_VERSION!
    pause
    exit /b 1
)
if !MAJOR! EQU 3 if !MINOR! LSS 10 (
    echo ERROR: Python 3.10+ is required. Found: !PYTHON_VERSION!
    pause
    exit /b 1
)
echo   Found Python !PYTHON_VERSION! - OK

:: Check Node.js installation
echo Checking Node.js installation...
node --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Node.js is not installed or not in PATH.
    echo.
    echo Please install Node.js 18 or later from:
    echo   https://nodejs.org/
    echo.
    echo Choose the LTS version for best compatibility.
    echo.
    pause
    exit /b 1
)

:: Check Node version is 18+
for /f "tokens=1 delims=v." %%v in ('node --version') do set NODE_MAJOR=%%v
if !NODE_MAJOR! LSS 18 (
    for /f "tokens=*" %%v in ('node --version') do set NODE_VERSION=%%v
    echo ERROR: Node.js 18+ is required. Found: !NODE_VERSION!
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('node --version') do echo   Found Node.js %%v - OK

echo.
echo -----------------------------------------------
echo   Setting up Python backend...
echo -----------------------------------------------

cd /d "%SCRIPT_DIR%backend"

:: Create virtual environment if it doesn't exist
if not exist "venv" (
    echo Creating Python virtual environment...
    python -m venv venv
    if %ERRORLEVEL% NEQ 0 (
        echo ERROR: Failed to create virtual environment.
        pause
        exit /b 1
    )
)

:: Activate venv and install dependencies
echo Installing backend dependencies...
call venv\Scripts\activate.bat
pip install -r requirements.txt -q
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to install backend dependencies.
    pause
    exit /b 1
)
echo   Backend dependencies installed - OK

echo.
echo -----------------------------------------------
echo   Building frontend application...
echo -----------------------------------------------

cd /d "%SCRIPT_DIR%frontend"

:: Install npm dependencies
echo Installing frontend dependencies...
call npm install
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to install frontend dependencies.
    pause
    exit /b 1
)

:: Build the frontend
echo Building frontend for production...
call npm run build
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to build frontend.
    pause
    exit /b 1
)

:: Verify build succeeded
if not exist "dist\index.html" (
    echo ERROR: Frontend build did not produce expected output.
    pause
    exit /b 1
)
echo   Frontend built successfully - OK

echo.
echo ===============================================
echo   Setup Complete!
echo ===============================================
echo.
echo You can now run the TDN Module Toolkit by double-clicking:
echo   run.bat
echo.
echo The browser will open automatically to the application.
echo.
pause
