import { contextBridge, ipcRenderer } from 'electron';

/**
 * Electron API exposed to the renderer process via contextBridge.
 * This provides a secure way for the frontend to access native functionality.
 */
const electronAPI = {
  /**
   * Indicates that the app is running in Electron
   */
  isElectron: true,

  /**
   * Show a native file/folder open dialog
   */
  showOpenDialog: async (options: {
    title?: string;
    defaultPath?: string;
    properties?: Array<'openFile' | 'openDirectory' | 'multiSelections' | 'showHiddenFiles'>;
    filters?: Array<{ name: string; extensions: string[] }>;
  }): Promise<string[] | undefined> => {
    return ipcRenderer.invoke('show-open-dialog', options);
  },

  /**
   * Show a native file save dialog
   */
  showSaveDialog: async (options: {
    title?: string;
    defaultPath?: string;
    filters?: Array<{ name: string; extensions: string[] }>;
  }): Promise<string | undefined> => {
    return ipcRenderer.invoke('show-save-dialog', options);
  },

  /**
   * Get the app's executable path
   */
  getAppPath: async (): Promise<string> => {
    return ipcRenderer.invoke('get-app-path');
  },

  /**
   * Get the app's user data path
   */
  getUserDataPath: async (): Promise<string> => {
    return ipcRenderer.invoke('get-user-data-path');
  },

  /**
   * Get platform information
   */
  getPlatform: (): string => {
    return process.platform;
  }
};

// Expose the API to the renderer process
contextBridge.exposeInMainWorld('electronAPI', electronAPI);

// Type declaration for the global window object
declare global {
  interface Window {
    electronAPI?: typeof electronAPI;
  }
}
