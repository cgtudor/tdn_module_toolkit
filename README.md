# TDN Module Toolkit

A graphical toolkit that contains item, store and creature inventory management for The Dragon's Neck (TDN) Neverwinter Nights module.

## Quick Start

### First Time Setup

1. **Install Python 3.10+** (if not already installed)
   - Download from https://www.python.org/downloads/
   - During installation, check "Add Python to PATH"

2. **Install Node.js 18+** (if not already installed)
   - Download from https://nodejs.org/
   - Choose the LTS version

3. **Run setup**
   - Double-click `setup.bat`
   - Wait for setup to complete

### Running the Application

1. Double-click `run.bat`
2. Browser opens automatically to http://localhost:8000
3. On first run, configure your module path in the dialog that appears
4. Close the terminal window when done

## Features

- **Item Browser**: Search, filter, and view all item templates
- **Creature Inventory**: Edit equipment slots and inventory for creatures
- **Store Management**: Manage store categories, settings, and items
- **Area Instance Viewer**: Browse store and creature instances in areas
- **Real-time Updates**: Automatically detects file changes

## Requirements

| Software | Version | Purpose |
|----------|---------|---------|
| Python | 3.10+ | Runs the backend server |
| Node.js | 18+ | Only needed for initial setup |

After setup, you only need Python to run the application.

## Configuration

On first run, you'll be prompted to configure:
- **Module Path**: Location of your TDN module files (JSON format)
- **TLK Path**: (Optional) Path to custom string tables
- **2DA Path**: (Optional) Path to game data tables

Configuration is saved and persists between sessions.

## Troubleshooting

### "Frontend has not been built"
Run `setup.bat` first to complete initial setup.

### "Python is not installed"
Install Python 3.10+ from https://www.python.org/downloads/

### "Node.js is not installed"
Install Node.js 18+ from https://nodejs.org/

### Port 8000 already in use
Another application is using port 8000. Close it or change the port in the backend configuration.

### Changes not appearing
Click the refresh button in the application, or restart the server.

## For Developers

Use `run-dev.bat` instead of `run.bat` for development. This runs:
- Backend on http://127.0.0.1:8000 with hot reload
- Frontend on http://localhost:5173 with hot reload

### Manual Setup

```bash
# Backend
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn main:app --reload

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

### Rebuilding Frontend

After making frontend changes, rebuild with:
```bash
cd frontend
npm run build
```

## API Documentation

When the backend is running, visit http://127.0.0.1:8000/docs for interactive API documentation.

## Building a Release Executable

To package the toolkit as a standalone Windows application:

```bash
build-app.bat
```

This creates a Windows installer at `release\TDN Module Toolkit-1.0.0-Setup.exe`.

### What the Build Does

1. Installs npm dependencies
2. Builds Python backend with PyInstaller into a standalone executable
3. Builds the React frontend with Vite
4. Compiles the Electron desktop wrapper
5. Packages everything with electron-builder into an NSIS installer

### Build Requirements

- Node.js 18+
- Python 3.10+ with venv set up (`setup.bat`)
- PyInstaller (auto-installed during build)

### Custom Icon (Optional)

Place a 256x256 `icon.ico` file in the `resources\` directory before building. Without it, the default Electron icon is used.

### Development with Electron

To run the app as a desktop application during development:

```bash
run-dev-electron.bat
```

This starts the backend, frontend dev server, and Electron window together.

## Tech Stack

- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS, Shadcn/ui
- **Backend**: Python, FastAPI, SQLite (FTS5)
- **Desktop**: Electron, electron-builder (for packaging)
