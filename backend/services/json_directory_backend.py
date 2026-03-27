"""JSON directory storage backend for GFF resources.

Implements GFFStorageBackend for the standard NWN module layout where
each resource is stored as a JSON file on disk:

    module_path/
      uti/<resref>.uti.json
      utc/<resref>.utc.json
      utm/<resref>.utm.json
      git/<resref>.git.json
      are/<resref>.are.json
      itp/<name>.itp.json
"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List


class HighPrecisionFloatEncoder(json.JSONEncoder):
    """JSON encoder that preserves float precision using repr()."""

    def encode(self, o):
        """Override encode to handle floats with full precision."""
        return self._encode_with_precision(o)

    def _encode_with_precision(self, o, indent_level=0):
        """Recursively encode with float precision preservation."""
        indent = "  "  # 2 spaces to match json.dump(indent=2)

        if isinstance(o, dict):
            if not o:
                return "{}"
            items = []
            for k, v in o.items():
                key_str = json.dumps(k)
                val_str = self._encode_with_precision(v, indent_level + 1)
                items.append(f"{indent * (indent_level + 1)}{key_str}: {val_str}")
            return "{\n" + ",\n".join(items) + "\n" + (indent * indent_level) + "}"

        elif isinstance(o, list):
            if not o:
                return "[]"
            items = []
            for item in o:
                val_str = self._encode_with_precision(item, indent_level + 1)
                items.append(f"{indent * (indent_level + 1)}{val_str}")
            return "[\n" + ",\n".join(items) + "\n" + (indent * indent_level) + "]"

        elif isinstance(o, float):
            return repr(o)

        elif isinstance(o, bool):
            return "true" if o else "false"

        elif isinstance(o, (int, str, type(None))):
            return json.dumps(o)

        else:
            return json.dumps(o)


class JsonDirectoryBackend:
    """GFFStorageBackend implementation backed by a directory of JSON files.

    Each resource type lives in its own subdirectory and each resource is
    stored as ``<resref>.<type>.json``.
    """

    def __init__(self, module_path: str):
        self.module_path = Path(module_path)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _resource_dir(self, resource_type: str) -> Path:
        """Get the subdirectory for a resource type."""
        return self.module_path / resource_type

    def _resource_path(self, resref: str, resource_type: str) -> Path:
        """Build the full file path for a resource."""
        return self._resource_dir(resource_type) / f"{resref}.{resource_type}.json"

    def _read_json(self, file_path: Path) -> Optional[dict]:
        """Read and parse a JSON file.

        Returns None for missing files (expected for base game items).
        Returns None for parse errors or permission errors (file in use).
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return None
        except json.JSONDecodeError as e:
            print(f"Error parsing {file_path}: {e}")
            return None
        except PermissionError as e:
            print(f"Permission error reading {file_path}: {e}")
            return None
        except OSError as e:
            print(f"OS error reading {file_path}: {e}")
            return None

    def _write_json(self, file_path: Path, data: dict) -> bool:
        """Write data to a JSON file with preserved float precision."""
        try:
            encoder = HighPrecisionFloatEncoder()
            content = encoder.encode(data)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        except Exception as e:
            print(f"Error writing {file_path}: {e}")
            return False

    def _get_file_modified(self, file_path: Path) -> str:
        """Get file modification time as ISO string, or empty string if missing."""
        try:
            mtime = os.path.getmtime(file_path)
            return datetime.fromtimestamp(mtime).isoformat()
        except OSError:
            return ""

    # ------------------------------------------------------------------
    # GFFStorageBackend protocol implementation
    # ------------------------------------------------------------------

    def list_resources(self, resource_type: str) -> List[str]:
        """List all resrefs of a given resource type."""
        res_dir = self._resource_dir(resource_type)
        if not res_dir.exists():
            return []

        suffix = f".{resource_type}.json"
        resrefs = []
        for file_path in res_dir.glob(f"*{suffix}"):
            # Strip the compound extension to get the resref
            name = file_path.name
            if name.endswith(suffix):
                resref = name[:-len(suffix)]
                if resref:
                    resrefs.append(resref)
        return resrefs

    def read_resource(self, resref: str, resource_type: str) -> Optional[dict]:
        """Read a resource and return its data as a dict."""
        file_path = self._resource_path(resref, resource_type)
        return self._read_json(file_path)

    def write_resource(self, resref: str, resource_type: str, data: dict) -> bool:
        """Write resource data to a JSON file."""
        file_path = self._resource_path(resref, resource_type)
        return self._write_json(file_path, data)

    def resource_exists(self, resref: str, resource_type: str) -> bool:
        """Check whether a resource file exists on disk."""
        file_path = self._resource_path(resref, resource_type)
        return file_path.exists()

    def delete_resource(self, resref: str, resource_type: str) -> bool:
        """Delete a resource file from disk."""
        file_path = self._resource_path(resref, resource_type)
        if file_path.exists():
            try:
                file_path.unlink()
                return True
            except OSError as e:
                print(f"Error deleting {file_path}: {e}")
                return False
        return False

    def rename_resource(self, old_resref: str, new_resref: str, resource_type: str) -> bool:
        """Rename a resource file on disk.

        Reads the old file, writes it to the new path, and deletes
        the old file. Does NOT modify the dict contents (e.g.,
        TemplateResRef) -- that is the caller's responsibility.
        """
        old_path = self._resource_path(old_resref, resource_type)
        new_path = self._resource_path(new_resref, resource_type)

        if not old_path.exists() or new_path.exists():
            return False

        data = self._read_json(old_path)
        if data is None:
            return False

        if not self._write_json(new_path, data):
            return False

        old_path.unlink()
        return True

    def get_resource_modified(self, resref: str, resource_type: str) -> str:
        """Get the file modification time as an ISO-format string."""
        file_path = self._resource_path(resref, resource_type)
        return self._get_file_modified(file_path)

    def get_mode(self) -> str:
        """Return the backend mode identifier."""
        return "json_directory"
