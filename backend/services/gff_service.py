"""GFF resource read/write service.

Delegates all storage I/O to an injected GFFStorageBackend while
providing domain-specific convenience methods and GFF data helpers.
"""
from pathlib import Path
from typing import Optional, List, Any

from services.storage_backend import GFFStorageBackend


class GFFService:
    """Service for reading and writing GFF resources.

    All file/storage I/O is delegated to the injected backend.
    Static helper methods for GFF dict manipulation are backend-agnostic.
    """

    def __init__(self, backend: GFFStorageBackend):
        self.backend = backend

    # ===== Item (UTI) Operations =====

    def list_item_resrefs(self) -> List[str]:
        """List all item resrefs."""
        return self.backend.list_resources("uti")

    def item_exists(self, resref: str) -> bool:
        """Check if an item exists."""
        return self.backend.resource_exists(resref, "uti")

    def get_item(self, resref: str) -> Optional[dict]:
        """Get a single item by resref."""
        return self.backend.read_resource(resref, "uti")

    def save_item(self, resref: str, data: dict) -> bool:
        """Save an item."""
        return self.backend.write_resource(resref, "uti", data)

    def get_item_modified(self, resref: str) -> str:
        """Get item modification indicator."""
        return self.backend.get_resource_modified(resref, "uti")

    def rename_item(self, old_resref: str, new_resref: str) -> bool:
        """Rename an item and update TemplateResRef inside.

        Args:
            old_resref: Current resref of the item
            new_resref: New resref for the item

        Returns:
            True if successful, False otherwise
        """
        if not self.backend.resource_exists(old_resref, "uti"):
            return False
        if self.backend.resource_exists(new_resref, "uti"):
            return False

        data = self.backend.read_resource(old_resref, "uti")
        if not data:
            return False

        self.set_value(data, "TemplateResRef", new_resref, "resref")

        if self.backend.write_resource(new_resref, "uti", data):
            self.backend.delete_resource(old_resref, "uti")
            return True
        return False

    def delete_item(self, resref: str) -> bool:
        """Delete an item."""
        return self.backend.delete_resource(resref, "uti")

    # ===== Creature (UTC) Operations =====

    def list_creature_resrefs(self) -> List[str]:
        """List all creature resrefs."""
        return self.backend.list_resources("utc")

    def creature_exists(self, resref: str) -> bool:
        """Check if a creature exists."""
        return self.backend.resource_exists(resref, "utc")

    def get_creature(self, resref: str) -> Optional[dict]:
        """Get a single creature by resref."""
        return self.backend.read_resource(resref, "utc")

    def save_creature(self, resref: str, data: dict) -> bool:
        """Save a creature."""
        return self.backend.write_resource(resref, "utc", data)

    def get_creature_modified(self, resref: str) -> str:
        """Get creature modification indicator."""
        return self.backend.get_resource_modified(resref, "utc")

    # ===== Store (UTM) Operations =====

    def list_store_resrefs(self) -> List[str]:
        """List all store resrefs."""
        return self.backend.list_resources("utm")

    def store_exists(self, resref: str) -> bool:
        """Check if a store exists."""
        return self.backend.resource_exists(resref, "utm")

    def get_store(self, resref: str) -> Optional[dict]:
        """Get a single store by resref."""
        return self.backend.read_resource(resref, "utm")

    def save_store(self, resref: str, data: dict) -> bool:
        """Save a store."""
        return self.backend.write_resource(resref, "utm", data)

    def get_store_modified(self, resref: str) -> str:
        """Get store modification indicator."""
        return self.backend.get_resource_modified(resref, "utm")

    # ===== Area (GIT/ARE) Operations =====

    def list_area_git_resrefs(self) -> List[str]:
        """List all area GIT resrefs (for area instances)."""
        return self.backend.list_resources("git")

    def list_area_are_resrefs(self) -> List[str]:
        """List all area ARE resrefs (for area metadata)."""
        return self.backend.list_resources("are")

    def get_area_git(self, resref: str) -> Optional[dict]:
        """Get area GIT data (instances)."""
        return self.backend.read_resource(resref, "git")

    def get_area_are(self, resref: str) -> Optional[dict]:
        """Get area ARE data (metadata)."""
        return self.backend.read_resource(resref, "are")

    def save_area_git(self, resref: str, data: dict) -> bool:
        """Save area GIT data."""
        return self.backend.write_resource(resref, "git", data)

    def get_area_modified(self, resref: str) -> str:
        """Get area modification indicator."""
        return self.backend.get_resource_modified(resref, "git")

    # ===== GFF Data Extraction Helpers =====

    @staticmethod
    def extract_locstring(data: dict, key: str) -> str:
        """Extract a localized string value, returning English or first available.

        Handles CExoLocString format which can contain:
        - Language strings keyed by language ID ("0" = English, "1" = French, etc.)
        - A StrRef ("id" key) pointing to a TLK string table entry
        - Both language strings and a StrRef

        Returns the string content or empty string if only a StrRef is present.
        """
        if key not in data:
            return ""

        loc_data = data[key]
        if isinstance(loc_data, dict):
            # Check for 'value' key first (CExoLocString format)
            if "value" in loc_data:
                value = loc_data["value"]
                if isinstance(value, dict):
                    # Try English (0) first, then any other language string
                    # Skip the "id" key which is a TLK StrRef, not a language string
                    if "0" in value:
                        return value["0"]
                    for k, v in value.items():
                        if k != "id" and isinstance(v, str):
                            return v
                    # Only StrRef present, no embedded strings
                    return ""
                return str(value) if value else ""
            # Direct language dict
            if "0" in loc_data:
                return loc_data["0"]
            for k, v in loc_data.items():
                if k != "id" and isinstance(v, str):
                    return v
            return ""
        return str(loc_data) if loc_data else ""

    @staticmethod
    def extract_value(data: dict, key: str, default: Any = None) -> Any:
        """Extract a value from GFF data, handling nested 'value' keys."""
        if key not in data:
            return default

        val = data[key]
        if isinstance(val, dict) and "value" in val:
            return val["value"]
        return val

    @staticmethod
    def set_value(data: dict, key: str, value: Any, value_type: str = None):
        """Set a value in GFF data, preserving structure."""
        if key in data and isinstance(data[key], dict) and "type" in data[key]:
            # Preserve existing type structure
            data[key]["value"] = value
        elif value_type:
            # Create new typed value
            data[key] = {"type": value_type, "value": value}
        else:
            # Simple value
            data[key] = value

    @staticmethod
    def extract_list(data: dict, key: str) -> List[dict]:
        """Extract a list from GFF data."""
        if key not in data:
            return []

        val = data[key]
        if isinstance(val, dict) and "value" in val:
            val = val["value"]

        if isinstance(val, list):
            return val
        return []

    @staticmethod
    def get_resref_from_path(file_path: Path) -> str:
        """Extract resref from a file path like 'item.uti.json' -> 'item'."""
        name = file_path.name
        # Remove all extensions
        parts = name.split('.')
        return parts[0] if parts else name

    @staticmethod
    def set_locstring(data: dict, key: str, text: str = None, string_ref: int = None):
        """Set a localized string value in GFF data.

        The StrRef "id" is stored inside the "value" dict, matching the
        current nwn_gff / gffjson.nim format.  When *text* or *string_ref*
        is ``None`` the corresponding part of the locstring is left
        unchanged (pass an empty string or ``-1`` to explicitly clear).

        Args:
            data: The GFF data dictionary to modify
            key: The key for the localized string (e.g., "LocalizedName")
            text: Text to set for language 0 (English). None leaves existing text unchanged.
            string_ref: TLK string reference ID. None leaves existing StrRef unchanged.
        """
        if key in data and isinstance(data[key], dict) and "type" in data[key]:
            # Preserve existing value dict so we don't lose entries
            existing_value = data[key].get("value", {})
            if not isinstance(existing_value, dict):
                existing_value = {}

            # Migrate any legacy outer-level "id" into the value dict
            if "id" in data[key]:
                if "id" not in existing_value:
                    existing_value["id"] = data[key]["id"]
                del data[key]["id"]

            if text is not None:
                existing_value["0"] = text
            if string_ref is not None:
                existing_value["id"] = string_ref

            data[key]["value"] = existing_value
        else:
            # Create new locstring — "id" goes inside "value"
            value_dict = {}
            if text is not None:
                value_dict["0"] = text
            if string_ref is not None:
                value_dict["id"] = string_ref
            data[key] = {"type": "cexolocstring", "value": value_dict}
