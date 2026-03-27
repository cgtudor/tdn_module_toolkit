const API_BASE = '/api';

async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    ...options,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

// Items API
export const itemsApi = {
  list: (params: { offset?: number; limit?: number; base_item?: number }) =>
    fetchApi<{ items: unknown[]; total: number }>(`/items?${new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== undefined).map(([k, v]) => [k, String(v)])
    )}`),

  search: (q: string, limit = 50) =>
    fetchApi<{ items: unknown[]; total: number }>(`/items/search?q=${encodeURIComponent(q)}&limit=${limit}`),

  get: (resref: string) =>
    fetchApi<unknown>(`/items/${resref}`),

  baseItems: () =>
    fetchApi<{ base_items: { base_item: number; name: string; count: number }[] }>('/items/base-items/list'),

  getStoreCategory: (resref: string) =>
    fetchApi<{
      resref: string;
      base_item: number;
      base_item_name: string;
      store_panel: number | null;
      category_id: number;
      category_name: string;
    }>(`/items/${resref}/store-category`),

  getReferences: (resref: string) =>
    fetchApi<{
      creature_inventory: Array<{ creature_resref: string; index: number }>;
      creature_equipment: Array<{ creature_resref: string; slot_id: number }>;
      store_templates: Array<{ store_resref: string; category_id: number; index: number }>;
      area_stores: Array<{ area_resref: string; store_index: number; category_id: number; item_index: number }>;
      total_count: number;
    }>(`/items/${resref}/references`),

  updateInstances: (resref: string) =>
    fetchApi<{
      success: boolean;
      message: string;
      updated_counts: {
        creature_inventory: number;
        creature_equipment: number;
        area_stores: number;
        total: number;
      };
    }>(`/items/${resref}/update-instances`, { method: 'POST' }),

  update: (resref: string, data: Record<string, unknown>) =>
    fetchApi<unknown>(`/items/${resref}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  getPaletteCategories: () =>
    fetchApi<{
      categories: Array<{ id: number; strref: number; name: string }>;
      available: boolean;
    }>('/items/palette/categories'),

  getPropertyTypes: () =>
    fetchApi<{
      properties: Array<{
        id: number;
        label: string;
        has_subtype: boolean;
        has_cost_value: boolean;
        cost_table: number;
      }>;
    }>('/items/properties/types'),

  getPropertySubtypes: (propertyId: number) =>
    fetchApi<{
      subtypes: Array<{ id: number; label: string }>;
    }>(`/items/properties/${propertyId}/subtypes`),

  getPropertyCostValues: (propertyId: number) =>
    fetchApi<{
      cost_values: Array<{ id: number; label: string }>;
    }>(`/items/properties/${propertyId}/cost-values`),
};

// Creatures API
export const creaturesApi = {
  list: (params: { offset?: number; limit?: number }) =>
    fetchApi<{ creatures: unknown[]; total: number }>(`/creatures?${new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== undefined).map(([k, v]) => [k, String(v)])
    )}`),

  search: (q: string, limit = 50) =>
    fetchApi<{ creatures: unknown[]; total: number }>(`/creatures/search?q=${encodeURIComponent(q)}&limit=${limit}`),

  get: (resref: string) =>
    fetchApi<unknown>(`/creatures/${resref}`),

  setEquipment: (resref: string, slotId: number, itemResref: string) =>
    fetchApi<{ success: boolean }>(`/creatures/${resref}/equipment/${slotId}`, {
      method: 'PUT',
      body: JSON.stringify({ item_resref: itemResref }),
    }),

  removeEquipment: (resref: string, slotId: number) =>
    fetchApi<{ success: boolean }>(`/creatures/${resref}/equipment/${slotId}`, {
      method: 'DELETE',
    }),

  addInventory: (resref: string, itemResref: string, stackSize = 1) =>
    fetchApi<{ success: boolean }>(`/creatures/${resref}/inventory`, {
      method: 'POST',
      body: JSON.stringify({ item_resref: itemResref, stack_size: stackSize }),
    }),

  removeInventory: (resref: string, index: number) =>
    fetchApi<{ success: boolean }>(`/creatures/${resref}/inventory/${index}`, {
      method: 'DELETE',
    }),
};

// Stores API
export const storesApi = {
  list: (params: { offset?: number; limit?: number }) =>
    fetchApi<{ stores: unknown[]; total: number }>(`/stores?${new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== undefined).map(([k, v]) => [k, String(v)])
    )}`),

  search: (q: string, limit = 50) =>
    fetchApi<{ stores: unknown[]; total: number }>(`/stores/search?q=${encodeURIComponent(q)}&limit=${limit}`),

  get: (resref: string) =>
    fetchApi<unknown>(`/stores/${resref}`),

  updateSettings: (resref: string, settings: Record<string, unknown>) =>
    fetchApi<{ success: boolean }>(`/stores/${resref}/settings`, {
      method: 'PUT',
      body: JSON.stringify(settings),
    }),

  // Add item with automatic category detection (preferred)
  addItemAuto: (resref: string, itemResref: string, infinite = false, stackSize = 1) =>
    fetchApi<{
      success: boolean;
      item_resref: string;
      category_id: number;
      category_name: string;
      base_item: number;
      store_panel: number | null;
    }>(`/stores/${resref}/items`, {
      method: 'POST',
      body: JSON.stringify({ item_resref: itemResref, infinite, stack_size: stackSize }),
    }),

  // Add item to specific category (manual override)
  addItem: (resref: string, categoryId: number, itemResref: string, infinite = false, stackSize = 1) =>
    fetchApi<{ success: boolean }>(`/stores/${resref}/categories/${categoryId}/items`, {
      method: 'POST',
      body: JSON.stringify({ item_resref: itemResref, infinite, stack_size: stackSize }),
    }),

  updateItem: (resref: string, categoryId: number, index: number, updates: {
    infinite?: boolean;
    stack_size?: number;
    cost?: number;
    identified?: boolean;
    repos_x?: number;
    repos_y?: number;
  }) =>
    fetchApi<{ success: boolean }>(`/stores/${resref}/categories/${categoryId}/items/${index}`, {
      method: 'PUT',
      body: JSON.stringify(updates),
    }),

  removeItem: (resref: string, categoryId: number, index: number) =>
    fetchApi<{ success: boolean }>(`/stores/${resref}/categories/${categoryId}/items/${index}`, {
      method: 'DELETE',
    }),
};

// Areas API
export const areasApi = {
  list: (params: { offset?: number; limit?: number }) =>
    fetchApi<{ areas: unknown[]; total: number }>(`/areas?${new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== undefined).map(([k, v]) => [k, String(v)])
    )}`),

  search: (q: string, limit = 50) =>
    fetchApi<{ areas: unknown[]; total: number }>(`/areas/search?q=${encodeURIComponent(q)}&limit=${limit}`),

  get: (resref: string) =>
    fetchApi<unknown>(`/areas/${resref}`),

  listStores: (resref: string) =>
    fetchApi<{ stores: unknown[]; total: number }>(`/areas/${resref}/stores`),

  getStore: (resref: string, index: number) =>
    fetchApi<unknown>(`/areas/${resref}/stores/${index}`),

  listCreatures: (resref: string) =>
    fetchApi<{ creatures: unknown[]; total: number }>(`/areas/${resref}/creatures`),

  getCreature: (resref: string, index: number) =>
    fetchApi<unknown>(`/areas/${resref}/creatures/${index}`),

  syncStore: (resref: string, index: number) =>
    fetchApi<{ success: boolean; message: string; changes_made: string[] }>(
      `/areas/${resref}/stores/${index}/sync`,
      { method: 'POST' }
    ),

  updateStoreSettings: (resref: string, index: number, settings: {
    markup?: number;
    markdown?: number;
    max_buy_price?: number;
    store_gold?: number;
    identify_price?: number;
    black_market?: boolean;
    bm_markdown?: number;
    will_not_buy?: number[];
    will_only_buy?: number[];
  }) =>
    fetchApi<{ success: boolean; message: string; changes: string[] }>(
      `/areas/${resref}/stores/${index}/settings`,
      {
        method: 'PUT',
        body: JSON.stringify(settings),
      }
    ),

  // Add item with automatic category detection (preferred)
  addStoreItemAuto: (resref: string, storeIndex: number, itemResref: string, infinite = false) =>
    fetchApi<{
      success: boolean;
      item_resref: string;
      category_id: number;
      category_name: string;
      base_item: number;
      store_panel: number | null;
    }>(
      `/areas/${resref}/stores/${storeIndex}/items`,
      {
        method: 'POST',
        body: JSON.stringify({ item_resref: itemResref, infinite }),
      }
    ),

  // Add item to specific category (manual override)
  addStoreItem: (resref: string, storeIndex: number, categoryId: number, itemResref: string, infinite = false) =>
    fetchApi<{ success: boolean; item_resref: string }>(
      `/areas/${resref}/stores/${storeIndex}/categories/${categoryId}/items`,
      {
        method: 'POST',
        body: JSON.stringify({ item_resref: itemResref, infinite }),
      }
    ),

  updateStoreItem: (resref: string, storeIndex: number, categoryId: number, itemIndex: number, updates: {
    infinite?: boolean;
    stack_size?: number;
    cost?: number;
    identified?: boolean;
    repos_x?: number;
    repos_y?: number;
  }) =>
    fetchApi<{ success: boolean }>(
      `/areas/${resref}/stores/${storeIndex}/categories/${categoryId}/items/${itemIndex}`,
      {
        method: 'PUT',
        body: JSON.stringify(updates),
      }
    ),

  removeStoreItem: (resref: string, storeIndex: number, categoryId: number, itemIndex: number) =>
    fetchApi<{ success: boolean; index: number }>(
      `/areas/${resref}/stores/${storeIndex}/categories/${categoryId}/items/${itemIndex}`,
      { method: 'DELETE' }
    ),
};

// System API
export const systemApi = {
  status: () =>
    fetchApi<{
      status: string;
      mode: 'json_directory' | 'mod_file';
      module_path: string;
      file_watcher: boolean;
      configured: boolean;
      indexing: boolean;
      indexing_message: string;
      state: 'needs_configuration' | 'initializing' | 'indexing' | 'ready' | 'error';
      error_message: string | null;
      dirty_count: number;
      counts: {
        items: number;
        creatures: number;
        stores: number;
        areas: number;
        item_references?: number;
      };
    }>('/system/status'),

  reindex: () =>
    fetchApi<{
      success: boolean;
      counts: {
        items: number;
        creatures: number;
        stores: number;
        areas: number;
        item_references?: number;
      };
    }>('/system/reindex', { method: 'POST' }),

  reinitialize: () =>
    fetchApi<{
      success: boolean;
      message: string;
    }>('/config/reinitialize', { method: 'POST' }),

  dirty: () =>
    fetchApi<{
      has_unsaved_changes: boolean;
      dirty_count: number;
      dirty_resources: Array<[string, string]>;
    }>('/system/dirty'),

  save: () =>
    fetchApi<{
      success: boolean;
      message: string;
    }>('/system/save', { method: 'POST' }),
};

// Global search
export const searchApi = {
  global: (q: string, limit = 20) =>
    fetchApi<{ items: unknown[]; creatures: unknown[]; stores: unknown[]; total: number }>(
      `/search?q=${encodeURIComponent(q)}&limit=${limit}`
    ),
};
