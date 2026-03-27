"""TLK string table service for resolving localized strings."""
import json
from pathlib import Path
from typing import Optional, Dict, Any


class TLKService:
    """Service for loading and querying TLK string tables."""

    # Custom TLK entries start at this offset
    CUSTOM_TLK_BASE = 16777216  # 0x1000000

    def __init__(self, base_tlk_path: Optional[Path] = None,
                 custom_tlk_path: Optional[Path] = None):
        """Initialize TLK service.

        Args:
            base_tlk_path: Path to base game TLK JSON file (dialog.tlk.json)
            custom_tlk_path: Path to custom TLK JSON file (dragonsneck.tlk.json)
        """
        self.base_tlk_path = base_tlk_path
        self.custom_tlk_path = custom_tlk_path

        # Caches for loaded TLK entries
        self._base_entries: Dict[int, str] = {}
        self._custom_entries: Dict[int, str] = {}
        self._loaded = False

    def load_tlk_files(self) -> bool:
        """Load TLK files into memory.

        Returns:
            True if at least one TLK file was loaded successfully.
        """
        loaded_any = False

        # Load base TLK
        if self.base_tlk_path and self.base_tlk_path.exists():
            try:
                self._base_entries = self._load_tlk_json(self.base_tlk_path)
                print(f"Loaded {len(self._base_entries)} base TLK entries")
                loaded_any = True
            except Exception as e:
                print(f"Failed to load base TLK: {e}")

        # Load custom TLK
        if self.custom_tlk_path and self.custom_tlk_path.exists():
            try:
                self._custom_entries = self._load_tlk_json(self.custom_tlk_path)
                print(f"Loaded {len(self._custom_entries)} custom TLK entries")
                loaded_any = True
            except Exception as e:
                print(f"Failed to load custom TLK: {e}")

        self._loaded = True
        return loaded_any

    def _load_tlk_json(self, path: Path) -> Dict[int, str]:
        """Load a TLK JSON file and return entries as dict.

        Args:
            path: Path to TLK JSON file

        Returns:
            Dict mapping strref ID to text
        """
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        entries = {}
        for entry in data.get("entries", []):
            entry_id = entry.get("id")
            text = entry.get("text", "")
            if entry_id is not None:
                entries[entry_id] = text

        return entries

    def get_string(self, strref: int) -> Optional[str]:
        """Get string by StrRef.

        Args:
            strref: String reference ID

        Returns:
            The string text, or None if not found
        """
        if not self._loaded:
            self.load_tlk_files()

        if strref < 0:
            return None

        # Check if this is a custom TLK reference
        if strref >= self.CUSTOM_TLK_BASE:
            custom_id = strref - self.CUSTOM_TLK_BASE
            return self._custom_entries.get(custom_id)
        else:
            return self._base_entries.get(strref)

    def resolve_localized_name(self, loc_data: Any) -> str:
        """Resolve a LocalizedName or similar field to a string.

        This handles the GFF CExoLocString format:
        {
            "type": "cexolocstring",
            "value": {
                "id": 12345,  # TLK reference
                "0": "English text"  # Embedded text (language 0 = English)
            }
        }

        Resolution priority:
        1. Embedded value.0 (English text if present)
        2. TLK id reference (custom if >= 16777216, else base)
        3. Any other embedded language value

        Args:
            loc_data: The LocalizedName field data from GFF

        Returns:
            Resolved string, or empty string if not found
        """
        if not loc_data:
            return ""

        # Handle dict format
        if isinstance(loc_data, dict):
            # Check for nested 'value' key (GFF format)
            value = loc_data.get("value", loc_data)

            if isinstance(value, dict):
                # Priority 1: Check for embedded English text (key "0")
                if "0" in value:
                    text = value["0"]
                    if text:
                        return str(text)

                # Priority 2: Check for TLK reference
                if "id" in value:
                    tlk_id = value["id"]
                    if isinstance(tlk_id, int) and tlk_id >= 0:
                        tlk_text = self.get_string(tlk_id)
                        if tlk_text:
                            return tlk_text

                # Priority 3: Any other embedded language value
                for key, text in value.items():
                    if key not in ("id", "type") and text:
                        return str(text)

            elif isinstance(value, str):
                return value

        elif isinstance(loc_data, str):
            return loc_data

        return ""

    def is_loaded(self) -> bool:
        """Check if TLK files have been loaded."""
        return self._loaded

    def get_entry_count(self) -> dict:
        """Get count of loaded entries.

        Returns:
            Dict with base and custom entry counts
        """
        return {
            "base": len(self._base_entries),
            "custom": len(self._custom_entries)
        }

    def search_entries(self, query: str, limit: int = 50) -> list:
        """Search for entries containing query text.

        Args:
            query: Text to search for (case-insensitive)
            limit: Maximum results to return

        Returns:
            List of matching entries with id, text, and source
        """
        if not self._loaded:
            self.load_tlk_files()

        results = []
        query_lower = query.lower()

        # Search base entries
        for entry_id, text in self._base_entries.items():
            if query_lower in text.lower():
                results.append({
                    "id": entry_id,
                    "strref": entry_id,
                    "text": text,
                    "source": "base"
                })
                if len(results) >= limit:
                    break

        # Search custom entries
        if len(results) < limit:
            for entry_id, text in self._custom_entries.items():
                if query_lower in text.lower():
                    results.append({
                        "id": entry_id,
                        "strref": entry_id + self.CUSTOM_TLK_BASE,
                        "text": text,
                        "source": "custom"
                    })
                    if len(results) >= limit:
                        break

        return results
