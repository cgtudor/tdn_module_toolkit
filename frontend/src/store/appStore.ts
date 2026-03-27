import { create } from 'zustand';

export type ViewType = 'items' | 'creatures' | 'stores' | 'areas';

// Initialize dark mode from localStorage or system preference
const getInitialDarkMode = (): boolean => {
  const stored = localStorage.getItem('darkMode');
  if (stored !== null) {
    return stored === 'true';
  }
  // Default to system preference
  return window.matchMedia('(prefers-color-scheme: dark)').matches;
};

interface AppState {
  // Theme
  darkMode: boolean;
  setDarkMode: (dark: boolean) => void;
  toggleDarkMode: () => void;

  // Navigation
  currentView: ViewType;
  setCurrentView: (view: ViewType) => void;

  // Selection
  selectedItemResref: string | null;
  setSelectedItemResref: (resref: string | null) => void;

  selectedCreatureResref: string | null;
  setSelectedCreatureResref: (resref: string | null) => void;

  selectedStoreResref: string | null;
  setSelectedStoreResref: (resref: string | null) => void;

  selectedAreaResref: string | null;
  setSelectedAreaResref: (resref: string | null) => void;

  // Global search
  globalSearchQuery: string;
  setGlobalSearchQuery: (query: string) => void;

  // Item picker modal
  itemPickerOpen: boolean;
  itemPickerCallback: ((resref: string) => void) | null;
  openItemPicker: (callback: (resref: string) => void) => void;
  closeItemPicker: () => void;

  // System status
  systemStatus: {
    connected: boolean;
    mode: 'json_directory' | 'mod_file';
    dirtyCount: number;
    counts: {
      items: number;
      creatures: number;
      stores: number;
      areas: number;
    };
  };
  setSystemStatus: (status: AppState['systemStatus']) => void;
}

export const useAppStore = create<AppState>((set) => ({
  // Theme
  darkMode: getInitialDarkMode(),
  setDarkMode: (dark) => {
    localStorage.setItem('darkMode', String(dark));
    set({ darkMode: dark });
  },
  toggleDarkMode: () => set((state) => {
    const newValue = !state.darkMode;
    localStorage.setItem('darkMode', String(newValue));
    return { darkMode: newValue };
  }),

  // Navigation
  currentView: 'items',
  setCurrentView: (view) => set({ currentView: view }),

  // Selection
  selectedItemResref: null,
  setSelectedItemResref: (resref) => set({ selectedItemResref: resref }),

  selectedCreatureResref: null,
  setSelectedCreatureResref: (resref) => set({ selectedCreatureResref: resref }),

  selectedStoreResref: null,
  setSelectedStoreResref: (resref) => set({ selectedStoreResref: resref }),

  selectedAreaResref: null,
  setSelectedAreaResref: (resref) => set({ selectedAreaResref: resref }),

  // Global search
  globalSearchQuery: '',
  setGlobalSearchQuery: (query) => set({ globalSearchQuery: query }),

  // Item picker
  itemPickerOpen: false,
  itemPickerCallback: null,
  openItemPicker: (callback) => set({ itemPickerOpen: true, itemPickerCallback: callback }),
  closeItemPicker: () => set({ itemPickerOpen: false, itemPickerCallback: null }),

  // System status
  systemStatus: {
    connected: false,
    mode: 'json_directory',
    dirtyCount: 0,
    counts: { items: 0, creatures: 0, stores: 0, areas: 0 },
  },
  setSystemStatus: (status) => set({ systemStatus: status }),
}));
