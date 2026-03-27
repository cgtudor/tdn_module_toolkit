import { EquipmentSlot, InventoryItem } from './creature';
import { StoreSettings, StoreCategory } from './store';

export interface AreaSummary {
  resref: string;
  name: string;
  store_count: number;
  creature_count: number;
}

export interface AreaListResponse {
  areas: AreaSummary[];
  total: number;
  offset: number;
  limit: number;
}

export interface StoreInstance {
  index: number;
  resref: string;
  template_resref?: string;
  tag: string;
  name: string;
  x: number;
  y: number;
  z: number;
  settings: StoreSettings;
  categories: StoreCategory[];
  raw_data?: Record<string, unknown>;
}

export interface CreatureInstance {
  index: number;
  resref: string;
  template_resref?: string;
  tag: string;
  first_name: string;
  last_name: string;
  x: number;
  y: number;
  z: number;
  equipment: EquipmentSlot[];
  inventory: InventoryItem[];
  raw_data?: Record<string, unknown>;
}

export interface SyncResult {
  success: boolean;
  message: string;
  changes_made: string[];
}

export interface SystemStatus {
  status: string;
  module_path: string;
  file_watcher: boolean;
  configured: boolean;
  counts: {
    items: number;
    creatures: number;
    stores: number;
    areas: number;
    item_references?: number;
  };
}

export interface GlobalSearchResponse {
  items: Array<{ resref: string; name: string; base_item: number; cost: number }>;
  creatures: Array<{ resref: string; first_name: string; last_name: string; display_name: string }>;
  stores: Array<{ resref: string; name: string }>;
  total: number;
}
