/**
 * Electron API type definitions and helper functions.
 *
 * This module provides utilities for detecting whether the app is running
 * in Electron and accessing native functionality through the exposed API.
 */

/**
 * Options for the native open dialog
 */
export interface OpenDialogOptions {
  title?: string;
  defaultPath?: string;
  properties?: Array<'openFile' | 'openDirectory' | 'multiSelections' | 'showHiddenFiles'>;
  filters?: Array<{ name: string; extensions: string[] }>;
}

/**
 * Options for the native save dialog
 */
export interface SaveDialogOptions {
  title?: string;
  defaultPath?: string;
  filters?: Array<{ name: string; extensions: string[] }>;
}

/**
 * The Electron API exposed via preload script
 */
export interface ElectronAPI {
  isElectron: boolean;
  showOpenDialog: (options: OpenDialogOptions) => Promise<string[] | undefined>;
  showSaveDialog: (options: SaveDialogOptions) => Promise<string | undefined>;
  getAppPath: () => Promise<string>;
  getUserDataPath: () => Promise<string>;
  getPlatform: () => string;
}

// Extend the Window interface to include electronAPI
declare global {
  interface Window {
    electronAPI?: ElectronAPI;
  }
}

/**
 * Check if the app is running in Electron
 */
export function isElectron(): boolean {
  return !!(window.electronAPI?.isElectron);
}

/**
 * Get the Electron API if available
 */
export function getElectronAPI(): ElectronAPI | undefined {
  return window.electronAPI;
}

/**
 * Show a native folder picker dialog
 * Returns the selected folder path or undefined if cancelled
 */
export async function showFolderDialog(options?: {
  title?: string;
  defaultPath?: string;
}): Promise<string | undefined> {
  if (!isElectron() || !window.electronAPI) {
    return undefined;
  }

  const result = await window.electronAPI.showOpenDialog({
    title: options?.title ?? 'Select Folder',
    defaultPath: options?.defaultPath,
    properties: ['openDirectory']
  });

  return result?.[0];
}

/**
 * Show a native file picker dialog
 * Returns the selected file path(s) or undefined if cancelled
 */
export async function showFileDialog(options?: {
  title?: string;
  defaultPath?: string;
  filters?: Array<{ name: string; extensions: string[] }>;
  multiple?: boolean;
}): Promise<string[] | undefined> {
  if (!isElectron() || !window.electronAPI) {
    return undefined;
  }

  const properties: Array<'openFile' | 'multiSelections'> = ['openFile'];
  if (options?.multiple) {
    properties.push('multiSelections');
  }

  const result = await window.electronAPI.showOpenDialog({
    title: options?.title ?? 'Select File',
    defaultPath: options?.defaultPath,
    filters: options?.filters,
    properties
  });

  return result;
}

/**
 * Show a native save dialog
 * Returns the selected save path or undefined if cancelled
 */
export async function showSaveDialog(options?: {
  title?: string;
  defaultPath?: string;
  filters?: Array<{ name: string; extensions: string[] }>;
}): Promise<string | undefined> {
  if (!isElectron() || !window.electronAPI) {
    return undefined;
  }

  return window.electronAPI.showSaveDialog({
    title: options?.title ?? 'Save File',
    defaultPath: options?.defaultPath,
    filters: options?.filters
  });
}
