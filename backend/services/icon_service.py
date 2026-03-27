"""Service for resolving and serving NWN item icons.

Handles icon filename resolution from baseitems.2da, texture lookup across
hak source directories and base game KEY/BIF files, TGA/DDS→PNG conversion,
PLT rendering, and composite icon assembly.

Performance: Parses KEY files natively at startup to build a complete base game
resource index. Reads BIF files directly for extraction (no subprocess calls).
Caches converted PNGs to disk to survive restarts.
"""
import hashlib
import io
import os
import struct
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image

from services.tda_service import TDAService


def _get_nwn_tools_path() -> Path:
    """Get path to neverwinter.nim tools directory."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent / "tools"
    return Path(__file__).resolve().parent.parent.parent.parent / "neverwinter.nim" / "bin"


def _get_cache_dir() -> Path:
    """Get directory for caching converted PNG icons."""
    if getattr(sys, 'frozen', False):
        app_data = os.environ.get('APPDATA') or os.path.expanduser('~')
        cache_dir = Path(app_data) / 'TDN Module Toolkit' / 'icon_cache'
    else:
        cache_dir = Path(__file__).resolve().parent.parent / 'icon_cache'
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


# ---------------------------------------------------------------------------
#  KEY/BIF file parser (native, no subprocess needed)
# ---------------------------------------------------------------------------

# NWN resource type IDs we care about for icons
_ICON_RESTYPES = {3: ".tga", 6: ".plt", 2033: ".dds"}


def _parse_key_file(key_path: Path) -> Dict[str, Tuple[Path, int, int]]:
    """Parse a NWN KEY file and return a resource index.

    Returns dict mapping "resref.ext" (lowercase) -> (bif_path, bif_offset, bif_size)
    Only indexes texture types (TGA, PLT, DDS).
    """
    index = {}
    try:
        with open(key_path, "rb") as f:
            data = f.read()
    except Exception as e:
        print(f"IconService: failed to read KEY file {key_path}: {e}", flush=True)
        return index

    if len(data) < 64:
        return index

    # Header
    file_type = data[:4]  # "KEY "
    file_ver = data[4:8]   # "V1  "
    bif_count = struct.unpack_from("<I", data, 8)[0]
    key_count = struct.unpack_from("<I", data, 12)[0]
    offset_to_files = struct.unpack_from("<I", data, 16)[0]
    offset_to_keys = struct.unpack_from("<I", data, 20)[0]

    # Parse BIF file table -> list of (bif_filename, bif_size)
    bif_entries = []
    key_dir = key_path.parent
    for i in range(bif_count):
        entry_offset = offset_to_files + i * 12
        bif_size = struct.unpack_from("<I", data, entry_offset)[0]
        name_offset = struct.unpack_from("<I", data, entry_offset + 4)[0]
        name_size = struct.unpack_from("<H", data, entry_offset + 8)[0]
        # drives = struct.unpack_from("<H", data, entry_offset + 10)[0]

        bif_name_raw = data[name_offset:name_offset + name_size]
        bif_name = bif_name_raw.rstrip(b'\x00').decode('ascii', errors='replace')
        # BIF paths use backslashes in the KEY file, normalize
        bif_name = bif_name.replace('\\', '/')
        bif_path = key_dir / bif_name
        bif_entries.append(bif_path)

    # Parse key table (resref -> BIF location)
    for i in range(key_count):
        entry_offset = offset_to_keys + i * 22
        if entry_offset + 22 > len(data):
            break

        resref_raw = data[entry_offset:entry_offset + 16]
        resref = resref_raw.rstrip(b'\x00').decode('ascii', errors='replace').lower()
        res_type = struct.unpack_from("<H", data, entry_offset + 16)[0]
        res_id = struct.unpack_from("<I", data, entry_offset + 18)[0]

        # Only index texture types
        ext = _ICON_RESTYPES.get(res_type)
        if not ext:
            continue

        # Decode ResID: upper 20 bits = BIF index, lower 14 bits = resource index within BIF
        # Actually for KEY V1: bits 20+ are BIF index, bits 0-13 are variable resource index
        bif_idx = (res_id >> 20) & 0xFFF
        res_idx = res_id & 0x3FFF

        if bif_idx >= len(bif_entries):
            continue

        bif_path = bif_entries[bif_idx]
        key = f"{resref}{ext}"
        # First entry wins (shouldn't have duplicates in a single KEY)
        if key not in index:
            index[key] = (bif_path, bif_idx, res_idx)

    return index


def _extract_from_bif(bif_path: Path, res_idx: int) -> Optional[bytes]:
    """Extract a single resource from a BIF file by its resource index.

    BIF V1 format:
    - Header (20 bytes): type(4) + version(4) + var_count(4) + fixed_count(4) + var_offset(4)
    - Variable resource table: entries of (id:4, offset:4, size:4)
    """
    try:
        with open(bif_path, "rb") as f:
            header = f.read(20)
            if len(header) < 20:
                return None

            var_count = struct.unpack_from("<I", header, 8)[0]
            var_offset = struct.unpack_from("<I", header, 16)[0]

            if res_idx >= var_count:
                return None

            # Read the resource table entry
            entry_offset = var_offset + res_idx * 16
            f.seek(entry_offset)
            entry = f.read(16)
            if len(entry) < 16:
                return None

            # id(4) + offset(4) + size(4) + type(4)
            data_offset = struct.unpack_from("<I", entry, 4)[0]
            data_size = struct.unpack_from("<I", entry, 8)[0]

            if data_size == 0 or data_size > 50_000_000:  # sanity limit 50MB
                return None

            f.seek(data_offset)
            return f.read(data_size)
    except Exception:
        return None


class IconService:
    """Resolves and serves NWN item icons as PNG images."""

    PLT_LAYERS = [
        "skin", "hair", "metal1", "metal2",
        "cloth1", "cloth2", "leather1", "leather2",
        "tattoo1", "tattoo2"
    ]

    DEFAULT_PALETTE_ROWS = {
        "skin": 2, "hair": 0, "metal1": 5, "metal2": 5,
        "cloth1": 10, "cloth2": 10, "leather1": 15, "leather2": 15,
        "tattoo1": 0, "tattoo2": 0
    }

    def __init__(
        self,
        tda_service: TDAService,
        hak_source_path: Optional[Path] = None,
        nwn_root_path: Optional[Path] = None,
    ):
        self.tda_service = tda_service
        self.hak_source_path = hak_source_path
        self.nwn_root_path = nwn_root_path

        # Case-insensitive resource index: lowercase_filename -> full_path
        self._hak_index: Dict[str, Path] = {}

        # Base game KEY/BIF index: lowercase_filename -> (bif_path, bif_idx, res_idx)
        self._key_index: Dict[str, Tuple[Path, int, int]] = {}

        # Parsed baseitems.2da data
        self._baseitems: Dict[int, dict] = {}

        # Palette images for PLT rendering
        self._palettes: Dict[str, Optional[Image.Image]] = {}

        # In-memory LRU cache: cache_key -> png_bytes
        self._mem_cache: Dict[str, bytes] = {}
        self._mem_cache_order: list = []
        self._mem_cache_max = 2000

        # Disk cache directory
        self._cache_dir = _get_cache_dir()

        # Negative cache: resrefs we know don't exist anywhere
        self._not_found: set = set()

        self._build_baseitems_cache()
        self._build_hak_index()
        self._build_key_index()
        self._load_palettes()

    # ------------------------------------------------------------------
    #  Initialization
    # ------------------------------------------------------------------

    def _build_baseitems_cache(self):
        """Extract icon-relevant columns from baseitems.2da."""
        if not self.tda_service:
            return
        data = self.tda_service.get_all_baseitems()
        if not data:
            return
        for row_id, row in data.items():
            try:
                model_type_raw = row.get("ModelType")
                item_class = row.get("ItemClass")
                default_icon = row.get("DefaultIcon")
                min_range_raw = row.get("MinRange")
                max_range_raw = row.get("MaxRange")

                model_type = int(model_type_raw) if model_type_raw is not None else None
                min_range = int(min_range_raw) if min_range_raw is not None else 0
                max_range = int(max_range_raw) if max_range_raw is not None else 255

                self._baseitems[row_id] = {
                    "model_type": model_type,
                    "item_class": item_class,
                    "default_icon": default_icon,
                    "min_range": min_range,
                    "max_range": max_range,
                }
            except (ValueError, TypeError):
                continue
        print(f"IconService: cached {len(self._baseitems)} base item types", flush=True)

    def _build_hak_index(self):
        """Scan hak source directories for texture files.

        Uses os.scandir for ~20x speedup over Path.iterdir on large dirs.
        """
        if not self.hak_source_path or not self.hak_source_path.exists():
            print("IconService: no hak_source_path, skipping hak index", flush=True)
            return

        count = 0
        hak_str = str(self.hak_source_path)
        try:
            for subdir in os.scandir(hak_str):
                if not subdir.is_dir() or not subdir.name.startswith("tdn_"):
                    continue
                try:
                    for entry in os.scandir(subdir.path):
                        if entry.is_file():
                            name_lower = entry.name.lower()
                            if name_lower.endswith((".tga", ".dds", ".plt")):
                                if name_lower not in self._hak_index:
                                    self._hak_index[name_lower] = Path(entry.path)
                                    count += 1
                except PermissionError:
                    continue
        except PermissionError:
            pass
        print(f"IconService: indexed {count} texture files from hak directories", flush=True)

    def _build_key_index(self):
        """Parse base game KEY files to build a complete resource index."""
        if not self.nwn_root_path:
            print("IconService: no nwn_root_path, skipping KEY index", flush=True)
            return

        data_dir = self.nwn_root_path / "data"
        if not data_dir.exists():
            print(f"IconService: data dir not found at {data_dir}", flush=True)
            return

        total = 0
        for key_file in sorted(data_dir.glob("*.key")):
            entries = _parse_key_file(key_file)
            # Hak index has priority, only add if not already in hak index
            for resname, bif_info in entries.items():
                if resname not in self._hak_index and resname not in self._key_index:
                    self._key_index[resname] = bif_info
                    total += 1
        print(f"IconService: indexed {total} texture resources from KEY files", flush=True)

    def _load_palettes(self):
        """Load palette TGA files for PLT rendering."""
        for name in ["pal_armor01", "pal_cloth01", "pal_leath01"]:
            img = self._load_image_raw(f"{name}.tga")
            if img:
                self._palettes[name] = img
            else:
                self._palettes[name] = None

    # ------------------------------------------------------------------
    #  Resource loading (no subprocess calls!)
    # ------------------------------------------------------------------

    def _resource_exists(self, resref_ext: str) -> bool:
        """Check if a resource exists in any index (hak or base game)."""
        return resref_ext in self._hak_index or resref_ext in self._key_index

    def _load_raw_bytes(self, resref_ext: str) -> Optional[bytes]:
        """Load raw file bytes from hak index or base game BIF."""
        # Check hak index first
        path = self._hak_index.get(resref_ext)
        if path:
            try:
                return path.read_bytes()
            except Exception:
                pass

        # Check base game KEY/BIF index
        bif_info = self._key_index.get(resref_ext)
        if bif_info:
            bif_path, _, res_idx = bif_info
            return _extract_from_bif(bif_path, res_idx)

        return None

    def _load_image_raw(self, resref_ext: str) -> Optional[Image.Image]:
        """Load an image from hak dirs or base game by full filename (e.g., 'foo.tga')."""
        raw = self._load_raw_bytes(resref_ext.lower())
        if raw:
            try:
                return Image.open(io.BytesIO(raw)).convert("RGBA")
            except Exception:
                pass
        return None

    def _load_texture(self, resref: str) -> Optional[Image.Image]:
        """Load a texture by resref (no extension), trying TGA, DDS, then PLT."""
        resref_lower = resref.lower()

        if resref_lower in self._not_found:
            return None

        # Try TGA, DDS from hak or base game
        for ext in (".tga", ".dds"):
            key = resref_lower + ext
            raw = self._load_raw_bytes(key)
            if raw:
                try:
                    return Image.open(io.BytesIO(raw)).convert("RGBA")
                except Exception:
                    continue

        # Try PLT
        raw = self._load_raw_bytes(resref_lower + ".plt")
        if raw:
            img = self._render_plt_bytes(raw)
            if img:
                return img

        self._not_found.add(resref_lower)
        return None

    # ------------------------------------------------------------------
    #  Disk + memory cache
    # ------------------------------------------------------------------

    def _cache_key(self, base_item: int, p1: int, p2: int, p3: int) -> str:
        return f"{base_item}_{p1}_{p2}_{p3}"

    def _disk_cache_path(self, cache_key: str) -> Path:
        return self._cache_dir / f"{cache_key}.png"

    def _get_cached(self, cache_key: str) -> Optional[bytes]:
        """Check memory cache, then disk cache."""
        # Memory
        if cache_key in self._mem_cache:
            return self._mem_cache[cache_key]
        # Disk
        disk_path = self._disk_cache_path(cache_key)
        if disk_path.exists():
            try:
                data = disk_path.read_bytes()
                self._put_mem_cache(cache_key, data)
                return data
            except Exception:
                pass
        return None

    def _put_cached(self, cache_key: str, data: bytes):
        """Store in both memory and disk cache."""
        self._put_mem_cache(cache_key, data)
        try:
            self._disk_cache_path(cache_key).write_bytes(data)
        except Exception:
            pass

    def _put_mem_cache(self, cache_key: str, data: bytes):
        """Store in memory cache with LRU eviction."""
        if cache_key in self._mem_cache:
            return
        if len(self._mem_cache_order) >= self._mem_cache_max:
            evict = self._mem_cache_order.pop(0)
            self._mem_cache.pop(evict, None)
        self._mem_cache[cache_key] = data
        self._mem_cache_order.append(cache_key)

    # ------------------------------------------------------------------
    #  Icon resolution
    # ------------------------------------------------------------------

    def _get_icon_resref(self, base_item: int, part1: int, part2: int = 0, part3: int = 0) -> Optional[dict]:
        """Determine icon resref(s) from base item type and model parts."""
        info = self._baseitems.get(base_item)
        if not info or info["model_type"] is None:
            return None

        item_class = info["item_class"]
        if not item_class:
            return None

        model_type = info["model_type"]
        ic = item_class.lower()

        if model_type == 0:
            return {"resref": f"i{ic}_{part1:03d}", "model_type": 0}
        elif model_type == 1:
            return {"resref": f"i{ic}_{part1:03d}", "model_type": 1}
        elif model_type == 2:
            return {
                "bottom": f"i{ic}_b_{part1:03d}",
                "middle": f"i{ic}_m_{part2:03d}",
                "top": f"i{ic}_t_{part3:03d}",
                "model_type": 2,
            }
        elif model_type == 3:
            default_icon = info.get("default_icon")
            if default_icon:
                return {"resref": default_icon.lower(), "model_type": 3}

        return None

    def _image_to_png_bytes(self, img: Image.Image) -> bytes:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    def get_icon_png(self, base_item: int, part1: int, part2: int = 0, part3: int = 0) -> Optional[bytes]:
        """Get the icon PNG bytes for an item. Uses disk+memory cache."""
        ck = self._cache_key(base_item, part1, part2, part3)
        cached = self._get_cached(ck)
        if cached:
            return cached

        png_data = self._resolve_icon(base_item, part1, part2, part3)
        if png_data:
            self._put_cached(ck, png_data)
        return png_data

    def _resolve_icon(self, base_item: int, part1: int, part2: int, part3: int) -> Optional[bytes]:
        """Actually resolve and render an icon (uncached)."""
        icon_info = self._get_icon_resref(base_item, part1, part2, part3)

        if icon_info:
            model_type = icon_info.get("model_type")

            if model_type == 2:
                bottom = self._load_texture(icon_info["bottom"])
                middle = self._load_texture(icon_info["middle"])
                top = self._load_texture(icon_info["top"])
                result = self._assemble_composite(bottom, middle, top)
                if result:
                    return self._image_to_png_bytes(result)
                if bottom:
                    return self._image_to_png_bytes(bottom)
            else:
                resref = icon_info.get("resref")
                if resref:
                    img = self._load_texture(resref)
                    if img:
                        return self._image_to_png_bytes(img)

        # Fallback: DefaultIcon
        info = self._baseitems.get(base_item)
        if info and info.get("default_icon"):
            img = self._load_texture(info["default_icon"])
            if img:
                return self._image_to_png_bytes(img)

        return None

    def get_default_icon_png(self, base_item: int) -> Optional[bytes]:
        """Get the default icon for a base item type."""
        info = self._baseitems.get(base_item)
        if not info:
            return None
        if info.get("default_icon"):
            img = self._load_texture(info["default_icon"])
            if img:
                return self._image_to_png_bytes(img)
        return self.get_icon_png(base_item, 1, 1, 1)

    def get_preview_png(self, base_item: int, part1: int, part2: int = 0, part3: int = 0) -> Optional[bytes]:
        """Get a preview icon (uses same cache)."""
        return self.get_icon_png(base_item, part1, part2, part3)

    # ------------------------------------------------------------------
    #  Available parts listing (no subprocess - uses indexes)
    # ------------------------------------------------------------------

    def list_available_parts(self, base_item: int) -> Optional[dict]:
        """List available icon part numbers for a base item type."""
        info = self._baseitems.get(base_item)
        if not info or info["model_type"] is None:
            return None

        model_type = info["model_type"]
        item_class = info.get("item_class")
        if not item_class:
            return None

        ic = item_class.lower()
        min_r = info["min_range"]
        max_r = info["max_range"]

        if model_type == 0:
            return {"model_type": 0, "parts": self._scan_parts(f"i{ic}_", min_r, max_r)}
        elif model_type == 1:
            return {"model_type": 1, "parts": self._scan_parts(f"i{ic}_", min_r, max_r)}
        elif model_type == 2:
            return {
                "model_type": 2,
                "bottom_parts": self._scan_parts(f"i{ic}_b_", min_r, max_r),
                "middle_parts": self._scan_parts(f"i{ic}_m_", min_r, max_r),
                "top_parts": self._scan_parts(f"i{ic}_t_", min_r, max_r),
            }
        elif model_type == 3:
            return {"model_type": 3, "default_icon": info.get("default_icon")}
        return None

    def _scan_parts(self, prefix: str, min_range: int, max_range: int) -> List[int]:
        """Scan both hak and KEY indexes for available part numbers. No subprocess."""
        found = set()
        prefix_lower = prefix.lower()
        exts = (".tga", ".dds", ".plt")

        # Scan hak index
        for key in self._hak_index:
            if not key.startswith(prefix_lower):
                continue
            remainder = key[len(prefix_lower):]
            for ext in exts:
                if remainder.endswith(ext):
                    try:
                        num = int(remainder[:-len(ext)])
                        if min_range <= num <= max_range:
                            found.add(num)
                    except ValueError:
                        pass

        # Scan KEY index (same logic, no subprocess!)
        for key in self._key_index:
            if not key.startswith(prefix_lower):
                continue
            remainder = key[len(prefix_lower):]
            for ext in exts:
                if remainder.endswith(ext):
                    try:
                        num = int(remainder[:-len(ext)])
                        if min_range <= num <= max_range:
                            found.add(num)
                    except ValueError:
                        pass

        return sorted(found)

    # ------------------------------------------------------------------
    #  Composite assembly
    # ------------------------------------------------------------------

    def _assemble_composite(self, bottom: Optional[Image.Image], middle: Optional[Image.Image], top: Optional[Image.Image]) -> Optional[Image.Image]:
        parts = [p for p in [bottom, middle, top] if p is not None]
        if not parts:
            return None
        size = parts[0].size
        result = Image.new("RGBA", size, (0, 0, 0, 0))
        for part in parts:
            if part.size != size:
                part = part.resize(size, Image.LANCZOS)
            result = Image.alpha_composite(result, part)
        return result

    # ------------------------------------------------------------------
    #  PLT rendering
    # ------------------------------------------------------------------

    def _render_plt_bytes(self, data: bytes) -> Optional[Image.Image]:
        try:
            if len(data) < 24 or data[:8] != b"PLT V1  ":
                return None
            width = struct.unpack_from("<I", data, 16)[0]
            height = struct.unpack_from("<I", data, 20)[0]
            pixel_start = 24
            expected = pixel_start + width * height * 2
            if len(data) < expected:
                return None
            return self._render_plt_pixels(data[pixel_start:expected], width, height)
        except Exception:
            return None

    def _render_plt_pixels(self, pixel_data: bytes, width: int, height: int) -> Optional[Image.Image]:
        """Render PLT pixel data. Optimized: builds RGBA buffer directly."""
        palette = self._palettes.get("pal_armor01")

        # Pre-build palette lookup table for speed
        # palette_lut[layer_idx] = row of RGBA values indexed by intensity
        palette_lut = {}
        if palette:
            pw, ph = palette.size
            for layer_idx, layer_name in enumerate(self.PLT_LAYERS):
                row = self.DEFAULT_PALETTE_ROWS.get(layer_name, 0)
                row = min(row, ph - 1)
                # Read entire palette row at once
                lut = []
                for intensity in range(256):
                    px = min(intensity, pw - 1)
                    c = palette.getpixel((px, row))
                    if len(c) == 4:
                        lut.append(c)
                    else:
                        lut.append((*c[:3], 255))
                palette_lut[layer_idx] = lut

        # Build RGBA buffer
        buf = bytearray(width * height * 4)
        for y in range(height):
            out_y = height - 1 - y
            for x in range(width):
                src_offset = (y * width + x) * 2
                intensity = pixel_data[src_offset]
                layer_idx = pixel_data[src_offset + 1]

                dst_offset = (out_y * width + x) * 4

                if layer_idx in palette_lut:
                    r, g, b, a = palette_lut[layer_idx][intensity]
                    buf[dst_offset] = r
                    buf[dst_offset + 1] = g
                    buf[dst_offset + 2] = b
                    buf[dst_offset + 3] = a
                elif intensity == 0:
                    buf[dst_offset:dst_offset + 4] = b'\x00\x00\x00\x00'
                else:
                    buf[dst_offset] = intensity
                    buf[dst_offset + 1] = intensity
                    buf[dst_offset + 2] = intensity
                    buf[dst_offset + 3] = 255

        return Image.frombytes("RGBA", (width, height), bytes(buf))
