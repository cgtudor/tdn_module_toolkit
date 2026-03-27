"""ERF container reader/writer for Neverwinter Nights .mod/.erf/.hak files.

Supports ERF V1.0 format (standard for NWN:EE). Detects and raises a clear
error for E1.0 (enhanced/compressed) format.

No external dependencies beyond the Python standard library.

Reference implementations:
- neverwinter.nim/neverwinter/erf.nim
- neverwinter.nim/neverwinter/restype.nim
- neverwinter.nim/neverwinter/resref.nim
"""

import hashlib
import struct
import os
from typing import Dict, List, Tuple, Optional

# ---------------------------------------------------------------------------
#  ResType Registry  (from neverwinter.nim/neverwinter/restype.nim)
# ---------------------------------------------------------------------------

_RESTYPE_TO_EXT: Dict[int, str] = {
    0: "res", 1: "bmp", 2: "mve", 3: "tga", 4: "wav",
    5: "wfx", 6: "plt", 7: "ini", 8: "bmu", 9: "mpg",
    10: "txt",
    2000: "plh", 2001: "tex", 2002: "mdl", 2003: "thg",
    2005: "fnt", 2007: "lua", 2008: "slt", 2009: "nss",
    2010: "ncs", 2011: "mod", 2012: "are", 2013: "set",
    2014: "ifo", 2015: "bic", 2016: "wok", 2017: "2da",
    2018: "tlk", 2022: "txi", 2023: "git", 2024: "bti",
    2025: "uti", 2026: "btc", 2027: "utc", 2029: "dlg",
    2030: "itp", 2031: "btt", 2032: "utt", 2033: "dds",
    2034: "bts", 2035: "uts", 2036: "ltr", 2037: "gff",
    2038: "fac", 2039: "bte", 2040: "ute", 2041: "btd",
    2042: "utd", 2043: "btp", 2044: "utp", 2045: "dft",
    2046: "gic", 2047: "gui", 2048: "css", 2049: "ccs",
    2050: "btm", 2051: "utm", 2052: "dwk", 2053: "pwk",
    2054: "btg", 2055: "utg", 2056: "jrl", 2057: "sav",
    2058: "utw", 2059: "4pc", 2060: "ssf", 2061: "hak",
    2062: "nwm", 2063: "bik", 2064: "ndb", 2065: "ptm",
    2066: "ptt", 2067: "bak", 2068: "dat", 2069: "shd",
    2070: "xbc", 2071: "wbm", 2072: "mtr", 2073: "ktx",
    2074: "ttf", 2075: "sql", 2076: "tml", 2077: "sq3",
    2078: "lod", 2079: "gif", 2080: "png", 2081: "jpg",
    2082: "caf", 2083: "jui",
    9996: "ids", 9997: "erf", 9998: "bif", 9999: "key",
}

_EXT_TO_RESTYPE: Dict[str, int] = {v: k for k, v in _RESTYPE_TO_EXT.items()}

# Valid ERF file type identifiers
_VALID_ERF_TYPES = frozenset({"NWM ", "MOD ", "ERF ", "HAK "})

# ERF header is always 160 bytes
ERF_HEADER_SIZE = 160

# Key list entry sizes
ERF_V1_KEY_SIZE = 24     # 16 resref + 4 id + 2 restype + 2 unused
ERF_V1_RES_SIZE = 8      # 4 offset + 4 size


# ---------------------------------------------------------------------------
#  Public ResType helpers
# ---------------------------------------------------------------------------

def restype_from_extension(ext: str) -> int:
    """Convert a file extension to a numeric ResType ID.

    Args:
        ext: File extension without dot (e.g. ``"uti"``, ``"utc"``).

    Returns:
        The numeric ResType ID.

    Raises:
        KeyError: If the extension is not registered.
    """
    return _EXT_TO_RESTYPE[ext.lower()]


def extension_from_restype(restype: int) -> str:
    """Convert a numeric ResType ID to a file extension.

    Args:
        restype: Numeric ResType ID (e.g. 2025 for UTI).

    Returns:
        The file extension string (e.g. ``"uti"``).

    Raises:
        KeyError: If the ResType ID is not registered.
    """
    return _RESTYPE_TO_EXT[restype]


def restype_registered(restype: int) -> bool:
    """Check if a ResType ID is known."""
    return restype in _RESTYPE_TO_EXT


def extension_registered(ext: str) -> bool:
    """Check if a file extension is known."""
    return ext.lower() in _EXT_TO_RESTYPE


# ---------------------------------------------------------------------------
#  Exceptions
# ---------------------------------------------------------------------------

class ErfError(Exception):
    """Raised when an ERF file cannot be read or written."""


# ---------------------------------------------------------------------------
#  ErfFile  -  read-only ERF container with lazy resource access
# ---------------------------------------------------------------------------

class ErfFile:
    """Read-only ERF container (.mod, .erf, .hak).

    Parses the header and resource index on open, then provides
    random-access reads of individual resources by seeking.

    Usage::

        with ErfFile("module.mod") as erf:
            resources = erf.list_resources()
            data = erf.read_resource("creature01", 2027)
    """

    def __init__(self, file_path: str):
        """Open an ERF file and parse its header and resource index.

        Args:
            file_path: Path to the ERF file.

        Raises:
            ErfError: If the file cannot be opened or parsed.
            FileNotFoundError: If the file does not exist.
        """
        self.file_path = file_path
        self._file = None
        self._entries: Dict[Tuple[str, int], Tuple[int, int]] = {}
        # Preserve original case for listing
        self._original_resrefs: Dict[Tuple[str, int], str] = {}
        self.file_type: str = ""
        self.file_version: str = ""
        self.entry_count: int = 0
        self.build_year: int = 0
        self.build_day: int = 0

        self._open_and_parse()

    def _open_and_parse(self):
        """Open the file and parse header + index."""
        self._file = open(self.file_path, "rb")
        try:
            self._parse_header()
            self._parse_index()
        except Exception:
            self._file.close()
            self._file = None
            raise

    def _parse_header(self):
        """Parse the 160-byte ERF header."""
        header_data = self._file.read(ERF_HEADER_SIZE)
        if len(header_data) < ERF_HEADER_SIZE:
            raise ErfError(
                f"File too short for ERF header: {len(header_data)} bytes "
                f"(need {ERF_HEADER_SIZE})"
            )

        self.file_type = header_data[0:4].decode("ascii")
        version_str = header_data[4:8].decode("ascii")

        if version_str == "E1.0":
            raise ErfError(
                "ERF E1.0 (enhanced/compressed) format is not supported. "
                "Only V1.0 format is supported. Convert the file with "
                "nwn_erf if needed."
            )
        if version_str != "V1.0":
            raise ErfError(f"Unsupported ERF version: {version_str!r}")

        self.file_version = version_str

        (
            loc_str_count,
            loc_str_size,
            entry_count,
            offset_to_loc_str,
            offset_to_key_list,
            offset_to_res_list,
            build_year,
            build_day,
            str_ref,
        ) = struct.unpack_from("<9i", header_data, 8)

        self.entry_count = entry_count
        self.build_year = build_year
        self.build_day = build_day
        self._offset_to_key_list = offset_to_key_list
        self._offset_to_res_list = offset_to_res_list

    def _parse_index(self):
        """Parse key list and resource list to build the resource index."""
        # Read resource list first (offsets and sizes)
        self._file.seek(self._offset_to_res_list)
        res_data = self._file.read(self.entry_count * ERF_V1_RES_SIZE)
        if len(res_data) < self.entry_count * ERF_V1_RES_SIZE:
            raise ErfError("Truncated resource list in ERF file")

        res_entries: List[Tuple[int, int]] = []
        for i in range(self.entry_count):
            offset, size = struct.unpack_from(
                "<II", res_data, i * ERF_V1_RES_SIZE
            )
            res_entries.append((offset, size))

        # Read key list (resref + id + restype)
        self._file.seek(self._offset_to_key_list)
        key_data = self._file.read(self.entry_count * ERF_V1_KEY_SIZE)
        if len(key_data) < self.entry_count * ERF_V1_KEY_SIZE:
            raise ErfError("Truncated key list in ERF file")

        for i in range(self.entry_count):
            base = i * ERF_V1_KEY_SIZE
            resref_raw = key_data[base:base + 16]
            resref = resref_raw.split(b"\x00", 1)[0].decode("ascii").strip()
            # Skip 4 bytes (resource ID)
            restype = struct.unpack_from("<H", key_data, base + 20)[0]
            # Skip 2 bytes unused

            # Skip invalid restypes (65535 = 0xFFFF)
            if restype == 65535:
                continue

            if not resref:
                continue

            key = (resref.lower(), restype)

            # Handle duplicates: skip if same data, warn if different
            if key in self._entries:
                existing = self._entries[key]
                if existing == res_entries[i]:
                    continue
                # Different data for same resref - keep the first one
                continue

            self._entries[key] = res_entries[i]
            self._original_resrefs[key] = resref

    def list_resources(
        self, type_filter: Optional[int] = None
    ) -> List[Tuple[str, int]]:
        """List all resources in the ERF.

        Args:
            type_filter: If provided, only return resources of this ResType.

        Returns:
            List of (resref, restype) tuples. ResRefs are in their original
            case as stored in the ERF.
        """
        result = []
        for (resref_lower, restype), _ in self._entries.items():
            if type_filter is not None and restype != type_filter:
                continue
            original = self._original_resrefs.get(
                (resref_lower, restype), resref_lower
            )
            result.append((original, restype))
        return result

    def read_resource(
        self, resref: str, restype: int
    ) -> Optional[bytes]:
        """Read raw bytes of a resource.

        Args:
            resref: Resource reference name (case-insensitive).
            restype: Numeric ResType ID.

        Returns:
            Raw bytes of the resource, or None if not found.
        """
        if self._file is None:
            raise ErfError("ERF file is closed")

        key = (resref.lower(), restype)
        entry = self._entries.get(key)
        if entry is None:
            return None

        offset, size = entry
        self._file.seek(offset)
        data = self._file.read(size)
        if len(data) < size:
            raise ErfError(
                f"Truncated resource data for {resref}.{restype}: "
                f"expected {size} bytes, got {len(data)}"
            )
        return data

    def resource_exists(self, resref: str, restype: int) -> bool:
        """Check if a resource exists in the ERF.

        Args:
            resref: Resource reference name (case-insensitive).
            restype: Numeric ResType ID.

        Returns:
            True if the resource exists.
        """
        return (resref.lower(), restype) in self._entries

    def bulk_hash_by_type(self, restype: int) -> Dict[str, str]:
        """Compute MD5 hashes for all resources of a given type.

        Entries are sorted by file offset so that reads are sequential,
        minimising disk seeks for large ERF files.

        Args:
            restype: Numeric ResType ID to filter on.

        Returns:
            Dict mapping lowercase resref to hex MD5 digest.

        Raises:
            ErfError: If the file handle is closed.
        """
        if self._file is None:
            raise ErfError("ERF file is closed")

        # Collect entries of the requested type
        entries: List[Tuple[str, int, int]] = []  # (resref, offset, size)
        for (resref_lower, rt), (offset, size) in self._entries.items():
            if rt == restype:
                entries.append((resref_lower, offset, size))

        # Sort by file offset for sequential I/O
        entries.sort(key=lambda e: e[1])

        result: Dict[str, str] = {}
        for resref_lower, offset, size in entries:
            self._file.seek(offset)
            data = self._file.read(size)
            if len(data) < size:
                raise ErfError(
                    f"Truncated resource data for {resref_lower}.{restype}: "
                    f"expected {size} bytes, got {len(data)}"
                )
            result[resref_lower] = hashlib.md5(data).hexdigest()

        return result

    def bulk_read_by_type(self, restype: int) -> Dict[str, bytes]:
        """Read raw bytes for all resources of a given type.

        Entries are sorted by file offset so that reads are sequential,
        minimising disk seeks for large ERF files.

        Args:
            restype: Numeric ResType ID to filter on.

        Returns:
            Dict mapping lowercase resref to raw bytes.

        Raises:
            ErfError: If the file handle is closed or data is truncated.
        """
        if self._file is None:
            raise ErfError("ERF file is closed")

        # Collect entries of the requested type
        entries: List[Tuple[str, int, int]] = []  # (resref, offset, size)
        for (resref_lower, rt), (offset, size) in self._entries.items():
            if rt == restype:
                entries.append((resref_lower, offset, size))

        # Sort by file offset for sequential I/O
        entries.sort(key=lambda e: e[1])

        result: Dict[str, bytes] = {}
        for resref_lower, offset, size in entries:
            self._file.seek(offset)
            data = self._file.read(size)
            if len(data) < size:
                raise ErfError(
                    f"Truncated resource data for {resref_lower}.{restype}: "
                    f"expected {size} bytes, got {len(data)}"
                )
            result[resref_lower] = data

        return result

    @property
    def resource_count(self) -> int:
        """Number of valid resources in the ERF."""
        return len(self._entries)

    def close(self):
        """Close the underlying file handle."""
        if self._file is not None:
            self._file.close()
            self._file = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def __del__(self):
        self.close()


# ---------------------------------------------------------------------------
#  write_erf  -  Write a complete ERF V1.0 file
# ---------------------------------------------------------------------------

def write_erf(
    file_path: str,
    resources: Dict[Tuple[str, int], bytes],
    file_type: str = "MOD ",
) -> None:
    """Write a complete ERF V1.0 file.

    Args:
        file_path: Output file path.
        resources: Dict mapping (resref, restype) to raw bytes.
        file_type: ERF file type identifier (default ``"MOD "``).

    Raises:
        ErfError: If the file cannot be written.
    """
    if len(file_type) != 4:
        raise ErfError(
            f"file_type must be exactly 4 characters, got {file_type!r}"
        )

    # Sort entries alphabetically by (restype, resref) for reproducibility
    sorted_keys = sorted(
        resources.keys(),
        key=lambda k: (k[1], k[0].lower()),
    )

    entry_count = len(sorted_keys)

    # Calculate offsets (no localized strings)
    offset_to_loc_str = ERF_HEADER_SIZE
    loc_str_size = 0
    offset_to_key_list = offset_to_loc_str + loc_str_size
    key_list_size = entry_count * ERF_V1_KEY_SIZE
    offset_to_res_list = offset_to_key_list + key_list_size
    res_list_size = entry_count * ERF_V1_RES_SIZE
    offset_to_data = offset_to_res_list + res_list_size

    # Build resource data and track offsets
    resource_data = bytearray()
    res_entries: List[Tuple[int, int]] = []  # (offset, size)

    for resref, restype in sorted_keys:
        data = resources[(resref, restype)]
        res_offset = offset_to_data + len(resource_data)
        res_entries.append((res_offset, len(data)))
        resource_data.extend(data)

    # Ensure total size fits in int32 (ERF format limitation)
    total_size = offset_to_data + len(resource_data)
    if total_size > 0x7FFFFFFF:
        raise ErfError(
            f"ERF would exceed 2GB limit ({total_size} bytes). "
            "This is not supported by the file format."
        )

    # Write the file
    out = bytearray()

    # -- Header (160 bytes) --
    out.extend(file_type.encode("ascii"))
    out.extend(b"V1.0")
    out.extend(struct.pack("<i", 0))                   # locStrCount
    out.extend(struct.pack("<i", 0))                   # locStrSize
    out.extend(struct.pack("<i", entry_count))
    out.extend(struct.pack("<i", offset_to_loc_str))
    out.extend(struct.pack("<i", offset_to_key_list))
    out.extend(struct.pack("<i", offset_to_res_list))
    out.extend(struct.pack("<i", 0))                   # buildYear
    out.extend(struct.pack("<i", 0))                   # buildDay
    out.extend(struct.pack("<i", 0))                   # strRef
    out.extend(b"\x00" * 116)                          # reserved
    assert len(out) == ERF_HEADER_SIZE

    # -- Key list --
    for idx, (resref, restype) in enumerate(sorted_keys):
        # 16-byte resref (null-padded)
        rr_bytes = resref.encode("ascii")[:16]
        out.extend(rr_bytes.ljust(16, b"\x00"))
        # 4-byte resource ID
        out.extend(struct.pack("<I", idx))
        # 2-byte restype
        out.extend(struct.pack("<H", restype))
        # 2-byte unused
        out.extend(b"\x00\x00")

    # -- Resource list --
    for res_offset, res_size in res_entries:
        out.extend(struct.pack("<I", res_offset))
        out.extend(struct.pack("<I", res_size))

    # -- Resource data --
    out.extend(resource_data)

    # Write atomically via temp file
    tmp_path = file_path + ".tmp"
    try:
        with open(tmp_path, "wb") as f:
            f.write(bytes(out))
        # On Windows, need to remove destination first if it exists
        if os.path.exists(file_path):
            backup_path = file_path + ".bak"
            if os.path.exists(backup_path):
                os.remove(backup_path)
            os.rename(file_path, backup_path)
        os.rename(tmp_path, file_path)
    except Exception as e:
        # Clean up temp file on failure
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        raise ErfError(f"Failed to write ERF file: {e}") from e
