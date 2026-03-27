@echo off
REM Build the Python backend with PyInstaller
REM This creates a standalone executable that includes all dependencies

echo ========================================
echo Building TDN Module Toolkit Backend
echo ========================================

cd /d "%~dp0backend"

REM Ensure we're using the venv
if not exist "venv\Scripts\python.exe" (
    echo ERROR: Virtual environment not found. Run setup.bat first.
    exit /b 1
)

REM Use venv python/pip directly (more reliable than activate)
set VENV_PYTHON=venv\Scripts\python.exe
set VENV_PIP=venv\Scripts\pip.exe
REM Install PyInstaller if not present
%VENV_PIP% show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    %VENV_PIP% install pyinstaller
)

echo Building backend executable...

REM Clean previous build
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"

REM Build with PyInstaller (use python -m for reliable invocation)
REM --onedir: Creates a directory with all dependencies (faster startup than --onefile)
REM --name: Name of the output executable
REM --hidden-import: Include modules that PyInstaller might miss
%VENV_PYTHON% -m PyInstaller --onedir --name tdn-backend ^
    --hidden-import uvicorn.logging ^
    --hidden-import uvicorn.loops.auto ^
    --hidden-import uvicorn.protocols.http.auto ^
    --hidden-import uvicorn.protocols.websockets.auto ^
    --hidden-import uvicorn.lifespan.on ^
    --hidden-import uvicorn.lifespan.off ^
    --hidden-import email.mime ^
    --hidden-import email.mime.multipart ^
    --hidden-import email.mime.text ^
    --hidden-import aiosqlite ^
    --hidden-import sqlite3 ^
    --hidden-import watchdog ^
    --hidden-import watchdog.observers ^
    --hidden-import watchdog.events ^
    --hidden-import sse_starlette ^
    --hidden-import PIL ^
    --hidden-import PIL.Image ^
    --hidden-import PIL.TgaImagePlugin ^
    --hidden-import PIL.DdsImagePlugin ^
    --hidden-import PIL.PngImagePlugin ^
    --add-data "services;services" ^
    --add-data "api;api" ^
    --add-data "models;models" ^
    --add-data "db;db" ^
    main.py

if errorlevel 1 (
    echo ERROR: PyInstaller build failed
    exit /b 1
)

REM Move the output to the expected location
cd /d "%~dp0"
if not exist "build\python" mkdir "build\python"
if exist "build\python\tdn-backend" rmdir /s /q "build\python\tdn-backend"
move "backend\dist\tdn-backend" "build\python\tdn-backend"

REM Clean up build artifacts in backend folder
rmdir /s /q "backend\dist" 2>nul
rmdir /s /q "backend\build" 2>nul
del "backend\tdn-backend.spec" 2>nul

echo ========================================
echo Backend build complete!
echo Output: build\python\tdn-backend\
echo ========================================
