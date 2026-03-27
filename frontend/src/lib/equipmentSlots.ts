// Equipment slot definitions for creature equipment management

export interface SlotDefinition {
  id: number;
  name: string;
  shortName: string;
  icon: string;
  gridPosition: { row: number; col: number };
}

export const EQUIPMENT_SLOT_DEFS: SlotDefinition[] = [
  { id: 1, name: "Head", shortName: "Head", icon: "crown", gridPosition: { row: 0, col: 1 } },
  { id: 512, name: "Neck", shortName: "Neck", icon: "gem", gridPosition: { row: 1, col: 0 } },
  { id: 64, name: "Cloak", shortName: "Cloak", icon: "wind", gridPosition: { row: 1, col: 2 } },
  { id: 2, name: "Chest", shortName: "Chest", icon: "shirt", gridPosition: { row: 2, col: 1 } },
  { id: 8, name: "Arms", shortName: "Arms", icon: "shield", gridPosition: { row: 2, col: 0 } },
  { id: 1024, name: "Belt", shortName: "Belt", icon: "minus", gridPosition: { row: 2, col: 2 } },
  { id: 16, name: "Right Hand", shortName: "R.Hand", icon: "sword", gridPosition: { row: 3, col: 0 } },
  { id: 32, name: "Left Hand", shortName: "L.Hand", icon: "shield", gridPosition: { row: 3, col: 2 } },
  { id: 128, name: "Left Ring", shortName: "L.Ring", icon: "circle", gridPosition: { row: 4, col: 0 } },
  { id: 256, name: "Right Ring", shortName: "R.Ring", icon: "circle", gridPosition: { row: 4, col: 2 } },
  { id: 4, name: "Boots", shortName: "Boots", icon: "footprints", gridPosition: { row: 4, col: 1 } },
  { id: 2048, name: "Arrows", shortName: "Arrows", icon: "arrow-right", gridPosition: { row: 5, col: 0 } },
  { id: 4096, name: "Bullets", shortName: "Bullets", icon: "circle-dot", gridPosition: { row: 5, col: 1 } },
  { id: 8192, name: "Bolts", shortName: "Bolts", icon: "arrow-right", gridPosition: { row: 5, col: 2 } },
  // Creature-specific slots (slot indices 14-17 from nwscript.nss)
  { id: 16384, name: "Creature Left Weapon", shortName: "C.L.Wpn", icon: "paw-print", gridPosition: { row: 6, col: 0 } },
  { id: 32768, name: "Creature Right Weapon", shortName: "C.R.Wpn", icon: "paw-print", gridPosition: { row: 6, col: 1 } },
  { id: 65536, name: "Creature Bite Weapon", shortName: "C.Bite", icon: "paw-print", gridPosition: { row: 6, col: 2 } },
  { id: 131072, name: "Creature Armour", shortName: "C.Armour", icon: "shirt", gridPosition: { row: 7, col: 1 } },
];

export function getSlotById(id: number): SlotDefinition | undefined {
  return EQUIPMENT_SLOT_DEFS.find(s => s.id === id);
}

export function getAllSlotIds(): number[] {
  return EQUIPMENT_SLOT_DEFS.map(s => s.id);
}
