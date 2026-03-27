"""Palette management service for item palette (ITP) files."""
from typing import Optional, List, Tuple

PALETTE_RESREF = "itempalcus"
PALETTE_TYPE = "itp"


class PaletteService:
    """Service for managing item palette (ITP) files.

    All I/O is routed through a GFFStorageBackend, so this works for
    both JSON directory mode and MOD file mode.
    """

    def __init__(self, backend):
        self._backend = backend

    def _load_palette(self) -> Optional[dict]:
        """Load the palette data."""
        return self._backend.read_resource(PALETTE_RESREF, PALETTE_TYPE)

    def _save_palette(self, data: dict) -> bool:
        """Save the palette data."""
        return self._backend.write_resource(PALETTE_RESREF, PALETTE_TYPE, data)

    def palette_exists(self) -> bool:
        """Check if the item palette file exists."""
        return self._backend.resource_exists(PALETTE_RESREF, PALETTE_TYPE)

    def get_categories(self) -> List[dict]:
        """Get list of palette categories.

        Returns:
            List of category dicts with 'id', 'strref', and 'name' keys
        """
        palette = self._load_palette()
        if not palette:
            return []

        categories = []
        main_list = palette.get("MAIN", {}).get("value", [])
        if not main_list:
            return []

        cat_list = main_list[0].get("LIST", {}).get("value", [])
        for cat in cat_list:
            cat_id = cat.get("ID", {}).get("value", 0)
            strref = cat.get("STRREF", {}).get("value", 0)
            name = cat.get("NAME", {}).get("value", f"Category {cat_id}")
            categories.append({
                "id": cat_id,
                "strref": strref,
                "name": name
            })
        return categories

    def find_item(self, resref: str) -> Optional[Tuple[int, int, dict]]:
        """Find item in palette.

        Args:
            resref: The item's resref to find

        Returns:
            Tuple of (category_idx, item_idx, entry) or None if not found
        """
        palette = self._load_palette()
        if not palette:
            return None

        main_list = palette.get("MAIN", {}).get("value", [])
        if not main_list:
            return None

        cat_list = main_list[0].get("LIST", {}).get("value", [])
        for cat_idx, cat in enumerate(cat_list):
            items = cat.get("LIST", {}).get("value", [])
            for item_idx, item in enumerate(items):
                item_resref = item.get("RESREF", {}).get("value", "")
                if item_resref == resref:
                    return (cat_idx, item_idx, item)
        return None

    def update_item_name(self, resref: str, name: str) -> bool:
        """Update item's NAME in palette.

        Args:
            resref: The item's resref
            name: New name to set

        Returns:
            True if successful, False otherwise
        """
        palette = self._load_palette()
        if not palette:
            return False

        found = self.find_item(resref)
        if not found:
            return False

        cat_idx, item_idx, _ = found
        main_list = palette["MAIN"]["value"]
        cat_list = main_list[0]["LIST"]["value"]
        cat_list[cat_idx]["LIST"]["value"][item_idx]["NAME"] = {
            "type": "cexostring", "value": name
        }
        return self._save_palette(palette)

    def update_item_resref(self, old_resref: str, new_resref: str) -> bool:
        """Update item's RESREF in palette.

        Args:
            old_resref: Current resref of the item
            new_resref: New resref to set

        Returns:
            True if successful, False otherwise
        """
        palette = self._load_palette()
        if not palette:
            return False

        found = self.find_item(old_resref)
        if not found:
            return False

        cat_idx, item_idx, _ = found
        main_list = palette["MAIN"]["value"]
        cat_list = main_list[0]["LIST"]["value"]
        cat_list[cat_idx]["LIST"]["value"][item_idx]["RESREF"] = {
            "type": "resref", "value": new_resref
        }
        return self._save_palette(palette)

    def move_item_to_category(self, resref: str, target_category_id: int) -> bool:
        """Move item to a different palette category.

        Args:
            resref: The item's resref
            target_category_id: ID of the target category

        Returns:
            True if successful, False otherwise
        """
        palette = self._load_palette()
        if not palette:
            return False

        found = self.find_item(resref)
        if not found:
            return False

        src_cat_idx, item_idx, entry = found
        main_list = palette["MAIN"]["value"]
        cat_list = main_list[0]["LIST"]["value"]

        # Find target category
        target_cat_idx = None
        for idx, cat in enumerate(cat_list):
            if cat.get("ID", {}).get("value") == target_category_id:
                target_cat_idx = idx
                break

        if target_cat_idx is None or target_cat_idx == src_cat_idx:
            return False

        # Remove from source
        cat_list[src_cat_idx]["LIST"]["value"].pop(item_idx)

        # Add to target
        if "LIST" not in cat_list[target_cat_idx]:
            cat_list[target_cat_idx]["LIST"] = {"type": "list", "value": []}
        cat_list[target_cat_idx]["LIST"]["value"].append(entry)

        return self._save_palette(palette)

    def remove_item(self, resref: str) -> bool:
        """Remove an item from the palette.

        Args:
            resref: The item's resref to remove

        Returns:
            True if successful, False otherwise
        """
        palette = self._load_palette()
        if not palette:
            return False

        found = self.find_item(resref)
        if not found:
            return False

        cat_idx, item_idx, _ = found
        main_list = palette["MAIN"]["value"]
        cat_list = main_list[0]["LIST"]["value"]
        cat_list[cat_idx]["LIST"]["value"].pop(item_idx)

        return self._save_palette(palette)
