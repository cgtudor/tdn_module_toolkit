// Store category definitions
// These match NWN's actual store tabs and the backend StoreCategories
//
// StorePanel values from baseitems.2da directly correspond to categories:
//   0 = Armor and Clothing
//   1 = Weapons
//   2 = Potions and Scrolls
//   3 = Wands and Magic Items
//   4 = Miscellaneous

export interface CategoryDefinition {
  id: number;
  name: string;
  icon: string;
}

export const STORE_CATEGORY_DEFS: CategoryDefinition[] = [
  { id: 0, name: "Armor", icon: "shield" },
  { id: 1, name: "Weapons", icon: "sword" },
  { id: 2, name: "Potions/Scrolls", icon: "flask-conical" },
  { id: 3, name: "Magic Items", icon: "wand" },
  { id: 4, name: "Miscellaneous", icon: "package" },
];

export function getCategoryById(id: number): CategoryDefinition | undefined {
  return STORE_CATEGORY_DEFS.find(c => c.id === id);
}

export function getAllCategoryIds(): number[] {
  return STORE_CATEGORY_DEFS.map(c => c.id);
}
