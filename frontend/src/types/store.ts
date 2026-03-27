export interface StoreItem {
  index: number;
  resref: string;
  name: string;
  infinite: boolean;
  stack_size: number;
  repos_x: number;
  repos_y: number;
  base_item: number | null;
  inv_slot_width: number;
  inv_slot_height: number;
  item_data?: Record<string, unknown>;
}

export interface StoreItemAddResult {
  success: boolean;
  item_resref: string;
  category_id: number;
  category_name: string;
  base_item: number;
  store_panel: number | null;
}

export interface StoreCategory {
  category_id: number;
  category_name: string;
  items: StoreItem[];
}

export interface StoreSettings {
  markup: number;
  markdown: number;
  max_buy_price: number;
  store_gold: number;
  identify_price: number;
  black_market: boolean;
  bm_markdown: number;
  will_not_buy: number[];
  will_only_buy: number[];
}

export interface StoreSummary {
  resref: string;
  name: string;
  markup: number;
  markdown: number;
  max_buy_price: number;
  store_gold: number;
  item_count: number;
}

export interface StoreDetail {
  resref: string;
  name: string;
  tag: string;
  settings: StoreSettings;
  categories: StoreCategory[];
  raw_data?: Record<string, unknown>;
}

export interface StoreListResponse {
  stores: StoreSummary[];
  total: number;
  offset: number;
  limit: number;
}

// Store category constants (matches backend StoreCategories)
export const STORE_CATEGORIES = {
  ARMOR: 0,
  WEAPONS: 1,
  POTIONS_SCROLLS: 2,
  MAGIC_ITEMS: 3,
  MISCELLANEOUS: 4,
} as const;

export const CATEGORY_NAMES: Record<number, string> = {
  0: "Armor",
  1: "Weapons",
  2: "Potions/Scrolls",
  3: "Magic Items",
  4: "Miscellaneous",
};
