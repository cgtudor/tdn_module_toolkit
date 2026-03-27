import { app, BrowserWindow, ipcMain, dialog, Menu } from 'electron';
import * as path from 'path';
import * as fs from 'fs';
import { backendManager } from './backend-manager';

// Ensure single instance - prevent multiple copies from running
const gotTheLock = app.requestSingleInstanceLock();

if (!gotTheLock) {
  // Another instance is already running, quit this one
  app.quit();
}

// Keep a global reference of the window object to prevent garbage collection
let mainWindow: BrowserWindow | null = null;
let splashWindow: BrowserWindow | null = null;

// Check if running in development mode
const isDev = !app.isPackaged;

// Get app version from package.json
function getAppVersion(): string {
  try {
    const packagePath = isDev
      ? path.join(__dirname, '..', '..', 'package.json')
      : path.join(app.getAppPath(), 'package.json');
    const packageJson = JSON.parse(fs.readFileSync(packagePath, 'utf-8'));
    return packageJson.version || '1.0.0';
  } catch {
    return '1.0.0';
  }
}

/**
 * Create the splash/loading window
 */
function createSplashWindow(): void {
  // Determine splash.html path
  // In dev: __dirname is electron/dist, splash.html is in electron/
  // In prod: splash.html is bundled in electron/ folder in the app
  const splashPath = isDev
    ? path.join(__dirname, '..', 'splash.html')
    : path.join(app.getAppPath(), 'electron', 'splash.html');

  console.log('Splash path:', splashPath);
  console.log('Splash exists:', fs.existsSync(splashPath));

  // Verify the splash file exists
  if (!fs.existsSync(splashPath)) {
    console.error('Splash file not found at:', splashPath);
    // Try alternative paths
    const altPaths = [
      path.join(__dirname, 'splash.html'),
      path.join(__dirname, '..', 'splash.html'),
      path.join(app.getAppPath(), 'splash.html'),
      path.join(app.getAppPath(), 'electron', 'splash.html'),
    ];
    for (const altPath of altPaths) {
      console.log('  Checking:', altPath, '- exists:', fs.existsSync(altPath));
    }
  }

  splashWindow = new BrowserWindow({
    width: 400,
    height: 320,
    frame: false,
    transparent: false,
    resizable: false,
    movable: true,
    center: true,
    alwaysOnTop: true,
    skipTaskbar: false,
    show: true, // Show immediately - don't wait for ready-to-show
    backgroundColor: '#1a1a2e',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true
    },
    icon: isDev
      ? path.join(__dirname, '..', 'resources', 'icon.ico')
      : path.join(process.resourcesPath || '', 'icon.ico'),
    title: 'TDN Module Toolkit'
  });

  // Load splash with error handling
  splashWindow.loadFile(splashPath).catch((err) => {
    console.error('Failed to load splash file:', err);
    // Show window anyway with error
    splashWindow?.show();
  });

  splashWindow.webContents.on('did-finish-load', () => {
    console.log('Splash loaded successfully');
    updateSplashVersion(getAppVersion());
  });

  splashWindow.webContents.on('did-fail-load', (_event, errorCode, errorDescription) => {
    console.error('Splash failed to load:', errorCode, errorDescription);
  });

  splashWindow.on('closed', () => {
    splashWindow = null;
  });
}

/**
 * Update the splash screen status
 */
function updateSplashStatus(status: string, substatus?: string, progress?: number): void {
  if (splashWindow && !splashWindow.isDestroyed()) {
    splashWindow.webContents.executeJavaScript(`
      if (window.electronSplash) {
        window.electronSplash.updateStatus(${JSON.stringify(status)}, ${JSON.stringify(substatus || '')});
        ${progress !== undefined ? `window.electronSplash.setProgress(${progress});` : ''}
      }
    `).catch(() => {});
  }
}

/**
 * Update the splash screen version
 */
function updateSplashVersion(version: string): void {
  if (splashWindow && !splashWindow.isDestroyed()) {
    splashWindow.webContents.executeJavaScript(`
      if (window.electronSplash) {
        window.electronSplash.setVersion(${JSON.stringify(version)});
      }
    `).catch(() => {});
  }
}

/**
 * Show error on splash screen
 */
function showSplashError(title: string, message: string): void {
  if (splashWindow && !splashWindow.isDestroyed()) {
    splashWindow.webContents.executeJavaScript(`
      if (window.electronSplash) {
        window.electronSplash.showError(${JSON.stringify(title)}, ${JSON.stringify(message)});
      }
    `).catch(() => {});
  }
}

/**
 * Close the splash window
 */
function closeSplashWindow(): void {
  if (splashWindow && !splashWindow.isDestroyed()) {
    splashWindow.close();
    splashWindow = null;
  }
}

/**
 * Create the main application window
 */
function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1000,
    minHeight: 700,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false // Required for preload script access
    },
    icon: isDev
      ? path.join(__dirname, '..', 'resources', 'icon.ico')
      : path.join(process.resourcesPath || '', 'icon.ico'),
    show: false, // Don't show until ready
    title: 'TDN Module Toolkit'
  });

  // Load the appropriate URL
  // In dev mode, load Vite dev server; in production, load from backend
  const appUrl = isDev ? 'http://localhost:5173' : backendManager.getUrl();
  console.log('Loading URL:', appUrl);
  mainWindow.loadURL(appUrl);

  // Show window when ready to prevent visual flash
  mainWindow.once('ready-to-show', () => {
    mainWindow?.show();
  });

  // Handle window closed
  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

/**
 * Create a minimal application menu
 */
function createMenu(): void {
  const template: Electron.MenuItemConstructorOptions[] = [
    {
      label: 'File',
      submenu: [
        { role: 'quit' }
      ]
    },
    {
      label: 'Edit',
      submenu: [
        { role: 'undo' },
        { role: 'redo' },
        { type: 'separator' },
        { role: 'cut' },
        { role: 'copy' },
        { role: 'paste' },
        { role: 'selectAll' }
      ]
    },
    {
      label: 'View',
      submenu: [
        { role: 'reload' },
        { role: 'forceReload' },
        { type: 'separator' },
        { role: 'resetZoom' },
        { role: 'zoomIn' },
        { role: 'zoomOut' },
        { type: 'separator' },
        { role: 'togglefullscreen' },
        { type: 'separator' },
        { role: 'toggleDevTools' }
      ]
    }
  ];

  const menu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(menu);
}

/**
 * Register IPC handlers for native dialogs and other functionality
 */
function registerIpcHandlers(): void {
  // Show open dialog (file/folder picker)
  ipcMain.handle('show-open-dialog', async (_event, options: {
    title?: string;
    defaultPath?: string;
    properties?: Array<'openFile' | 'openDirectory' | 'multiSelections' | 'showHiddenFiles'>;
    filters?: Array<{ name: string; extensions: string[] }>;
  }) => {
    const result = await dialog.showOpenDialog({
      title: options.title,
      defaultPath: options.defaultPath,
      properties: options.properties,
      filters: options.filters
    });

    if (result.canceled) {
      return undefined;
    }
    return result.filePaths;
  });

  // Show save dialog
  ipcMain.handle('show-save-dialog', async (_event, options: {
    title?: string;
    defaultPath?: string;
    filters?: Array<{ name: string; extensions: string[] }>;
  }) => {
    const result = await dialog.showSaveDialog({
      title: options.title,
      defaultPath: options.defaultPath,
      filters: options.filters
    });

    if (result.canceled) {
      return undefined;
    }
    return result.filePath;
  });

  // Get app path
  ipcMain.handle('get-app-path', () => {
    return app.getAppPath();
  });

  // Get user data path
  ipcMain.handle('get-user-data-path', () => {
    return app.getPath('userData');
  });
}

/**
 * Application startup sequence
 */
async function startup(): Promise<void> {
  console.log('TDN Module Toolkit starting...');
  console.log('  Development mode:', isDev);
  console.log('  App path:', app.getAppPath());

  // Show splash window immediately
  createSplashWindow();

  // Set up progress callback for backend manager
  backendManager.setProgressCallback((status, substatus, progress) => {
    updateSplashStatus(status, substatus, progress);
  });

  try {
    // Start the backend (progress updates will be sent to splash)
    await backendManager.start();

    // Set up application menu
    createMenu();

    // Register IPC handlers
    registerIpcHandlers();

    // Create the main window
    updateSplashStatus('Opening application...', undefined, 100);
    createWindow();

    // Close splash after a brief delay to ensure main window is ready
    setTimeout(() => {
      closeSplashWindow();
    }, 500);
  } catch (error) {
    console.error('Failed to start application:', error);

    // Show error on splash screen
    const errorMessage = error instanceof Error ? error.message : String(error);
    showSplashError('Startup Error', errorMessage);

    // Keep splash visible for a few seconds so user can read the error
    setTimeout(() => {
      dialog.showErrorBox(
        'Startup Error',
        `Failed to start the TDN Module Toolkit backend.\n\nError: ${errorMessage}`
      );
      app.quit();
    }, 3000);
  }
}

/**
 * Application shutdown sequence
 */
async function shutdown(): Promise<void> {
  console.log('Shutting down...');
  await backendManager.stop();
}

// Electron app lifecycle events
app.whenReady().then(startup);

// Handle second instance attempt - focus existing window
app.on('second-instance', () => {
  if (mainWindow) {
    if (mainWindow.isMinimized()) {
      mainWindow.restore();
    }
    mainWindow.focus();
  } else if (splashWindow) {
    splashWindow.focus();
  }
});

app.on('window-all-closed', () => {
  // On macOS, apps typically stay open until explicitly quit
  // On Windows/Linux, quit when all windows are closed
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  // On macOS, re-create window when dock icon is clicked and no windows exist
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

app.on('before-quit', async (event) => {
  // Prevent immediate quit to allow graceful shutdown
  event.preventDefault();
  await shutdown();
  // Now actually quit
  app.exit(0);
});

// Handle uncaught exceptions
process.on('uncaughtException', (error) => {
  console.error('Uncaught exception:', error);
  dialog.showErrorBox('Error', `An unexpected error occurred:\n\n${error.message}`);
});

process.on('unhandledRejection', (reason) => {
  console.error('Unhandled rejection:', reason);
});
