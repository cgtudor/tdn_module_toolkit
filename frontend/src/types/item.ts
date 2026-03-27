export interface ItemProperty {
  property_name: number;
  property_name_resolved?: string;
  subtype?: number;
  subtype_resolved?: string;
  cost_table?: number;
  cost_value?: number;
  cost_value_resolved?: string;
  param1?: number;
  param1_value?: number;
  chance_appear?: number;
}

export interface ScriptVariable {
  name: string;
  var_type: number;  // 1=int, 2=float, 3=string
  value: number | string;
}

export interface ScriptVariableInput {
  name: string;
  var_type: number;  // 1=int, 2=float, 3=string
  value: number | string;
}

export interface ItemSummary {
  resref: string;
  name: string;
  base_item: number;
  cost: number;
  stack_size: number;
  identified: boolean;
}

export interface ItemDetail {
  resref: string;
  name: string;
  localized_name?: Record<string, unknown>;
  description?: string;
  localized_description?: Record<string, unknown>;
  tag: string;
  base_item: number;
  cost: number;
  additional_cost: number;
  stack_size: number;
  charges: number;
  cursed: boolean;
  identified: boolean;
  plot: boolean;
  stolen: boolean;
  palette_id?: number;
  comment?: string;
  properties: ItemProperty[];
  variables: ScriptVariable[];
  raw_data?: Record<string, unknown>;
}

export interface ItemListResponse {
  items: ItemSummary[];
  total: number;
  offset: number;
  limit: number;
}

export interface ItemSearchResponse {
  items: ItemSummary[];
  total: number;
}

// Types for item editing

export interface LocalizedStringUpdate {
  text?: string;
  string_ref?: number;
}

export interface ItemPropertyInput {
  property_name: number;
  subtype?: number;
  cost_table?: number;
  cost_value?: number;
  param1?: number;
  param1_value?: number;
  chance_appear?: number;
}

export interface ItemTemplateUpdate {
  // Basic fields
  name?: LocalizedStringUpdate;
  description?: LocalizedStringUpdate;
  desc_identified?: LocalizedStringUpdate;
  tag?: string;
  cost?: number;
  additional_cost?: number;
  stack_size?: number;
  charges?: number;

  // Flags
  identified?: boolean;
  plot?: boolean;
  cursed?: boolean;
  stolen?: boolean;

  // Properties (full replacement)
  properties?: ItemPropertyInput[];

  // Script variables (full replacement)
  variables?: ScriptVariableInput[];

  // Model parts (icon/appearance)
  model_part1?: number;
  model_part2?: number;
  model_part3?: number;

  // Advanced
  new_resref?: string;
  palette_category?: number;
}

export interface PaletteCategory {
  id: number;
  strref: number;
  name: string;
}

export interface PaletteCategoriesResponse {
  categories: PaletteCategory[];
  available: boolean;
}

// Types for item property editor dropdowns

export interface PropertyTypeOption {
  id: number;
  label: string;
  has_subtype: boolean;
  has_cost_value: boolean;
  cost_table: number;
}

export interface PropertySubtypeOption {
  id: number;
  label: string;
}

export interface PropertyCostValueOption {
  id: number;
  label: string;
}

export interface PropertyTypesResponse {
  properties: PropertyTypeOption[];
}

export interface PropertySubtypesResponse {
  subtypes: PropertySubtypeOption[];
}

export interface PropertyCostValuesResponse {
  cost_values: PropertyCostValueOption[];
}
