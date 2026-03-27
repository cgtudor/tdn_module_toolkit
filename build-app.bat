@echo off
REM Full application build script
REM Builds backend (PyInstaller), frontend (Vite), Electron, and packages everything

echo ========================================
echo Building TDN Module Toolkit
echo ========================================
echo.

cd /d "%~dp0"

REM Step 1: Install root dependencies
echo [1/5] Installing root dependencies...
call npm install
if errorlevel 1 (
    echo ERROR: Failed to install root dependencies
    exit /b 1
)

REM Step 2: Build Python backend
echo.
echo [2/5] Building Python backend...
call build-backend.bat
if errorlevel 1 (
    echo ERROR: Backend build failed
    exit /b 1
)

REM Step 3: Build frontend
echo.
echo [3/5] Building frontend...
cd frontend
call npm install
if errorlevel 1 (
    echo ERROR: Failed to install frontend dependencies
    exit /b 1
)

set ELECTRON_BUILD=true
call npm run build
if errorlevel 1 (
    echo ERROR: Frontend build failed
    exit /b 1
)
cd ..

REM Step 4: Compile Electron TypeScript
echo.
echo [4/5] Compiling Electron...
call npm run electron:compile
if errorlevel 1 (
    echo ERROR: Electron compile failed
    exit /b 1
)

REM Step 5: Package with electron-builder
echo.
echo [5/5] Packaging application...

REM Create resources directory if missing
if not exist "resources" mkdir "resources"

REM Check for icon, create placeholder if missing
if not exist "resources\icon.ico" (
    echo WARNING: resources\icon.ico not found. Using default Electron icon.
    REM We'll let electron-builder handle missing icon
)

call npm run package
if errorlevel 1 (
    echo ERROR: Packaging failed
    exit /b 1
)

echo.
echo ========================================
echo Build complete!
echo.
echo Output location: release\
echo.
echo To install, run the setup executable in the release folder.
echo ========================================
