"""2DA file parser service for game data tables."""
import re
from pathlib import Path
from typing import Optional, Dict, List, Any


# Common faction names (hardcoded as these are rarely changed)
FACTION_NAMES = {
    0: "PC",
    1: "Hostile",
    2: "Commoner",
    3: "Merchant",
    4: "Defender"
}

# Damage type names (from iprp_damagetype.2da)
DAMAGE_TYPE_NAMES = {
    0: "Bludgeoning",
    1: "Piercing",
    2: "Slashing",
    3: "Subdual",
    4: "Physical",
    5: "Magical",
    6: "Acid",
    7: "Cold",
    8: "Divine",
    9: "Electrical",
    10: "Fire",
    11: "Negative",
    12: "Positive",
    13: "Sonic"
}

# Immunity type names (IP_CONST_IMMUNITYMISC_* from nwscript.nss)
IMMUNITY_TYPE_NAMES = {
    0: "Backstab",
    1: "Mind-Affecting",
    2: "Poison",
    3: "Disease",
    4: "Fear",
    5: "Trap",
    6: "Paralysis",
    7: "Blindness",
    8: "Deafness",
    9: "Slow",
    10: "Entangle",
    11: "Silence",
    12: "Stun",
    13: "Sleep",
    14: "Charm",
    15: "Dominate",
    16: "Confused",
    17: "Cursed",
    18: "Dazed",
    19: "Ability Decrease",
    20: "Attack Decrease",
    21: "Damage Decrease",
    22: "Damage Immunity Decrease",
    23: "AC Decrease",
    24: "Movement Speed Decrease",
    25: "Saving Throw Decrease",
    26: "Spell Resistance Decrease",
    27: "Skill Decrease",
    28: "Knockdown",
    29: "Negative Level",
    30: "Sneak Attack",
    31: "Critical Hit",
    32: "Death Magic"
}

# Ability names (for Ability Bonus property)
ABILITY_NAMES = {
    0: "Strength",
    1: "Dexterity",
    2: "Constitution",
    3: "Intelligence",
    4: "Wisdom",
    5: "Charisma"
}

# Damage resistance values (from iprp_resistcost.2da Amount column)
RESIST_COST_VALUES = {
    0: "Random",
    1: "5/-",
    2: "10/-",
    3: "15/-",
    4: "20/-",
    5: "25/-",
    6: "30/-",
    7: "35/-",
    8: "40/-",
    9: "45/-",
    10: "50/-"
}

# Damage reduction (soak) values (from iprp_soakcost.2da)
SOAK_COST_VALUES = {
    0: "Random",
    1: "5/+1",
    2: "5/+2",
    3: "5/+3",
    4: "5/+4",
    5: "5/+5",
    6: "10/+1",
    7: "10/+2",
    8: "10/+3",
    9: "10/+4",
    10: "10/+5",
    11: "15/+1",
    12: "15/+2",
    13: "15/+3",
    14: "15/+4",
    15: "15/+5",
    16: "20/+1",
    17: "20/+2",
    18: "20/+3",
    19: "20/+4",
    20: "20/+5"
}

# Saving throw types
SAVING_THROW_NAMES = {
    0: "All",
    1: "Fortitude",
    2: "Will",
    3: "Reflex"
}

# AC Modifier types
AC_MODIFIER_NAMES = {
    0: "Dodge",
    1: "Natural",
    2: "Armor",
    3: "Shield",
    4: "Deflection"
}

# Alignment group names (for IPRP_ALIGNGRP subtypes)
ALIGNMENT_GROUP_NAMES = {
    0: "Neutral",
    1: "Lawful",
    2: "Chaotic",
    3: "Good",
    4: "Evil"
}

# Specific alignment names (for IPRP_ALIGNMENT subtypes)
SPECIFIC_ALIGNMENT_NAMES = {
    0: "Lawful Good",
    1: "Lawful Neutral",
    2: "Lawful Evil",
    3: "Neutral Good",
    4: "True Neutral",
    5: "Neutral Evil",
    6: "Chaotic Good",
    7: "Chaotic Neutral",
    8: "Chaotic Evil"
}

# Cast Spell uses/charges (IP_CONST_CASTSPELL_NUMUSES_*)
CAST_SPELL_USES = {
    1: "1 Use/Day",
    2: "2 Uses/Day",
    3: "3 Uses/Day",
    4: "4 Uses/Day",
    5: "5 Uses/Day",
    6: "1 Charge",
    7: "2 Charges",
    8: "3 Charges",
    9: "4 Charges",
    10: "5 Charges",
    11: "Unlimited",
    12: "Single Use"
}

# Cost table ID to 2DA filename mapping
# CostTableResRef in itempropdef.2da maps to these 2DA files
COST_TABLE_2DA_MAP = {
    # 0 = No cost table (no lookup needed)
    # 2 = Simple bonus (+1, +2, etc.) - handled specially
    # 3 = Cast spell charges - handled specially with CAST_SPELL_USES
    4: "iprp_damagecost",   # Damage bonus values
    5: "iprp_immuncost",    # Damage immunity percentages
    6: "iprp_soakcost",     # Damage reduction values
    7: "iprp_resistcost",   # Damage resistance values
    10: "iprp_weightcost",  # Weight reduction values
    14: "iprp_ammocost",    # Unlimited ammo types
    17: "iprp_trapcost",    # Trap strength
    22: "iprp_damvulcost",  # Damage vulnerability
    25: "iprp_srcost",      # Spell resistance / skill bonus
    28: "iprp_matcost",     # Material types
    29: "iprp_qualcost",    # Quality types
    30: "iprp_addprop",     # Additional property (if exists)
}

# Cost tables where the value is a simple +X or -X bonus
SIMPLE_BONUS_COST_TABLES = {2}  # Simple bonus
SIMPLE_PENALTY_COST_TABLES = {20, 21}  # Penalty tables
# Cost table 3 is for cast spell uses/charges
CAST_SPELL_COST_TABLE = 3

# Property IDs that use specific subtype tables (fallback when SubTypeResRef is empty)
# Maps property_id -> subtype_type
PROPERTY_SUBTYPE_OVERRIDES = {
    # Damage type properties
    5: "damage_type",      # AC Bonus vs. Damage Type
    16: "damage_type",     # Damage Bonus
    17: "damage_type",     # Damage Bonus vs. Alignment Group
    18: "damage_type",     # Damage Bonus vs. Racial Group
    19: "damage_type",     # Damage Bonus vs. Specific Alignment
    20: "damage_type",     # Damage Immunity
    23: "damage_type",     # Damage Resistance
    24: "damage_type",     # Damage Vulnerability
    # Ability properties
    0: "ability",          # Ability Bonus
    27: "ability",         # Decreased Ability Score
    # AC modifier properties
    1: "ac_type",          # AC Bonus
    28: "ac_type",         # Decreased AC
    # Saving throw properties
    40: "saving_throw",    # Saving Throw Bonus
    41: "saving_throw",    # Saving Throw Bonus Specific
    49: "saving_throw",    # Decreased Saving Throws
    # Immunity misc
    37: "immunity_misc",   # Immunity Miscellaneous
}


class TDAService:
    """Service for parsing and querying 2DA game data files."""

    def __init__(self, baseitems_path: Optional[Path] = None,
                 itemprops_path: Optional[Path] = None,
                 racialtypes_path: Optional[Path] = None,
                 appearance_path: Optional[Path] = None,
                 tda_folder_path: Optional[Path] = None):
        """Initialize 2DA service.

        Args:
            baseitems_path: Path to baseitems.2da file
            itemprops_path: Path to itemprops.2da file
            racialtypes_path: Path to racialtypes.2da file
            appearance_path: Path to appearance.2da file
            tda_folder_path: Path to folder containing all 2DA files (for dynamic loading)
        """
        self.baseitems_path = baseitems_path
        self.itemprops_path = itemprops_path
        self.racialtypes_path = racialtypes_path
        self.appearance_path = appearance_path
        self.tda_folder_path = tda_folder_path

        self._baseitems: Dict[int, Dict[str, Any]] = {}
        self._baseitems_columns: List[str] = []

        self._itemprops: Dict[int, Dict[str, Any]] = {}
        self._itemprops_columns: List[str] = []

        self._racialtypes: Dict[int, Dict[str, Any]] = {}
        self._racialtypes_columns: List[str] = []

        self._appearances: Dict[int, Dict[str, Any]] = {}
        self._appearances_columns: List[str] = []

        # itempropdef.2da for subtype resolution
        self._itempropdef: Dict[int, Dict[str, Any]] = {}
        self._itempropdef_columns: List[str] = []
        self._itempropdef_loaded = False

        # Cache for dynamically loaded 2DA files (for subtype lookups)
        self._subtype_2da_cache: Dict[str, Dict[int, Dict[str, Any]]] = {}

        self._loaded = False
        self._itemprops_loaded = False
        self._racialtypes_loaded = False
        self._appearances_loaded = False

    def load_baseitems(self) -> bool:
        """Load baseitems.2da into memory.

        Returns:
            True if loaded successfully.
        """
        if not self.baseitems_path or not self.baseitems_path.exists():
            print(f"baseitems.2da not found at: {self.baseitems_path}")
            return False

        try:
            self._baseitems, self._baseitems_columns = self._parse_2da(self.baseitems_path)
            print(f"Loaded {len(self._baseitems)} base item entries")
            self._loaded = True
            return True
        except Exception as e:
            print(f"Failed to load baseitems.2da: {e}")
            return False

    def load_itemprops(self) -> bool:
        """Load itemprops.2da into memory.

        Returns:
            True if loaded successfully.
        """
        if not self.itemprops_path or not self.itemprops_path.exists():
            print(f"itemprops.2da not found at: {self.itemprops_path}")
            return False

        try:
            self._itemprops, self._itemprops_columns = self._parse_2da(self.itemprops_path)
            print(f"Loaded {len(self._itemprops)} item property entries")
            self._itemprops_loaded = True
            return True
        except Exception as e:
            print(f"Failed to load itemprops.2da: {e}")
            return False

    def load_racialtypes(self) -> bool:
        """Load racialtypes.2da into memory.

        Returns:
            True if loaded successfully.
        """
        if not self.racialtypes_path or not self.racialtypes_path.exists():
            print(f"racialtypes.2da not found at: {self.racialtypes_path}")
            return False

        try:
            self._racialtypes, self._racialtypes_columns = self._parse_2da(self.racialtypes_path)
            print(f"Loaded {len(self._racialtypes)} racial type entries")
            self._racialtypes_loaded = True
            return True
        except Exception as e:
            print(f"Failed to load racialtypes.2da: {e}")
            return False

    def load_appearances(self) -> bool:
        """Load appearance.2da into memory.

        Returns:
            True if loaded successfully.
        """
        if not self.appearance_path or not self.appearance_path.exists():
            print(f"appearance.2da not found at: {self.appearance_path}")
            return False

        try:
            self._appearances, self._appearances_columns = self._parse_2da(self.appearance_path)
            print(f"Loaded {len(self._appearances)} appearance entries")
            self._appearances_loaded = True
            return True
        except Exception as e:
            print(f"Failed to load appearance.2da: {e}")
            return False

    def load_itempropdef(self) -> bool:
        """Load itempropdef.2da into memory for subtype resolution.

        This file maps item property types to their subtype 2DA files
        via the SubTypeResRef column.

        Returns:
            True if loaded successfully.
        """
        if not self.tda_folder_path:
            return False

        itempropdef_path = self.tda_folder_path / "itempropdef.2da"
        if not itempropdef_path.exists():
            print(f"itempropdef.2da not found at: {itempropdef_path}")
            return False

        try:
            self._itempropdef, self._itempropdef_columns = self._parse_2da(itempropdef_path)
            print(f"Loaded {len(self._itempropdef)} itempropdef entries")
            self._itempropdef_loaded = True
            return True
        except Exception as e:
            print(f"Failed to load itempropdef.2da: {e}")
            return False

    def _load_subtype_2da(self, tda_name: str) -> Optional[Dict[int, Dict[str, Any]]]:
        """Load a subtype 2DA file on demand.

        Args:
            tda_name: Name of the 2DA file (without .2da extension), e.g. "Classes", "IPRP_SPELLS"

        Returns:
            Dict mapping row IDs to row data, or None if not found
        """
        if not self.tda_folder_path:
            return None

        # Check cache first (case-insensitive)
        cache_key = tda_name.lower()
        if cache_key in self._subtype_2da_cache:
            return self._subtype_2da_cache[cache_key]

        # Try to find the file (case-insensitive search)
        tda_path = None
        for filename in [f"{tda_name}.2da", f"{tda_name.lower()}.2da", f"{tda_name.upper()}.2da"]:
            candidate = self.tda_folder_path / filename
            if candidate.exists():
                tda_path = candidate
                break

        # If not found with exact match, do a case-insensitive scan of the directory
        if not tda_path:
            target_lower = f"{tda_name.lower()}.2da"
            try:
                for file in self.tda_folder_path.iterdir():
                    if file.name.lower() == target_lower:
                        tda_path = file
                        break
            except Exception:
                pass

        if not tda_path:
            # Cache the miss to avoid repeated disk scans
            self._subtype_2da_cache[cache_key] = None
            return None

        try:
            entries, _ = self._parse_2da(tda_path)
            self._subtype_2da_cache[cache_key] = entries
            print(f"Loaded subtype 2DA: {tda_path.name} ({len(entries)} entries)")
            return entries
        except Exception as e:
            print(f"Failed to load subtype 2DA {tda_path}: {e}")
            self._subtype_2da_cache[cache_key] = None
            return None

    def _get_label_from_2da_row(self, row_data: Dict[str, Any]) -> Optional[str]:
        """Extract a human-readable label from a 2DA row.

        Tries common column names for labels in order of preference.

        Args:
            row_data: Dictionary of column values for a 2DA row

        Returns:
            Label string, or None if not found
        """
        # Try common label columns in order of preference
        for col in ["Label", "label", "LABEL", "Name", "name", "NAME", "SpellName"]:
            value = row_data.get(col)
            if value is not None:
                return str(value).replace("_", " ")
        return None

    def load_all(self) -> dict:
        """Load all 2DA files.

        Returns:
            Dict with load results for each file.
        """
        results = {
            "baseitems": self.load_baseitems(),
            "itemprops": self.load_itemprops(),
            "racialtypes": self.load_racialtypes(),
            "appearances": self.load_appearances(),
            "itempropdef": self.load_itempropdef()
        }
        return results

    def _parse_2da(self, path: Path) -> tuple[Dict[int, Dict[str, Any]], List[str]]:
        """Parse a 2DA file.

        2DA format:
        - Line 1: "2DA V2.0"
        - Line 2: Empty or default value
        - Line 3: Column names (space-separated, may be quoted)
        - Line 4+: Data rows (row_id followed by values)

        Values of "****" represent null/empty values.

        Args:
            path: Path to 2DA file

        Returns:
            Tuple of (entries dict, column names list)
        """
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()

        if len(lines) < 3:
            raise ValueError("2DA file too short")

        # Verify header
        if not lines[0].strip().startswith("2DA"):
            raise ValueError("Invalid 2DA header")

        # Parse column names (line 3, index 2)
        # Handle quoted column names with spaces
        columns = self._tokenize_line(lines[2])

        # Parse data rows
        entries = {}
        for line in lines[3:]:
            line = line.strip()
            if not line:
                continue

            tokens = self._tokenize_line(line)
            if not tokens:
                continue

            # First token is row ID
            try:
                row_id = int(tokens[0])
            except ValueError:
                # Skip non-numeric row IDs (like "****")
                continue

            # Build row data
            row_data = {}
            for i, col_name in enumerate(columns):
                # Token index is i+1 (skip row_id)
                token_idx = i + 1
                if token_idx < len(tokens):
                    value = tokens[token_idx]
                    # Convert **** to None
                    if value == "****":
                        row_data[col_name] = None
                    else:
                        # Try to convert to int or float
                        row_data[col_name] = self._convert_value(value)
                else:
                    row_data[col_name] = None

            entries[row_id] = row_data

        return entries, columns

    def _tokenize_line(self, line: str) -> List[str]:
        """Tokenize a 2DA line, handling quoted strings.

        Args:
            line: Line to tokenize

        Returns:
            List of tokens
        """
        tokens = []
        line = line.strip()

        # Pattern to match quoted strings or whitespace-separated tokens
        pattern = r'"([^"]*)"|\S+'

        for match in re.finditer(pattern, line):
            if match.group(1) is not None:
                # Quoted string
                tokens.append(match.group(1))
            else:
                tokens.append(match.group(0))

        return tokens

    def _convert_value(self, value: str) -> Any:
        """Convert string value to appropriate type.

        Args:
            value: String value to convert

        Returns:
            Converted value (int, float, or str)
        """
        # Try integer
        try:
            return int(value)
        except ValueError:
            pass

        # Try float
        try:
            return float(value)
        except ValueError:
            pass

        # Return as string
        return value

    def get_baseitem(self, item_id: int) -> Optional[Dict[str, Any]]:
        """Get base item data by ID.

        Args:
            item_id: Base item ID

        Returns:
            Dict with item data, or None if not found
        """
        if not self._loaded:
            self.load_baseitems()

        return self._baseitems.get(item_id)

    def get_store_panel(self, item_id: int) -> Optional[int]:
        """Get StorePanel value for a base item.

        StorePanel determines which category an item appears in when
        viewing a store inventory in-game.

        Args:
            item_id: Base item ID

        Returns:
            StorePanel value, or None if not found
        """
        item = self.get_baseitem(item_id)
        if item:
            return item.get("StorePanel")
        return None

    def get_baseitem_name(self, item_id: int) -> str:
        """Get human-readable name for a base item.

        Args:
            item_id: Base item ID

        Returns:
            Item label/name, or "Unknown" if not found
        """
        item = self.get_baseitem(item_id)
        if item:
            # Try 'label' column first, then 'Name'
            label = item.get("label") or item.get("Name")
            if label:
                return str(label)
        return f"Unknown ({item_id})"

    def get_all_baseitems(self) -> Dict[int, Dict[str, Any]]:
        """Get all loaded base items.

        Returns:
            Dict mapping item ID to item data
        """
        if not self._loaded:
            self.load_baseitems()

        return self._baseitems.copy()

    def get_columns(self) -> List[str]:
        """Get column names from baseitems.2da.

        Returns:
            List of column names
        """
        if not self._loaded:
            self.load_baseitems()

        return self._baseitems_columns.copy()

    def is_loaded(self) -> bool:
        """Check if 2DA files have been loaded."""
        return self._loaded

    def get_baseitems_by_store_panel(self, store_panel: int) -> List[int]:
        """Get all base item IDs with a specific StorePanel value.

        Args:
            store_panel: StorePanel value to filter by

        Returns:
            List of base item IDs
        """
        if not self._loaded:
            self.load_baseitems()

        return [
            item_id for item_id, data in self._baseitems.items()
            if data.get("StorePanel") == store_panel
        ]

    def get_store_panel_mapping(self) -> Dict[int, List[int]]:
        """Get mapping of StorePanel values to base item IDs.

        Returns:
            Dict mapping StorePanel value to list of base item IDs
        """
        if not self._loaded:
            self.load_baseitems()

        mapping: Dict[int, List[int]] = {}
        for item_id, data in self._baseitems.items():
            panel = data.get("StorePanel")
            if panel is not None:
                if panel not in mapping:
                    mapping[panel] = []
                mapping[panel].append(item_id)

        return mapping

    # ===== Item Properties (itemprops.2da) =====

    def get_itemprop(self, prop_id: int) -> Optional[Dict[str, Any]]:
        """Get item property data by ID.

        Args:
            prop_id: Item property ID

        Returns:
            Dict with property data, or None if not found
        """
        if not self._itemprops_loaded:
            self.load_itemprops()

        return self._itemprops.get(prop_id)

    def get_itemprop_name(self, prop_id: int) -> str:
        """Get human-readable name for an item property.

        Uses the Label column from itemprops.2da (e.g., "Ability_Bonus", "AC_Bonus").

        Args:
            prop_id: Item property ID

        Returns:
            Property label/name, or "Unknown" if not found
        """
        prop = self.get_itemprop(prop_id)
        if prop:
            # Try 'Label' column first, then 'Name'
            label = prop.get("Label") or prop.get("Name")
            if label:
                # Clean up the label (replace underscores with spaces)
                return str(label).replace("_", " ")
        return f"Unknown ({prop_id})"

    # ===== Racial Types (racialtypes.2da) =====

    def get_racialtype(self, race_id: int) -> Optional[Dict[str, Any]]:
        """Get racial type data by ID.

        Args:
            race_id: Race ID

        Returns:
            Dict with race data, or None if not found
        """
        if not self._racialtypes_loaded:
            self.load_racialtypes()

        return self._racialtypes.get(race_id)

    def get_race_name(self, race_id: int) -> str:
        """Get human-readable name for a race.

        Uses the Label column from racialtypes.2da (e.g., "Dwarf", "Elf", "SunElf").

        Args:
            race_id: Race ID

        Returns:
            Race label/name, or "Unknown" if not found
        """
        race = self.get_racialtype(race_id)
        if race:
            label = race.get("Label") or race.get("Name")
            if label:
                return str(label)
        return f"Unknown ({race_id})"

    # ===== Appearances (appearance.2da) =====

    def get_appearance(self, appearance_id: int) -> Optional[Dict[str, Any]]:
        """Get appearance data by ID.

        Args:
            appearance_id: Appearance ID

        Returns:
            Dict with appearance data, or None if not found
        """
        if not self._appearances_loaded:
            self.load_appearances()

        return self._appearances.get(appearance_id)

    def get_appearance_name(self, appearance_id: int) -> str:
        """Get human-readable name for an appearance.

        Uses the LABEL column from appearance.2da (e.g., "(Dynamic) Dwarf", "Bear: Brown").

        Args:
            appearance_id: Appearance ID

        Returns:
            Appearance label/name, or "Unknown" if not found
        """
        appearance = self.get_appearance(appearance_id)
        if appearance:
            # appearance.2da uses "LABEL" (uppercase) column
            label = appearance.get("LABEL") or appearance.get("Label") or appearance.get("label")
            if label:
                return str(label)
        return f"Unknown ({appearance_id})"

    # ===== Factions =====

    def get_faction_name(self, faction_id: int) -> str:
        """Get human-readable name for a faction.

        Uses hardcoded common faction names.

        Args:
            faction_id: Faction ID

        Returns:
            Faction name, or "Faction X" if not a common faction
        """
        return FACTION_NAMES.get(faction_id, f"Faction {faction_id}")

    # ===== Item Property Resolution =====

    def resolve_property_subtype(self, property_id: int, subtype: int) -> Optional[str]:
        """Resolve an item property subtype to a human-readable name.

        Uses itempropdef.2da to determine which 2DA file contains the subtype
        names (via SubTypeResRef column), then looks up the name dynamically.

        Falls back to hardcoded mappings for common property types when the
        subtype 2DA cannot be loaded.

        Args:
            property_id: The property type ID
            subtype: The subtype value

        Returns:
            Human-readable subtype name, or None if not resolvable
        """
        # Try dynamic lookup from itempropdef.2da first
        resolved = self._resolve_subtype_dynamic(property_id, subtype)
        if resolved:
            return resolved

        # Fall back to hardcoded mappings for common properties
        # Damage-related properties use damage types
        # 16=Damage, 17=DamageAlignmentGroup, 18=DamageRacialGroup, 19=DamageSpecificAlignment
        # 20=DamageImmunity, 22=DamageReduced, 23=DamageResist, 24=DamageVulnerability
        if property_id in [16, 17, 18, 19, 20, 22, 23, 24]:
            return DAMAGE_TYPE_NAMES.get(subtype)

        # Immunity property (37)
        if property_id == 37:
            return IMMUNITY_TYPE_NAMES.get(subtype)

        # Ability Bonus (0), Decreased Ability (27)
        if property_id in [0, 27]:
            return ABILITY_NAMES.get(subtype)

        # Saving throw properties (40=ImprovedSavingThrows, 41=ImprovedSavingThrowsSpecific)
        if property_id in [40, 41]:
            return SAVING_THROW_NAMES.get(subtype)

        # AC Bonus (1), AC Bonus vs alignment (2-5), Decreased AC (28)
        if property_id in [1, 2, 3, 4, 5, 28]:
            return AC_MODIFIER_NAMES.get(subtype)

        return None

    def _resolve_subtype_dynamic(self, property_id: int, subtype: int) -> Optional[str]:
        """Resolve subtype using dynamic 2DA lookup from itempropdef.2da.

        Args:
            property_id: The property type ID
            subtype: The subtype value

        Returns:
            Human-readable subtype name, or None if not resolvable
        """
        # Ensure itempropdef.2da is loaded
        if not self._itempropdef_loaded:
            self.load_itempropdef()

        if not self._itempropdef_loaded:
            return None

        # Get the property definition
        prop_def = self._itempropdef.get(property_id)
        if not prop_def:
            return None

        # Get SubTypeResRef - the name of the 2DA containing subtypes
        subtype_resref = prop_def.get("SubTypeResRef")
        if not subtype_resref:
            return None

        # Load the subtype 2DA (case-insensitive)
        subtype_2da = self._load_subtype_2da(subtype_resref)
        if not subtype_2da:
            # Fall back to hardcoded tables for common subtypes if 2DA not found
            subtype_lower = subtype_resref.lower()
            if subtype_lower == "iprp_aligngrp":
                return ALIGNMENT_GROUP_NAMES.get(subtype)
            if subtype_lower == "iprp_alignment":
                return SPECIFIC_ALIGNMENT_NAMES.get(subtype)
            return None

        # Look up the subtype row
        row_data = subtype_2da.get(subtype)
        if not row_data:
            return None

        # Get the label
        return self._get_label_from_2da_row(row_data)

    def resolve_property_value(self, property_id: int, cost_value: int) -> Optional[str]:
        """Resolve an item property cost value to a human-readable format.

        Uses itempropdef.2da to determine which cost table to use, then
        looks up the value dynamically from the appropriate 2DA file.

        Args:
            property_id: The property type ID
            cost_value: The cost value (row in the cost table)

        Returns:
            Human-readable value, or None if not resolvable
        """
        # Try dynamic lookup first
        resolved = self._resolve_value_dynamic(property_id, cost_value)
        if resolved:
            return resolved

        # Fall back to hardcoded mappings for common properties
        # Damage Resistance (23) uses iprp_resistcost
        if property_id == 23:
            return RESIST_COST_VALUES.get(cost_value)

        # Damage Reduction (22) uses iprp_soakcost
        if property_id == 22:
            return SOAK_COST_VALUES.get(cost_value)

        # For simple numeric bonuses (like +1, +2, etc.), just format it
        # Properties that use cost table 2 (simple bonus values):
        # 0=Ability, 1=AC, 6=Enhancement, 7-9=Enhancement vs, 40-41=Saving Throws
        # 51=Regeneration, 67=VampiricRegeneration
        if property_id in [0, 1, 6, 7, 8, 9, 40, 41, 51, 67]:
            if cost_value > 0:
                return f"+{cost_value}"

        # Damage Immunity (20) - percentage values
        if property_id == 20:
            # Common damage immunity percentages
            immunity_pcts = {
                1: "5%", 2: "10%", 3: "25%", 4: "50%", 5: "75%", 6: "90%", 7: "100%"
            }
            return immunity_pcts.get(cost_value)

        return None

    def _resolve_value_dynamic(self, property_id: int, cost_value: int) -> Optional[str]:
        """Resolve cost value using dynamic 2DA lookup from itempropdef.2da.

        Args:
            property_id: The property type ID
            cost_value: The cost value (row in the cost table)

        Returns:
            Human-readable value, or None if not resolvable
        """
        # Ensure itempropdef.2da is loaded
        if not self._itempropdef_loaded:
            self.load_itempropdef()

        if not self._itempropdef_loaded:
            return None

        # Get the property definition
        prop_def = self._itempropdef.get(property_id)
        if not prop_def:
            return None

        # Get CostTableResRef - the cost table ID
        cost_table_ref = prop_def.get("CostTableResRef")
        if cost_table_ref is None:
            return None

        # Handle simple bonus tables (just +X or -X)
        if cost_table_ref in SIMPLE_BONUS_COST_TABLES:
            if cost_value > 0:
                return f"+{cost_value}"
            return None

        if cost_table_ref in SIMPLE_PENALTY_COST_TABLES:
            if cost_value > 0:
                return f"-{cost_value}"
            return None

        # Handle cost table 0 (no meaningful value)
        if cost_table_ref == 0:
            return None

        # Handle cost table 3 (cast spell uses/charges)
        if cost_table_ref == CAST_SPELL_COST_TABLE:
            return CAST_SPELL_USES.get(cost_value)

        # Get the 2DA filename for this cost table
        tda_name = COST_TABLE_2DA_MAP.get(cost_table_ref)
        if not tda_name:
            return None

        # Load the cost table 2DA
        cost_2da = self._load_subtype_2da(tda_name)
        if not cost_2da:
            return None

        # Look up the value row
        row_data = cost_2da.get(cost_value)
        if not row_data:
            return None

        # Get the label
        return self._get_label_from_2da_row(row_data)

    # ===== Item Property Editor Support =====

    def get_all_item_properties(self) -> List[Dict[str, Any]]:
        """Get list of all item property types with metadata for editor dropdowns.

        Returns a list of dicts with:
        - id: Property type ID
        - label: Human-readable name (e.g., "Ability Bonus")
        - has_subtype: Whether this property has subtypes
        - has_cost_value: Whether this property has cost values
        - cost_table: The cost table ID (for reference)

        Returns:
            List of property type options
        """
        if not self._itemprops_loaded:
            self.load_itemprops()

        if not self._itempropdef_loaded:
            self.load_itempropdef()

        result = []
        for prop_id, prop_data in self._itemprops.items():
            label = prop_data.get("Label") or prop_data.get("Name")
            if label:
                label = str(label).replace("_", " ")
            else:
                label = f"Property {prop_id}"

            # Skip reserved/placeholder entries
            label_lower = label.lower()
            if "reserved" in label_lower or label_lower.startswith("unused"):
                continue

            # Check itempropdef for subtype and cost table info
            has_subtype = False
            has_cost_value = False
            cost_table = 0

            # Check for hardcoded subtype overrides first
            if prop_id in PROPERTY_SUBTYPE_OVERRIDES:
                has_subtype = True

            if self._itempropdef_loaded:
                prop_def = self._itempropdef.get(prop_id)
                if prop_def:
                    subtype_resref = prop_def.get("SubTypeResRef")
                    if subtype_resref is not None and subtype_resref != "":
                        has_subtype = True

                    cost_table_ref = prop_def.get("CostTableResRef")
                    if cost_table_ref is not None:
                        cost_table = cost_table_ref
                        # Cost table > 0 means there are cost values
                        has_cost_value = cost_table_ref > 0

            result.append({
                "id": prop_id,
                "label": label,
                "has_subtype": has_subtype,
                "has_cost_value": has_cost_value,
                "cost_table": cost_table
            })

        # Sort by label for easier browsing
        result.sort(key=lambda x: x["label"].lower())
        return result

    def get_property_subtypes(self, property_id: int) -> Optional[List[Dict[str, Any]]]:
        """Get list of valid subtypes for a property type.

        Args:
            property_id: The property type ID

        Returns:
            List of {id, label} dicts, or None if no subtypes
        """
        # Check for hardcoded property overrides first
        override_type = PROPERTY_SUBTYPE_OVERRIDES.get(property_id)
        if override_type:
            if override_type == "damage_type":
                return [{"id": k, "label": v} for k, v in DAMAGE_TYPE_NAMES.items()]
            if override_type == "ability":
                return [{"id": k, "label": v} for k, v in ABILITY_NAMES.items()]
            if override_type == "ac_type":
                return [{"id": k, "label": v} for k, v in AC_MODIFIER_NAMES.items()]
            if override_type == "saving_throw":
                return [{"id": k, "label": v} for k, v in SAVING_THROW_NAMES.items()]
            if override_type == "immunity_misc":
                return [{"id": k, "label": v} for k, v in IMMUNITY_TYPE_NAMES.items()]

        if not self._itempropdef_loaded:
            self.load_itempropdef()

        if not self._itempropdef_loaded:
            return None

        prop_def = self._itempropdef.get(property_id)
        if not prop_def:
            return None

        subtype_resref = prop_def.get("SubTypeResRef")
        if not subtype_resref:
            return None

        subtype_lower = subtype_resref.lower()

        # Use hardcoded tables for known subtypes (more reliable than 2DA parsing)
        if subtype_lower in ["iprp_aligngrp", "iprp_alignmentgrp"]:
            return [{"id": k, "label": v} for k, v in ALIGNMENT_GROUP_NAMES.items()]
        if subtype_lower in ["iprp_alignment", "iprp_align"]:
            return [{"id": k, "label": v} for k, v in SPECIFIC_ALIGNMENT_NAMES.items()]
        if subtype_lower in ["iprp_abilities", "iprp_ability"]:
            return [{"id": k, "label": v} for k, v in ABILITY_NAMES.items()]
        if "damagetype" in subtype_lower or "dmgtype" in subtype_lower:
            return [{"id": k, "label": v} for k, v in DAMAGE_TYPE_NAMES.items()]
        if subtype_lower in ["iprp_immunity", "iprp_immuncost", "iprp_immunitymisc"]:
            return [{"id": k, "label": v} for k, v in IMMUNITY_TYPE_NAMES.items()]
        if "savingthrow" in subtype_lower or "saveelement" in subtype_lower or subtype_lower == "iprp_save":
            return [{"id": k, "label": v} for k, v in SAVING_THROW_NAMES.items()]
        if subtype_lower in ["iprp_acmodtype", "iprp_actype"]:
            return [{"id": k, "label": v} for k, v in AC_MODIFIER_NAMES.items()]

        # Try to load the subtype 2DA for other types
        subtype_2da = self._load_subtype_2da(subtype_resref)
        if not subtype_2da:
            return None

        # Build result from 2DA
        result = []
        is_spell_list = subtype_resref.lower() in ["iprp_spells", "spells"]

        for row_id, row_data in subtype_2da.items():
            label = self._get_label_from_2da_row(row_data)
            if label:
                # For spell lists, append caster level to distinguish duplicates
                if is_spell_list:
                    caster_lvl = row_data.get("CasterLvl") or row_data.get("InnateLvl")
                    if caster_lvl is not None:
                        label = f"{label} (CL {caster_lvl})"
                result.append({"id": row_id, "label": label})

        # Sort by ID for consistency
        result.sort(key=lambda x: x["id"])
        return result

    def get_property_cost_values(self, property_id: int) -> Optional[List[Dict[str, Any]]]:
        """Get list of valid cost values for a property type.

        Args:
            property_id: The property type ID

        Returns:
            List of {id, label} dicts, or None if no cost values
        """
        if not self._itempropdef_loaded:
            self.load_itempropdef()

        if not self._itempropdef_loaded:
            return None

        prop_def = self._itempropdef.get(property_id)
        if not prop_def:
            return None

        cost_table_ref = prop_def.get("CostTableResRef")
        if cost_table_ref is None or cost_table_ref == 0:
            return None

        # Handle simple bonus tables (+1, +2, etc.)
        if cost_table_ref in SIMPLE_BONUS_COST_TABLES:
            # Return typical range +1 to +20
            return [{"id": i, "label": f"+{i}"} for i in range(1, 21)]

        # Handle simple penalty tables (-1, -2, etc.)
        if cost_table_ref in SIMPLE_PENALTY_COST_TABLES:
            return [{"id": i, "label": f"-{i}"} for i in range(1, 11)]

        # Handle cast spell uses/charges (cost table 3)
        if cost_table_ref == CAST_SPELL_COST_TABLE:
            return [{"id": k, "label": v} for k, v in CAST_SPELL_USES.items()]

        # Try to load the cost table 2DA
        tda_name = COST_TABLE_2DA_MAP.get(cost_table_ref)
        if not tda_name:
            return None

        cost_2da = self._load_subtype_2da(tda_name)
        if not cost_2da:
            # Fall back to hardcoded tables
            if cost_table_ref == 7:  # iprp_resistcost
                return [{"id": k, "label": v} for k, v in RESIST_COST_VALUES.items()]
            if cost_table_ref == 6:  # iprp_soakcost
                return [{"id": k, "label": v} for k, v in SOAK_COST_VALUES.items()]
            return None

        # Build result from 2DA
        result = []
        is_percentage_table = tda_name.lower() in ["iprp_immuncost", "iprp_damvulcost"]

        for row_id, row_data in cost_2da.items():
            label = self._get_label_from_2da_row(row_data)
            if label:
                # Check if label is a decimal number (percentage value)
                if is_percentage_table:
                    try:
                        decimal_val = float(label)
                        if 0 < decimal_val < 1:
                            # Convert decimal to percentage (0.46 -> "46%")
                            label = f"{int(decimal_val * 100)}%"
                        elif decimal_val >= 1:
                            # Already a percentage number
                            label = f"{int(decimal_val)}%"
                    except ValueError:
                        # Not a number, keep the label as-is (e.g., "Random")
                        pass
                result.append({"id": row_id, "label": label})

        # Sort by ID for consistency
        result.sort(key=lambda x: x["id"])
        return result
