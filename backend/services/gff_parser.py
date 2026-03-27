"""GFF binary parser for Neverwinter Nights GFF V3.2 format.

Reads and writes GFF binary data to/from Python dicts in the exact same
format as nwn_gff JSON output. No external dependencies beyond the
Python standard library.

Reference implementations:
- neverwinter.nim/neverwinter/gff.nim (binary format)
- neverwinter.nim/neverwinter/gffjson.nim (JSON mapping)
"""

import struct
import base64
from typing import Dict, Any, Optional, List, Tuple

# ---------------------------------------------------------------------------
#  Constants
# ---------------------------------------------------------------------------

GFF_HEADER_SIZE = 56
GFF_STRUCT_ENTRY_SIZE = 12
GFF_FIELD_ENTRY_SIZE = 12
GFF_LABEL_SIZE = 16

BAD_STR_REF = 0xFFFFFFFF

# Field type IDs (GffFieldKind enum from gff.nim)
FIELD_TYPE_BYTE = 0
FIELD_TYPE_CHAR = 1
FIELD_TYPE_WORD = 2
FIELD_TYPE_SHORT = 3
FIELD_TYPE_DWORD = 4
FIELD_TYPE_INT = 5
FIELD_TYPE_DWORD64 = 6
FIELD_TYPE_INT64 = 7
FIELD_TYPE_FLOAT = 8
FIELD_TYPE_DOUBLE = 9
FIELD_TYPE_CEXOSTRING = 10
FIELD_TYPE_RESREF = 11
FIELD_TYPE_CEXOLOCSTRING = 12
FIELD_TYPE_VOID = 13
FIELD_TYPE_STRUCT = 14
FIELD_TYPE_LIST = 15

# Lowercase type names used in JSON output (matching gffjson.nim)
FIELD_TYPE_NAMES: Dict[int, str] = {
    FIELD_TYPE_BYTE: "byte",
    FIELD_TYPE_CHAR: "char",
    FIELD_TYPE_WORD: "word",
    FIELD_TYPE_SHORT: "short",
    FIELD_TYPE_DWORD: "dword",
    FIELD_TYPE_INT: "int",
    FIELD_TYPE_DWORD64: "dword64",
    FIELD_TYPE_INT64: "int64",
    FIELD_TYPE_FLOAT: "float",
    FIELD_TYPE_DOUBLE: "double",
    FIELD_TYPE_CEXOSTRING: "cexostring",
    FIELD_TYPE_RESREF: "resref",
    FIELD_TYPE_CEXOLOCSTRING: "cexolocstring",
    FIELD_TYPE_VOID: "void",
    FIELD_TYPE_STRUCT: "struct",
    FIELD_TYPE_LIST: "list",
}

# Reverse lookup for JSON type name -> field type ID
FIELD_TYPE_IDS: Dict[str, int] = {v: k for k, v in FIELD_TYPE_NAMES.items()}

# Complex types that store data at an offset in the field data block
# (rather than inline in the dataOrOffset field).
# Note: Struct uses a struct-array index and List uses a list-indices-array
# offset — neither uses the field data block, so they are excluded here.
_COMPLEX_FIELD_DATA_TYPES = frozenset({
    FIELD_TYPE_DWORD64, FIELD_TYPE_INT64, FIELD_TYPE_DOUBLE,
    FIELD_TYPE_CEXOSTRING, FIELD_TYPE_RESREF, FIELD_TYPE_CEXOLOCSTRING,
    FIELD_TYPE_VOID,
})

# NWN encoding for string data
NWN_ENCODING = "windows-1252"


# ---------------------------------------------------------------------------
#  Exceptions
# ---------------------------------------------------------------------------

class GffParseError(Exception):
    """Raised when GFF binary data cannot be parsed."""


# ---------------------------------------------------------------------------
#  read_gff  -  binary GFF -> Python dict (nwn_gff JSON-compatible)
# ---------------------------------------------------------------------------

def read_gff(data: bytes) -> dict:
    """Parse binary GFF data into a Python dict.

    The returned dict matches the JSON output format of nwn_gff:
    - Root has ``__data_type`` key
    - Each field is ``{"type": "<name>", "value": <val>}``
    - Void fields use ``"value64"`` with base64-encoded data
    - Struct fields include ``"__struct_id"`` on the outer dict
    - CExoLocString value is an object with language-id keys and optional ``"id"``

    Args:
        data: Raw bytes of a GFF binary file.

    Returns:
        A dict representing the GFF structure.

    Raises:
        GffParseError: If the data is invalid or truncated.
    """
    if len(data) < GFF_HEADER_SIZE:
        raise GffParseError(
            f"Data too short for GFF header: {len(data)} bytes "
            f"(need at least {GFF_HEADER_SIZE})"
        )

    # -- Header ---------------------------------------------------------------
    file_type = data[0:4].decode("ascii")
    file_version = data[4:8].decode("ascii")

    if file_version != "V3.2":
        raise GffParseError(f"Unsupported GFF version: {file_version!r}")

    (
        struct_offset, struct_count,
        field_offset, field_count,
        label_offset, label_count,
        field_data_offset, field_data_size,
        field_indices_offset, field_indices_size,
        list_indices_offset, list_indices_size,
    ) = struct.unpack_from("<12I", data, 8)

    if struct_offset != 56:
        raise GffParseError(
            f"Expected struct offset 56, got {struct_offset}"
        )

    # -- Parse arrays ---------------------------------------------------------

    # Struct array: (id: int32, dataOrOffset: uint32, fieldCount: uint32)
    structs: List[Tuple[int, int, int]] = []
    for i in range(struct_count):
        off = struct_offset + i * GFF_STRUCT_ENTRY_SIZE
        sid, s_data_or_offset, s_field_count = struct.unpack_from(
            "<iII", data, off
        )
        structs.append((sid, s_data_or_offset, s_field_count))

    # Field array: (kind: uint32, labelIndex: uint32, dataOrOffset: uint32)
    fields: List[Tuple[int, int, int]] = []
    for i in range(field_count):
        off = field_offset + i * GFF_FIELD_ENTRY_SIZE
        f_kind, f_label_idx, f_data_or_offset = struct.unpack_from(
            "<III", data, off
        )
        if f_kind > FIELD_TYPE_LIST:
            raise GffParseError(
                f"Unknown field type {f_kind} at field index {i}"
            )
        fields.append((f_kind, f_label_idx, f_data_or_offset))

    # Label array: 16-byte null-padded strings
    labels: List[str] = []
    for i in range(label_count):
        off = label_offset + i * GFF_LABEL_SIZE
        raw = data[off:off + GFF_LABEL_SIZE]
        labels.append(raw.split(b"\x00", 1)[0].decode("ascii"))

    # Field indices array (uint32 values, byte size / 4 entries)
    fi_count = field_indices_size // 4
    field_indices: List[int] = list(
        struct.unpack_from(f"<{fi_count}I", data, field_indices_offset)
    ) if fi_count > 0 else []

    # List indices array (uint32 values)
    li_count = list_indices_size // 4
    list_indices: List[int] = list(
        struct.unpack_from(f"<{li_count}I", data, list_indices_offset)
    ) if li_count > 0 else []

    # -- Resolve structs recursively ------------------------------------------

    def _decode_nwn_string(raw_bytes: bytes) -> str:
        """Decode a NWN string from windows-1252 to Python str (UTF-8)."""
        try:
            return raw_bytes.decode(NWN_ENCODING)
        except (UnicodeDecodeError, LookupError):
            return raw_bytes.decode("latin-1")

    def _read_field_value(f_kind: int, f_data_or_offset: int) -> Any:
        """Read a single field value, returning the JSON-compatible value."""

        # -- Simple (inline) types -------------------------------------------
        if f_kind == FIELD_TYPE_BYTE:
            return f_data_or_offset & 0xFF

        if f_kind == FIELD_TYPE_CHAR:
            val = f_data_or_offset & 0xFF
            return val if val < 128 else val - 256  # signed int8

        if f_kind == FIELD_TYPE_WORD:
            return f_data_or_offset & 0xFFFF

        if f_kind == FIELD_TYPE_SHORT:
            val = f_data_or_offset & 0xFFFF
            return val if val < 32768 else val - 65536  # signed int16

        if f_kind == FIELD_TYPE_DWORD:
            return f_data_or_offset & 0xFFFFFFFF

        if f_kind == FIELD_TYPE_INT:
            val = f_data_or_offset & 0xFFFFFFFF
            if val >= 0x80000000:
                val -= 0x100000000
            return val

        if f_kind == FIELD_TYPE_FLOAT:
            # Reinterpret the uint32 bit pattern as float32
            bits = struct.pack("<I", f_data_or_offset & 0xFFFFFFFF)
            return struct.unpack("<f", bits)[0]

        # -- Complex types (data at offset in field data block) ---------------
        off = field_data_offset + f_data_or_offset

        if f_kind == FIELD_TYPE_DWORD64:
            return struct.unpack_from("<Q", data, off)[0]

        if f_kind == FIELD_TYPE_INT64:
            return struct.unpack_from("<q", data, off)[0]

        if f_kind == FIELD_TYPE_DOUBLE:
            return struct.unpack_from("<d", data, off)[0]

        if f_kind == FIELD_TYPE_CEXOSTRING:
            str_len = struct.unpack_from("<I", data, off)[0]
            raw = data[off + 4:off + 4 + str_len]
            return _decode_nwn_string(raw)

        if f_kind == FIELD_TYPE_RESREF:
            rr_len = struct.unpack_from("<B", data, off)[0]
            raw = data[off + 1:off + 1 + rr_len]
            return raw.decode("ascii")

        if f_kind == FIELD_TYPE_CEXOLOCSTRING:
            total_size = struct.unpack_from("<I", data, off)[0]
            pos = off + 4
            str_ref = struct.unpack_from("<I", data, pos)[0]
            pos += 4
            count = struct.unpack_from("<I", data, pos)[0]
            pos += 4
            entries: Dict[str, Any] = {}
            if str_ref != BAD_STR_REF:
                entries["id"] = str_ref
            for _ in range(count):
                lang_id = struct.unpack_from("<i", data, pos)[0]
                pos += 4
                s_len = struct.unpack_from("<I", data, pos)[0]
                pos += 4
                raw = data[pos:pos + s_len]
                entries[str(lang_id)] = _decode_nwn_string(raw)
                pos += s_len
            return entries

        if f_kind == FIELD_TYPE_VOID:
            v_len = struct.unpack_from("<I", data, off)[0]
            raw = data[off + 4:off + 4 + v_len]
            return base64.b64encode(raw).decode("ascii")

        # Struct and List are handled separately in _resolve_struct
        return None  # pragma: no cover

    def _resolve_struct(struct_idx: int) -> dict:
        """Resolve a struct by index into a dict."""
        sid, s_data_or_offset, s_field_count = structs[struct_idx]

        result: Dict[str, Any] = {}

        # __struct_id is only set for non-root structs (id != -1)
        if sid != -1:
            result["__struct_id"] = sid

        # Determine which field indices belong to this struct
        if s_field_count == 0:
            return result
        elif s_field_count == 1:
            field_idx_list = [s_data_or_offset]
        else:
            # Byte offset into field indices array -> divide by 4
            fi_start = s_data_or_offset // 4
            field_idx_list = field_indices[fi_start:fi_start + s_field_count]

        # Resolve each field
        for fidx in field_idx_list:
            f_kind, f_label_idx, f_data_or_offset = fields[fidx]
            label = labels[f_label_idx]
            type_name = FIELD_TYPE_NAMES[f_kind]

            if f_kind == FIELD_TYPE_STRUCT:
                # Struct: dataOrOffset is the struct index
                child = _resolve_struct(f_data_or_offset)
                result[label] = {
                    "type": type_name,
                    "value": child,
                    "__struct_id": child.get("__struct_id", 0),
                }

            elif f_kind == FIELD_TYPE_LIST:
                # List: dataOrOffset is byte offset into list indices array
                li_offset = f_data_or_offset // 4
                list_size = list_indices[li_offset]
                items = []
                for j in range(list_size):
                    child_struct_idx = list_indices[li_offset + 1 + j]
                    items.append(_resolve_struct(child_struct_idx))
                result[label] = {
                    "type": type_name,
                    "value": items,
                }

            elif f_kind == FIELD_TYPE_VOID:
                result[label] = {
                    "type": type_name,
                    "value64": _read_field_value(f_kind, f_data_or_offset),
                }

            else:
                result[label] = {
                    "type": type_name,
                    "value": _read_field_value(f_kind, f_data_or_offset),
                }

        return result

    # Resolve root struct (always index 0)
    root = _resolve_struct(0)
    root["__data_type"] = file_type
    # Root struct should NOT have __struct_id (id is -1)
    root.pop("__struct_id", None)
    return root


# ---------------------------------------------------------------------------
#  write_gff  -  Python dict -> binary GFF
# ---------------------------------------------------------------------------

def write_gff(data: dict) -> bytes:
    """Convert a dict (nwn_gff JSON format) back to binary GFF data.

    Args:
        data: A dict in nwn_gff JSON format (with ``__data_type``, typed fields).

    Returns:
        Raw bytes of a GFF binary file.

    Raises:
        GffParseError: If the dict structure is invalid.
    """
    file_type = data.get("__data_type", "GFF ")
    if len(file_type) != 4:
        raise GffParseError(
            f"__data_type must be exactly 4 characters, got {file_type!r}"
        )
    file_version = "V3.2"

    # Accumulators for the binary sections
    structs_list: List[Tuple[int, int, int]] = []  # (id, dataOrOffset, fieldCount)
    fields_list: List[Tuple[int, int, int]] = []   # (kind, labelIdx, dataOrOffset)
    labels_list: List[str] = []
    field_data = bytearray()
    field_indices_list: List[int] = []
    list_indices_list: List[int] = []

    def _get_label_index(label: str) -> int:
        """Get or create a label index."""
        try:
            return labels_list.index(label)
        except ValueError:
            labels_list.append(label)
            return len(labels_list) - 1

    def _encode_nwn_string(s: str) -> bytes:
        """Encode a Python string to NWN windows-1252 bytes."""
        try:
            return s.encode(NWN_ENCODING)
        except (UnicodeEncodeError, LookupError):
            return s.encode("latin-1")

    def _collect_struct(d: dict) -> int:
        """Recursively collect a struct, returning its index in structs_list."""
        struct_id = d.get("__struct_id", -1)

        # Reserve our slot (depth-first, so children get higher indices)
        my_idx = len(structs_list)
        structs_list.append((struct_id, 0, 0))  # placeholder

        this_field_indices: List[int] = []

        for key, val in d.items():
            if key.startswith("__"):
                continue

            if not isinstance(val, dict) or "type" not in val:
                continue

            type_name = val["type"]
            f_kind = FIELD_TYPE_IDS.get(type_name)
            if f_kind is None:
                raise GffParseError(f"Unknown field type: {type_name!r}")

            label_idx = _get_label_index(key)
            data_or_offset = 0

            # -- Simple (inline) types ---------------------------------------
            if f_kind == FIELD_TYPE_BYTE:
                data_or_offset = int(val["value"]) & 0xFF

            elif f_kind == FIELD_TYPE_CHAR:
                v = int(val["value"])
                # Pack as signed int8, store as uint32
                data_or_offset = struct.unpack("<I", struct.pack("<i", v))[0]

            elif f_kind == FIELD_TYPE_WORD:
                data_or_offset = int(val["value"]) & 0xFFFF

            elif f_kind == FIELD_TYPE_SHORT:
                v = int(val["value"])
                data_or_offset = struct.unpack("<I", struct.pack("<i", v))[0]

            elif f_kind == FIELD_TYPE_DWORD:
                data_or_offset = int(val["value"]) & 0xFFFFFFFF

            elif f_kind == FIELD_TYPE_INT:
                v = int(val["value"])
                data_or_offset = struct.unpack("<I", struct.pack("<i", v))[0]

            elif f_kind == FIELD_TYPE_FLOAT:
                fv = float(val["value"])
                # Pack float32, reinterpret as uint32
                data_or_offset = struct.unpack("<I", struct.pack("<f", fv))[0]

            # -- Complex types (data in field data block) --------------------
            elif f_kind == FIELD_TYPE_DWORD64:
                data_or_offset = len(field_data)
                field_data.extend(struct.pack("<Q", int(val["value"])))

            elif f_kind == FIELD_TYPE_INT64:
                data_or_offset = len(field_data)
                field_data.extend(struct.pack("<q", int(val["value"])))

            elif f_kind == FIELD_TYPE_DOUBLE:
                data_or_offset = len(field_data)
                field_data.extend(struct.pack("<d", float(val["value"])))

            elif f_kind == FIELD_TYPE_CEXOSTRING:
                data_or_offset = len(field_data)
                encoded = _encode_nwn_string(val["value"])
                field_data.extend(struct.pack("<I", len(encoded)))
                field_data.extend(encoded)

            elif f_kind == FIELD_TYPE_RESREF:
                data_or_offset = len(field_data)
                raw = val["value"].encode("ascii")
                field_data.extend(struct.pack("<B", len(raw)))
                field_data.extend(raw)

            elif f_kind == FIELD_TYPE_CEXOLOCSTRING:
                data_or_offset = len(field_data)
                loc_val = val["value"]
                str_ref = BAD_STR_REF
                entries: List[Tuple[int, bytes]] = []

                # Check for strref at field level first (legacy pattern
                # from older nwn_gff versions):
                #   {"id": 12837, "type": "cexolocstring", "value": {}}
                if "id" in val:
                    str_ref = int(val["id"])

                for lk, lv in loc_val.items():
                    if lk == "id":
                        # Inner "id" (current nwn_gff pattern) overrides
                        # field-level "id" if both are present
                        str_ref = int(lv)
                    else:
                        entries.append((int(lk), _encode_nwn_string(lv)))

                # Build the inner data: strRef(4) + count(4) + entries
                inner = bytearray()
                inner.extend(struct.pack("<I", str_ref))
                inner.extend(struct.pack("<I", len(entries)))
                for lang_id, encoded_str in entries:
                    inner.extend(struct.pack("<i", lang_id))
                    inner.extend(struct.pack("<I", len(encoded_str)))
                    inner.extend(encoded_str)

                # Total size includes strRef + count + entries (not itself)
                total_size = len(inner)
                field_data.extend(struct.pack("<I", total_size))
                field_data.extend(inner)

            elif f_kind == FIELD_TYPE_VOID:
                data_or_offset = len(field_data)
                # "value64" is base64-encoded (current format).
                # "value" is raw string bytes (legacy format, per gffjson.nim).
                if "value64" in val:
                    raw_data = base64.b64decode(val["value64"])
                else:
                    raw_data = val["value"].encode("latin-1")
                field_data.extend(struct.pack("<I", len(raw_data)))
                field_data.extend(raw_data)

            elif f_kind == FIELD_TYPE_STRUCT:
                child_idx = _collect_struct(val["value"])
                data_or_offset = child_idx

            elif f_kind == FIELD_TYPE_LIST:
                child_struct_indices: List[int] = []
                for item in val["value"]:
                    child_struct_indices.append(_collect_struct(item))

                data_or_offset = len(list_indices_list) * 4
                list_indices_list.append(len(child_struct_indices))
                list_indices_list.extend(child_struct_indices)

            # Record the field
            field_idx = len(fields_list)
            fields_list.append((f_kind, label_idx, data_or_offset))
            this_field_indices.append(field_idx)

        # Update the struct entry with real data
        fc = len(this_field_indices)
        if fc == 1:
            s_data_or_offset = this_field_indices[0]
        elif fc > 1:
            s_data_or_offset = len(field_indices_list) * 4
            field_indices_list.extend(this_field_indices)
        else:
            s_data_or_offset = 0

        structs_list[my_idx] = (struct_id, s_data_or_offset, fc)
        return my_idx

    root_idx = _collect_struct(data)
    if root_idx != 0:
        raise GffParseError("Root struct must be at index 0")

    # -- Build binary output --------------------------------------------------
    s_count = len(structs_list)
    f_count = len(fields_list)
    l_count = len(labels_list)
    fd_size = len(field_data)
    fi_size = len(field_indices_list) * 4
    li_size = len(list_indices_list) * 4

    struct_offset_val = 56
    field_offset_val = struct_offset_val + s_count * GFF_STRUCT_ENTRY_SIZE
    label_offset_val = field_offset_val + f_count * GFF_FIELD_ENTRY_SIZE
    field_data_offset_val = label_offset_val + l_count * GFF_LABEL_SIZE
    field_indices_offset_val = field_data_offset_val + fd_size
    list_indices_offset_val = field_indices_offset_val + fi_size

    out = bytearray()

    # Header
    out.extend(file_type.encode("ascii"))
    out.extend(file_version.encode("ascii"))
    out.extend(struct.pack("<I", struct_offset_val))
    out.extend(struct.pack("<I", s_count))
    out.extend(struct.pack("<I", field_offset_val))
    out.extend(struct.pack("<I", f_count))
    out.extend(struct.pack("<I", label_offset_val))
    out.extend(struct.pack("<I", l_count))
    out.extend(struct.pack("<I", field_data_offset_val))
    out.extend(struct.pack("<I", fd_size))
    out.extend(struct.pack("<I", field_indices_offset_val))
    out.extend(struct.pack("<I", fi_size))
    out.extend(struct.pack("<I", list_indices_offset_val))
    out.extend(struct.pack("<I", li_size))

    assert len(out) == 56

    # Struct array
    for sid, s_do, s_fc in structs_list:
        out.extend(struct.pack("<i", sid))
        out.extend(struct.pack("<I", s_do))
        out.extend(struct.pack("<I", s_fc))

    # Field array
    for fk, fli, fdo in fields_list:
        out.extend(struct.pack("<I", fk))
        out.extend(struct.pack("<I", fli))
        out.extend(struct.pack("<I", fdo))

    # Label array (16-byte null-padded)
    for lbl in labels_list:
        encoded = lbl.encode("ascii")
        out.extend(encoded[:16].ljust(16, b"\x00"))

    # Field data block
    out.extend(field_data)

    # Field indices array
    for fi in field_indices_list:
        out.extend(struct.pack("<I", fi))

    # List indices array
    for li in list_indices_list:
        out.extend(struct.pack("<I", li))

    return bytes(out)
