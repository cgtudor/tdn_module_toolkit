export interface EquipmentSlot {
  slot_id: number;
  slot_name: string;
  item_resref?: string;
  item_name?: string;
  item_data?: Record<string, unknown>;
}

export interface InventoryItem {
  index: number;
  resref: string;
  name: string;
  stack_size: number;
  repos_x: number;
  repos_y: number;
  item_data?: Record<string, unknown>;
}

export interface CreatureSummary {
  resref: string;
  first_name: string;
  last_name: string;
  display_name: string;
  race: number;
  appearance: number;
  equipment_count: number;
  inventory_count: number;
}

export interface CreatureDetail {
  resref: string;
  first_name: string;
  last_name: string;
  tag: string;
  race: number;
  race_name?: string;
  subrace?: string;
  appearance: number;
  appearance_name?: string;
  faction_id: number;
  faction_name?: string;
  gender: number;
  portrait?: string;
  equipment: EquipmentSlot[];
  inventory: InventoryItem[];
  raw_data?: Record<string, unknown>;
}

export interface CreatureListResponse {
  creatures: CreatureSummary[];
  total: number;
  offset: number;
  limit: number;
}

// Equipment slot constants
export const EQUIPMENT_SLOTS = {
  HEAD: 1,
  CHEST: 2,
  BOOTS: 4,
  ARMS: 8,
  RIGHT_HAND: 16,
  LEFT_HAND: 32,
  CLOAK: 64,
  LEFT_RING: 128,
  RIGHT_RING: 256,
  NECK: 512,
  BELT: 1024,
  ARROWS: 2048,
  BULLETS: 4096,
  BOLTS: 8192,
} as const;

export const SLOT_NAMES: Record<number, string> = {
  1: "Head",
  2: "Chest",
  4: "Boots",
  8: "Arms",
  16: "Right Hand",
  32: "Left Hand",
  64: "Cloak",
  128: "Left Ring",
  256: "Right Ring",
  512: "Neck",
  1024: "Belt",
  2048: "Arrows",
  4096: "Bullets",
  8192: "Bolts",
};
