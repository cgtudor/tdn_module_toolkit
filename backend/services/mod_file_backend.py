"""MOD file storage backend for GFF resources.

Implements GFFStorageBackend for direct .mod file editing. Resources are
read from the ERF container on demand using the custom GFF/ERF parsers,
with an LRU cache for parsed dicts. Writes are held in memory until
an explicit save() call rebuilds the entire ERF atomically.
"""

import hashlib
import logging
import os
from collections import OrderedDict
from typing import Dict, List, Optional, Set, Tuple

from .erf_parser import (
    ErfFile,
    ErfError,
    extension_from_restype,
    extension_registered,
    restype_from_extension,
    write_erf,
)
from .gff_parser import GffParseError, read_gff, write_gff

logger = logging.getLogger(__name__)


class ModFileError(Exception):
    """Raised for MOD file backend errors."""


class ModFileBackend:
    """GFFStorageBackend implementation backed by a .mod (ERF) container.

    Resources are read lazily from the ERF file and parsed to dicts via
    ``gff_parser.read_gff``. Modifications are held in memory until
    ``save()`` is called, which rebuilds the entire ERF atomically.

    Usage::

        backend = ModFileBackend("/path/to/module.mod")
        backend.load()
        data = backend.read_resource("apple", "uti")
        backend.write_resource("apple", "uti", modified_data)
        backend.save()
        backend.close()
    """

    def __init__(self, mod_file_path: str, cache_size: int = 500):
        """Create a new ModFileBackend.

        Args:
            mod_file_path: Path to the .mod file.
            cache_size: Maximum number of parsed GFF dicts to cache.
        """
        self._mod_path: str = mod_file_path
        self._cache_size: int = cache_size

        # Opened ERF handle (set by load())
        self._erf: Optional[ErfFile] = None
        # File mtime at load time (for external modification detection)
        self._load_mtime: float = 0.0

        # LRU cache: (resref_lower, restype) -> parsed dict
        self._cache: OrderedDict[Tuple[str, int], dict] = OrderedDict()

        # In-memory modifications (not yet saved to disk)
        self._dirty: Dict[Tuple[str, int], dict] = {}
        # Resources marked for deletion
        self._deleted: Set[Tuple[str, int]] = set()
        # Newly created resources (not in the original ERF)
        self._added: Dict[Tuple[str, int], dict] = {}

        # Version counters for change detection (get_resource_modified)
        self._version_counters: Dict[Tuple[str, int], int] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Open the .mod file and parse its resource index.

        Raises:
            ModFileError: If the file cannot be opened.
            FileNotFoundError: If the file does not exist.
        """
        if self._erf is not None:
            self.close()

        # Warn about stale temp/backup files from interrupted saves
        tmp_path = self._mod_path + ".tmp"
        if os.path.exists(tmp_path):
            logger.warning(
                "Found stale temp file from interrupted save: %s "
                "(you may want to inspect or delete it)",
                tmp_path,
            )

        try:
            self._erf = ErfFile(self._mod_path)
        except (ErfError, FileNotFoundError, OSError) as e:
            raise ModFileError(f"Failed to open MOD file: {e}") from e

        self._load_mtime = os.path.getmtime(self._mod_path)
        self._cache.clear()
        self._dirty.clear()
        self._deleted.clear()
        self._added.clear()
        self._version_counters.clear()

    def close(self) -> None:
        """Close the ERF file handle and clear all state.

        Any unsaved changes are discarded. Call save() first if needed.
        """
        if self.has_unsaved_changes:
            logger.warning(
                "Closing ModFileBackend with %d unsaved changes "
                "(changes will be discarded)",
                self.dirty_count,
            )
        if self._erf is not None:
            self._erf.close()
            self._erf = None
        self._cache.clear()
        self._dirty.clear()
        self._deleted.clear()
        self._added.clear()
        self._version_counters.clear()

    @property
    def is_loaded(self) -> bool:
        """True if the .mod file is open and ready."""
        return self._erf is not None

    # ------------------------------------------------------------------
    # Key helpers
    # ------------------------------------------------------------------

    def _make_key(
        self, resref: str, resource_type: str
    ) -> Optional[Tuple[str, int]]:
        """Build an internal key from resref and resource_type string.

        Returns None if the resource_type extension is not recognised.
        """
        try:
            restype = restype_from_extension(resource_type)
        except KeyError:
            return None
        return (resref.lower(), restype)

    def _ensure_loaded(self) -> None:
        """Raise if the backend is not loaded."""
        if self._erf is None:
            raise ModFileError("ModFileBackend is not loaded. Call load() first.")

    def _effective_exists(self, key: Tuple[str, int]) -> bool:
        """Check if a resource effectively exists (considering pending changes)."""
        if key in self._deleted:
            return False
        if key in self._dirty or key in self._added:
            return True
        return self._erf.resource_exists(key[0], key[1])

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    def _cache_get(self, key: Tuple[str, int]) -> Optional[dict]:
        """Get from cache, returning None on miss. Moves to end on hit."""
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def _cache_put(self, key: Tuple[str, int], data: dict) -> None:
        """Put into cache, evicting the oldest entry if over capacity."""
        self._cache[key] = data
        self._cache.move_to_end(key)
        while len(self._cache) > self._cache_size:
            self._cache.popitem(last=False)

    def _cache_remove(self, key: Tuple[str, int]) -> None:
        """Remove from cache if present."""
        self._cache.pop(key, None)

    # ------------------------------------------------------------------
    # GFFStorageBackend protocol implementation
    # ------------------------------------------------------------------

    def list_resources(self, resource_type: str) -> List[str]:
        """List all resrefs of a given resource type."""
        self._ensure_loaded()

        key_check = self._make_key("_dummy", resource_type)
        if key_check is None:
            return []
        restype = key_check[1]

        # Start with resources from the ERF
        resrefs: Set[str] = set()
        for rr, rt in self._erf.list_resources(type_filter=restype):
            k = (rr.lower(), rt)
            if k not in self._deleted:
                resrefs.add(rr.lower())

        # Add dirty resources of this type (may overlap with ERF)
        for (rr, rt) in self._dirty:
            if rt == restype and (rr, rt) not in self._deleted:
                resrefs.add(rr)

        # Add newly added resources of this type
        for (rr, rt) in self._added:
            if rt == restype:
                resrefs.add(rr)

        return sorted(resrefs)

    def read_resource(
        self, resref: str, resource_type: str
    ) -> Optional[dict]:
        """Read a resource and return its data as a dict."""
        self._ensure_loaded()

        key = self._make_key(resref, resource_type)
        if key is None:
            return None

        # Deleted?
        if key in self._deleted:
            return None

        # Dirty (modified)?
        if key in self._dirty:
            return self._dirty[key]

        # Newly added?
        if key in self._added:
            return self._added[key]

        # Cached?
        cached = self._cache_get(key)
        if cached is not None:
            return cached

        # Read from ERF
        raw = self._erf.read_resource(key[0], key[1])
        if raw is None:
            return None

        try:
            parsed = read_gff(raw)
        except GffParseError as e:
            logger.error(
                "Failed to parse GFF for %s.%s: %s",
                resref, resource_type, e,
            )
            return None

        self._cache_put(key, parsed)
        return parsed

    def write_resource(
        self, resref: str, resource_type: str, data: dict
    ) -> bool:
        """Write resource data (held in memory until save())."""
        self._ensure_loaded()

        key = self._make_key(resref, resource_type)
        if key is None:
            return False

        # Remove from deleted if it was previously deleted
        self._deleted.discard(key)

        # Determine if this is a new resource or modification of existing
        exists_in_erf = self._erf.resource_exists(key[0], key[1])
        if exists_in_erf or key in self._dirty:
            self._dirty[key] = data
            # If it was in _added, move to _dirty (it now exists logically)
            self._added.pop(key, None)
        elif key in self._added:
            self._added[key] = data
        else:
            # Brand new resource
            self._added[key] = data

        # Invalidate cache
        self._cache_remove(key)

        # Bump version counter
        self._version_counters[key] = self._version_counters.get(key, 0) + 1

        return True

    def resource_exists(self, resref: str, resource_type: str) -> bool:
        """Check whether a resource exists."""
        self._ensure_loaded()

        key = self._make_key(resref, resource_type)
        if key is None:
            return False

        return self._effective_exists(key)

    def delete_resource(self, resref: str, resource_type: str) -> bool:
        """Delete a resource (takes effect on save())."""
        self._ensure_loaded()

        key = self._make_key(resref, resource_type)
        if key is None:
            return False

        if not self._effective_exists(key):
            return False

        # If it was only in _added, just remove it
        if key in self._added:
            del self._added[key]
            # Don't add to _deleted since it never existed in the ERF
            self._cache_remove(key)
            return True

        # Mark for deletion from the ERF
        self._deleted.add(key)
        self._dirty.pop(key, None)
        self._cache_remove(key)

        return True

    def rename_resource(
        self, old_resref: str, new_resref: str, resource_type: str
    ) -> bool:
        """Rename a resource (storage-level only, does not update dict contents)."""
        self._ensure_loaded()

        old_key = self._make_key(old_resref, resource_type)
        new_key = self._make_key(new_resref, resource_type)
        if old_key is None or new_key is None:
            return False

        # Old must exist, new must not
        if not self._effective_exists(old_key):
            return False
        if self._effective_exists(new_key):
            return False

        # Read the data from wherever it currently lives
        data = self.read_resource(old_resref, resource_type)
        if data is None:
            return False

        # Was old in _added (never in ERF)?
        was_added = old_key in self._added

        # Delete old
        if was_added:
            del self._added[old_key]
        else:
            self._deleted.add(old_key)
            self._dirty.pop(old_key, None)
        self._cache_remove(old_key)

        # Add new
        if was_added:
            self._added[new_key] = data
        else:
            self._dirty[new_key] = data

        # Bump version counter for new key
        self._version_counters[new_key] = (
            self._version_counters.get(new_key, 0) + 1
        )

        return True

    def get_resource_modified(self, resref: str, resource_type: str) -> str:
        """Get a modification indicator for change detection.

        Returns a string version counter. Incremented on each write.
        For unmodified resources, returns "0".
        """
        self._ensure_loaded()

        key = self._make_key(resref, resource_type)
        if key is None:
            return ""

        if not self._effective_exists(key):
            return ""

        counter = self._version_counters.get(key, 0)
        return str(counter)

    def get_mode(self) -> str:
        """Return the backend mode identifier."""
        return "mod_file"

    # ------------------------------------------------------------------
    # Raw read / hash helpers (MOD-specific, not part of the protocol)
    # ------------------------------------------------------------------

    def read_resource_raw(
        self, resref: str, resource_type: str
    ) -> Optional[bytes]:
        """Read raw GFF bytes for a resource WITHOUT parsing.

        For dirty/added resources, serialises the in-memory dict back to
        GFF binary via ``write_gff()``. For clean ERF resources, reads
        the raw bytes directly from the container.

        Args:
            resref: Resource reference name.
            resource_type: Resource type extension (e.g. ``"uti"``).

        Returns:
            Raw bytes, or ``None`` if the resource does not exist.
        """
        self._ensure_loaded()

        key = self._make_key(resref, resource_type)
        if key is None:
            return None

        if key in self._deleted:
            return None

        # Dirty (modified) -- serialise from in-memory dict
        if key in self._dirty:
            try:
                return write_gff(self._dirty[key])
            except GffParseError as e:
                logger.error(
                    "Failed to serialise dirty resource %s.%s: %s",
                    resref, resource_type, e,
                )
                return None

        # Newly added -- serialise from in-memory dict
        if key in self._added:
            try:
                return write_gff(self._added[key])
            except GffParseError as e:
                logger.error(
                    "Failed to serialise added resource %s.%s: %s",
                    resref, resource_type, e,
                )
                return None

        # Clean ERF resource -- read raw bytes directly
        return self._erf.read_resource(key[0], key[1])

    def get_resource_hash(
        self, resref: str, resource_type: str
    ) -> Optional[str]:
        """Compute an MD5 hex digest for a resource's raw GFF bytes.

        Args:
            resref: Resource reference name.
            resource_type: Resource type extension.

        Returns:
            Hex digest string, or ``None`` if the resource does not exist.
        """
        raw = self.read_resource_raw(resref, resource_type)
        if raw is None:
            return None
        return hashlib.md5(raw).hexdigest()

    # ------------------------------------------------------------------
    # Dirty tracking
    # ------------------------------------------------------------------

    @property
    def has_unsaved_changes(self) -> bool:
        """True if there are any pending modifications."""
        return bool(self._dirty) or bool(self._deleted) or bool(self._added)

    @property
    def dirty_count(self) -> int:
        """Number of pending changes (modified + deleted + added)."""
        return len(self._dirty) + len(self._deleted) + len(self._added)

    @property
    def dirty_resources(self) -> List[Tuple[str, str]]:
        """List of (resref, resource_type) for all pending changes."""
        result = []
        for rr, rt in self._dirty:
            try:
                ext = extension_from_restype(rt)
                result.append((rr, ext))
            except KeyError:
                result.append((rr, str(rt)))

        for rr, rt in self._deleted:
            try:
                ext = extension_from_restype(rt)
                result.append((rr, ext))
            except KeyError:
                result.append((rr, str(rt)))

        for rr, rt in self._added:
            try:
                ext = extension_from_restype(rt)
                result.append((rr, ext))
            except KeyError:
                result.append((rr, str(rt)))

        return result

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def save(self) -> None:
        """Write all pending changes back to the .mod file.

        Rebuilds the entire ERF with modified, added, and unmodified
        resources. Deleted resources are omitted. The write is atomic
        (temp file + rename with backup).

        Raises:
            ModFileError: If the file was modified externally since load,
                or if the write fails.
        """
        self._ensure_loaded()

        if not self.has_unsaved_changes:
            return

        # Check for external modification
        try:
            current_mtime = os.path.getmtime(self._mod_path)
        except OSError as e:
            raise ModFileError(
                f"Cannot stat MOD file for modification check: {e}"
            ) from e

        if current_mtime != self._load_mtime:
            raise ModFileError(
                "MOD file was modified externally since it was loaded. "
                "Reload the file before saving to avoid data loss. "
                f"(loaded mtime: {self._load_mtime}, "
                f"current mtime: {current_mtime})"
            )

        # Collect all resources for the new ERF
        resources: Dict[Tuple[str, int], bytes] = {}

        # 1. Unmodified resources from the original ERF
        for resref, restype in self._erf.list_resources():
            key = (resref.lower(), restype)
            if key in self._deleted:
                continue
            if key in self._dirty:
                continue  # Will be handled below

            raw = self._erf.read_resource(resref, restype)
            if raw is not None:
                resources[(resref.lower(), restype)] = raw

        # 2. Dirty (modified) resources -> convert dict to GFF binary
        for key, data in self._dirty.items():
            try:
                binary = write_gff(data)
                resources[key] = binary
            except GffParseError as e:
                raise ModFileError(
                    f"Failed to convert {key[0]} to GFF binary: {e}"
                ) from e

        # 3. Added (new) resources -> convert dict to GFF binary
        for key, data in self._added.items():
            try:
                binary = write_gff(data)
                resources[key] = binary
            except GffParseError as e:
                raise ModFileError(
                    f"Failed to convert {key[0]} to GFF binary: {e}"
                ) from e

        # Close the old ERF handle before writing
        file_type = self._erf.file_type
        self._erf.close()
        self._erf = None

        # Write the new ERF (atomic: .tmp + rename with .bak)
        try:
            write_erf(self._mod_path, resources, file_type)
        except ErfError as e:
            # Try to reopen the original (or backup) for continued use
            try:
                self._erf = ErfFile(self._mod_path)
                self._load_mtime = os.path.getmtime(self._mod_path)
            except Exception as reopen_err:
                logger.error(
                    "Failed to reopen MOD file after write failure: %s. "
                    "Backend is now in an unrecoverable state. "
                    "Call load() to re-read the file.",
                    reopen_err,
                )
            raise ModFileError(f"Failed to write MOD file: {e}") from e

        # Reopen the newly written file
        try:
            self._erf = ErfFile(self._mod_path)
        except (ErfError, OSError) as e:
            raise ModFileError(
                f"Failed to reopen MOD file after save: {e}"
            ) from e

        self._load_mtime = os.path.getmtime(self._mod_path)

        # Clear all pending state
        self._dirty.clear()
        self._deleted.clear()
        self._added.clear()
        self._cache.clear()
        # Keep version counters (they're still valid for change detection)
