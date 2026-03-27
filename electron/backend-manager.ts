import { spawn, ChildProcess } from 'child_process';
import * as path from 'path';
import * as fs from 'fs';
import * as http from 'http';
import { app } from 'electron';

const BACKEND_PORT = 8000;
const HEALTH_CHECK_URL = `http://127.0.0.1:${BACKEND_PORT}/api/system/status`;
const HEALTH_CHECK_TIMEOUT = 300000; // 5 minutes - indexing can take a while on first run
const HEALTH_CHECK_INTERVAL = 500; // 500ms between checks

export type ProgressCallback = (status: string, substatus?: string, progress?: number) => void;

/** Status response from backend /api/system/status endpoint */
interface BackendStatus {
  status: string;
  state: 'needs_configuration' | 'initializing' | 'indexing' | 'ready' | 'error';
  module_path: string;
  file_watcher: boolean;
  counts: Record<string, number>;
  configured: boolean;
  indexing: boolean;
  indexing_message: string;
  error_message: string | null;
}

export class BackendManager {
  private process: ChildProcess | null = null;
  private isDev: boolean;
  private onProgress: ProgressCallback | null = null;
  private logPath: string = '';

  constructor() {
    // Detect development vs production mode
    this.isDev = !app.isPackaged;
  }

  /**
   * Get the path to the log file
   */
  getLogPath(): string {
    return this.logPath;
  }

  /**
   * Initialize the log file for backend output
   */
  private initLogFile(): void {
    try {
      // Use same log folder as Python backend: %APPDATA%\TDN Module Toolkit\logs
      const appData = process.env.APPDATA || app.getPath('userData');
      const logDir = path.join(appData, 'TDN Module Toolkit', 'logs');
      if (!fs.existsSync(logDir)) {
        fs.mkdirSync(logDir, { recursive: true });
      }
      
      // Use timestamped log file (prefixed with 'electron-' to distinguish from Python backend logs)
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
      this.logPath = path.join(logDir, `electron-${timestamp}.log`);
      
      this.writeLog('='.repeat(60));
      this.writeLog(`Electron backend manager log started`);
      this.writeLog(`Development mode: ${this.isDev}`);
      this.writeLog('='.repeat(60));
      
      console.log('Electron log file:', this.logPath);
    } catch (err) {
      console.error('Failed to create log file:', err);
    }
  }

  /**
   * Write a message to the log file (synchronous for reliability)
   */
  private writeLog(message: string): void {
    if (!this.logPath) return;
    const timestamp = new Date().toISOString();
    const line = `[${timestamp}] ${message}\n`;
    try {
      fs.appendFileSync(this.logPath, line);
    } catch {
      // Ignore write errors
    }
  }

  /**
   * Close the log file
   */
  private closeLogFile(): void {
    this.writeLog('Log ended');
  }

  /**
   * Set the progress callback for startup status updates
   */
  setProgressCallback(callback: ProgressCallback): void {
    this.onProgress = callback;
  }

  /**
   * Report progress to the callback if set
   */
  private reportProgress(status: string, substatus?: string, progress?: number): void {
    if (this.onProgress) {
      this.onProgress(status, substatus, progress);
    }
  }

  /**
   * Get the path to the Python executable or bundled backend
   */
  private getBackendCommand(): { command: string; args: string[]; cwd: string } {
    if (this.isDev) {
      // Development mode: use venv Python
      // __dirname is electron/dist after compilation, so go up to tdn_module_toolkit
      const rootDir = path.join(__dirname, '..', '..');
      const backendDir = path.join(rootDir, 'backend');
      const pythonPath = path.join(backendDir, 'venv', 'Scripts', 'python.exe');
      return {
        command: pythonPath,
        args: ['-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', String(BACKEND_PORT)],
        cwd: backendDir
      };
    } else {
      // Production mode: use bundled executable
      const resourcesPath = process.resourcesPath || path.dirname(app.getPath('exe'));
      const backendPath = path.join(resourcesPath, 'backend', 'tdn-backend.exe');
      return {
        command: backendPath,
        args: [],
        cwd: path.join(resourcesPath, 'backend')
      };
    }
  }

  /**
   * Check if the backend is responding to health checks
   * Returns the backend status if responding, or null if not reachable
   */
  private checkHealth(): Promise<BackendStatus | null> {
    return new Promise((resolve) => {
      const request = http.get(HEALTH_CHECK_URL, { timeout: 2000 }, (response) => {
        if (response.statusCode !== 200) {
          resolve(null);
          return;
        }
        
        let data = '';
        response.on('data', (chunk) => { data += chunk; });
        response.on('end', () => {
          try {
            const status = JSON.parse(data) as BackendStatus;
            resolve(status);
          } catch {
            // Response wasn't valid JSON, but server is responding
            resolve(null);
          }
        });
        response.on('error', () => resolve(null));
      });
      request.on('error', () => resolve(null));
      request.on('timeout', () => {
        request.destroy();
        resolve(null);
      });
    });
  }

  /**
   * Wait for the backend to become healthy
   */
  private async waitForHealth(): Promise<boolean> {
    const startTime = Date.now();
    let lastReportedMessage = '';
    let dotCount = 0;

    while (Date.now() - startTime < HEALTH_CHECK_TIMEOUT) {
      const status = await this.checkHealth();
      
      if (status) {
        this.writeLog(`Health check response: state=${status.state}, configured=${status.configured}, indexing=${status.indexing}`);
        
        // Backend is responding - check if ready or needs configuration
        // Both are valid "startup complete" states
        if (status.state === 'ready' || status.state === 'needs_configuration') {
          this.writeLog(`Backend ready (state: ${status.state})`);
          return true;
        }
        
        // Report what the backend is actually doing
        if (status.indexing && status.indexing_message) {
          // Only update if message changed to avoid flickering
          if (status.indexing_message !== lastReportedMessage) {
            lastReportedMessage = status.indexing_message;
            this.reportProgress('Indexing...', status.indexing_message, 70);
          }
        } else if (status.state === 'initializing') {
          this.reportProgress('Initializing services...', undefined, 60);
        } else if (status.state === 'error') {
          this.reportProgress('Backend error', status.error_message || 'Unknown error', -1);
          this.writeLog(`Backend error: ${status.error_message}`);
          return false;
        }
      } else {
        // Backend not responding yet - show animated dots so user knows we're waiting
        dotCount = (dotCount + 1) % 4;
        const dots = '.'.repeat(dotCount + 1);
        this.reportProgress('Starting backend' + dots, 'Waiting for server to respond', 40);
      }
      
      await new Promise(resolve => setTimeout(resolve, HEALTH_CHECK_INTERVAL));
    }

    return false;
  }

  /**
   * Start the backend process and wait for it to be ready
   */
  async start(): Promise<void> {
    this.reportProgress('Checking for existing backend...', undefined, 5);

    // First check if backend is already running (e.g., from another instance)
    const alreadyRunning = await this.checkHealth();
    if (alreadyRunning) {
      console.log('Backend already running on port', BACKEND_PORT);
      this.reportProgress('Connected to existing backend', undefined, 100);
      return;
    }

    this.reportProgress('Preparing backend server...', undefined, 10);

    // Initialize log file for this session
    this.initLogFile();

    const { command, args, cwd } = this.getBackendCommand();

    console.log('Starting backend...');
    console.log('  Command:', command);
    console.log('  Args:', args.join(' '));
    console.log('  CWD:', cwd);
    
    this.writeLog(`Command: ${command}`);
    this.writeLog(`Args: ${args.join(' ')}`);
    this.writeLog(`CWD: ${cwd}`);
    
    // Check if the executable exists
    if (!this.isDev && !fs.existsSync(command)) {
      const errMsg = `Backend executable not found: ${command}`;
      this.writeLog(`ERROR: ${errMsg}`);
      throw new Error(errMsg);
    }

    this.reportProgress('Starting backend server...', this.isDev ? 'Development mode' : 'Production mode', 20);

    this.process = spawn(command, args, {
      cwd,
      stdio: ['ignore', 'pipe', 'pipe'],
      windowsHide: true,
      // Don't detach - we want to control the process
      detached: false
    });

    // Log backend output and update progress based on output
    this.process.stdout?.on('data', (data: Buffer) => {
      const output = data.toString().trim();
      console.log('[Backend]', output);
      this.writeLog(`[stdout] ${output}`);
      this.parseBackendOutput(output);
    });

    this.process.stderr?.on('data', (data: Buffer) => {
      const output = data.toString().trim();
      console.error('[Backend]', output);
      this.writeLog(`[stderr] ${output}`);
      this.parseBackendOutput(output);
    });

    this.process.on('error', (err) => {
      console.error('Failed to start backend:', err);
      this.writeLog(`[error] Failed to start backend: ${err.message}`);
      this.reportProgress('Backend failed to start', err.message, -1);
    });

    this.process.on('exit', (code, signal) => {
      console.log(`Backend exited with code ${code}, signal ${signal}`);
      this.writeLog(`[exit] Backend exited with code ${code}, signal ${signal}`);
      this.process = null;
    });

    this.reportProgress('Waiting for backend to initialize...', 'Loading Python runtime', 30);

    // Wait for backend to be ready
    const isReady = await this.waitForHealth();
    if (!isReady) {
      this.writeLog('ERROR: Backend failed to start within timeout period');
      throw new Error(`Backend failed to start within timeout period. Check log file: ${this.logPath}`);
    }

    this.reportProgress('Backend ready', 'Preparing interface...', 100);
    this.writeLog('Backend is ready');
    console.log('Backend is ready');
  }

  /**
   * Parse backend output for progress updates
   * Matches actual messages from the Python backend
   */
  private parseBackendOutput(output: string): void {
    // Match exact messages from backend/main.py and services/indexer.py
    if (output.includes('Starting Module Toolkit')) {
      this.reportProgress('Starting backend...', 'Initializing services', 25);
    } else if (output.includes('Module path:')) {
      const modulePath = output.split('Module path:')[1]?.trim() || '';
      // Show just the last folder name for brevity
      const shortPath = modulePath.split(/[/\\]/).pop() || modulePath;
      this.reportProgress('Loading module...', shortPath, 30);
    } else if (output.includes('Loading TLK files')) {
      this.reportProgress('Loading TLK files...', 'String tables for item names', 35);
    } else if (output.includes('TLK service loaded')) {
      this.reportProgress('TLK files loaded', output.includes('entries') ? output.split(':')[1]?.trim() : '', 40);
    } else if (output.includes('Loading 2DA files')) {
      this.reportProgress('Loading 2DA files...', 'Game data tables', 45);
    } else if (output.includes('2DA service loaded')) {
      this.reportProgress('2DA files loaded', '', 50);
    } else if (output.includes('Initializing core services')) {
      this.reportProgress('Initializing core services...', 'GFF parser, database', 55);
    } else if (output.includes('Core services initialized')) {
      this.reportProgress('Core services ready', '', 58);
    } else if (output.includes('Initializing API modules')) {
      this.reportProgress('Initializing API...', '', 60);
    } else if (output.includes('API modules initialized')) {
      this.reportProgress('API ready', '', 62);
    } else if (output.includes('Syncing index (incremental)')) {
      this.reportProgress('Syncing index...', 'This may take a while on first run', 65);
    } else if (output.includes('Indexing items')) {
      this.reportProgress('Indexing...', 'Scanning items', 70);
    } else if (output.includes('Indexing creatures')) {
      this.reportProgress('Indexing...', 'Scanning creatures', 75);
    } else if (output.includes('Indexing stores')) {
      this.reportProgress('Indexing...', 'Scanning stores', 80);
    } else if (output.includes('Indexing areas')) {
      this.reportProgress('Indexing...', 'Scanning areas', 85);
    } else if (output.includes('Index sync complete')) {
      this.reportProgress('Index complete', 'Starting server...', 88);
    } else if (output.includes('Uvicorn running') || output.includes('Application startup complete') || output.includes('Started server')) {
      this.reportProgress('Server started', 'Performing health check...', 95);
    }
  }

  /**
   * Stop the backend process gracefully
   */
  async stop(): Promise<void> {
    if (!this.process) {
      return;
    }

    console.log('Stopping backend...');

    return new Promise((resolve) => {
      const process = this.process!;

      // Set up timeout for force kill
      const forceKillTimeout = setTimeout(() => {
        console.log('Force killing backend...');
        process.kill('SIGKILL');
      }, 5000);

      // Handle clean exit
      process.once('exit', () => {
        clearTimeout(forceKillTimeout);
        this.process = null;
        console.log('Backend stopped');
        resolve();
      });

      // Try graceful shutdown first (SIGTERM)
      // On Windows, this sends WM_CLOSE which uvicorn handles
      process.kill();
    });
  }

  /**
   * Check if the backend process is running
   */
  isRunning(): boolean {
    return this.process !== null && !this.process.killed;
  }

  /**
   * Get the backend URL
   */
  getUrl(): string {
    return `http://127.0.0.1:${BACKEND_PORT}`;
  }
}

export const backendManager = new BackendManager();
