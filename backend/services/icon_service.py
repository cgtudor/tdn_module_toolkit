"""Service for resolving and serving NWN item icons.

Handles icon filename resolution from baseitems.2da, texture lookup across
hak source directories and base game KEY/BIF files, TGA/DDS→PNG conversion,
PLT rendering, and composite icon assembly.
"""
import io
import struct
import subprocess
import sys
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image

from services.tda_service import TDAService


def _get_nwn_tools_path() -> Path:
    """Get path to neverwinter.nim tools directory."""
    if getattr(sys, 'frozen', False):
        # In bundled mode, tools should be alongside the executable
        return Path(sys.executable).parent / "tools"
    # In development, relative to workspace
    return Path(__file__).resolve().parent.parent.parent.parent / "neverwinter.nim" / "bin"


class IconService:
    """Resolves and serves NWN item icons as PNG images."""

    # PLT palette layer names (index → layer)
    PLT_LAYERS = [
        "skin", "hair", "metal1", "metal2",
        "cloth1", "cloth2", "leather1", "leather2",
        "tattoo1", "tattoo2"
    ]

    # Default palette row indices for each layer (neutral/gray appearance)
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
        self._resman_path = _get_nwn_tools_path() / "nwn_resman_cat.exe"

        # Case-insensitive resource index: lowercase_filename -> full_path
        self._resource_index: Dict[str, Path] = {}

        # Parsed baseitems.2da data: row_id -> {ModelType, ItemClass, DefaultIcon, MinRange, MaxRange}
        self._baseitems: Dict[int, dict] = {}

        # Palette images for PLT rendering
        self._palettes: Dict[str, Optional[Image.Image]] = {}

        self._build_baseitems_cache()
        self._build_resource_index()
        self._load_palettes()

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

    def _build_resource_index(self):
        """Scan hak source directories for icon texture files (.tga, .dds, .plt)."""
        if not self.hak_source_path or not self.hak_source_path.exists():
            print("IconService: no hak_source_path, skipping resource index", flush=True)
            return

        count = 0
        icon_extensions = {".tga", ".dds", ".plt"}
        for subdir in self.hak_source_path.iterdir():
            if not subdir.is_dir():
                continue
            # Scan all tdn_* directories
            if not subdir.name.startswith("tdn_"):
                continue
            try:
                for file_path in subdir.iterdir():
                    if file_path.is_file() and file_path.suffix.lower() in icon_extensions:
                        key = file_path.name.lower()
                        # Hak dirs have higher priority than base game, first one wins
                        if key not in self._resource_index:
                            self._resource_index[key] = file_path
                            count += 1
            except PermissionError:
                continue

        print(f"IconService: indexed {count} texture files from hak directories", flush=True)

    def _load_palettes(self):
        """Load palette TGA files for PLT rendering."""
        palette_names = ["pal_armor01", "pal_cloth01", "pal_leath01"]
        for name in palette_names:
            img = self._find_and_load_image(f"{name}.tga")
            if img:
                self._palettes[name] = img
                print(f"IconService: loaded palette {name} ({img.size})", flush=True)
            else:
                self._palettes[name] = None

    def _find_texture_file(self, resref: str) -> Optional[Path]:
        """Find a texture file by resref (without extension), checking TGA then DDS then PLT."""
        resref_lower = resref.lower()
        for ext in [".tga", ".dds", ".plt"]:
            key = resref_lower + ext
            if key in self._resource_index:
                return self._resource_index[key]
        return None

    def _find_and_load_image(self, filename: str) -> Optional[Image.Image]:
        """Find and load an image from hak dirs or base game."""
        # Check hak resource index
        key = filename.lower()
        if key in self._resource_index:
            try:
                return Image.open(self._resource_index[key]).convert("RGBA")
            except Exception:
                pass

        # Fall back to nwn_resman_cat for base game resources
        return self._extract_from_resman(filename)

    def _extract_from_resman(self, filename: str) -> Optional[Image.Image]:
        """Extract a resource from the base game using nwn_resman_cat."""
        if not self.nwn_root_path or not self._resman_path.exists():
            return None

        try:
            result = subprocess.run(
                [str(self._resman_path), "--root", str(self.nwn_root_path), filename],
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout:
                return Image.open(io.BytesIO(result.stdout)).convert("RGBA")
        except Exception:
            pass
        return None

    def _extract_raw_from_resman(self, filename: str) -> Optional[bytes]:
        """Extract raw bytes from the base game using nwn_resman_cat."""
        if not self.nwn_root_path or not self._resman_path.exists():
            return None

        try:
            result = subprocess.run(
                [str(self._resman_path), "--root", str(self.nwn_root_path), filename],
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout:
                return result.stdout
        except Exception:
            pass
        return None

    def _get_icon_resref(self, base_item: int, part1: int, part2: int = 0, part3: int = 0) -> Optional[dict]:
        """Determine icon resref(s) from base item type and model parts.

        Returns dict with keys depending on model type:
        - ModelType 0 (simple): {"resref": "iit_torch_001"}
        - ModelType 1 (layered): {"resref": "ihelm_001", "format": "plt"}
        - ModelType 2 (composite): {"bottom": "iwswss_b_011", "middle": "iwswss_m_011", "top": "iwswss_t_011"}
        """
        info = self._baseitems.get(base_item)
        if not info or info["model_type"] is None:
            return None

        item_class = info["item_class"]
        if not item_class:
            return None

        model_type = info["model_type"]
        item_class_lower = item_class.lower()

        if model_type == 0:
            # Simple: i<ItemClass>_<NNN>.tga
            resref = f"i{item_class_lower}_{part1:03d}"
            return {"resref": resref, "model_type": 0}
        elif model_type == 1:
            # Layered: i<ItemClass>_<NNN>.plt
            resref = f"i{item_class_lower}_{part1:03d}"
            return {"resref": resref, "model_type": 1, "format": "plt"}
        elif model_type == 2:
            # Composite: i<ItemClass>_b/m/t_<NNN>.tga
            bottom = f"i{item_class_lower}_b_{part1:03d}"
            middle = f"i{item_class_lower}_m_{part2:03d}"
            top = f"i{item_class_lower}_t_{part3:03d}"
            return {"bottom": bottom, "middle": middle, "top": top, "model_type": 2}
        elif model_type == 3:
            # Armor - use DefaultIcon as fallback
            default_icon = info.get("default_icon")
            if default_icon:
                return {"resref": default_icon.lower(), "model_type": 3}
            return None

        return None

    def _load_texture(self, resref: str) -> Optional[Image.Image]:
        """Load a texture by resref, checking hak dirs then base game. Handles TGA, DDS, and PLT."""
        resref_lower = resref.lower()

        # Check for TGA first, then DDS, in hak index
        for ext in [".tga", ".dds"]:
            key = resref_lower + ext
            if key in self._resource_index:
                try:
                    return Image.open(self._resource_index[key]).convert("RGBA")
                except Exception:
                    continue

        # Check for PLT in hak index
        plt_key = resref_lower + ".plt"
        if plt_key in self._resource_index:
            return self._render_plt_file(self._resource_index[plt_key])

        # Fall back to base game resman
        for ext in [".tga", ".dds"]:
            img = self._extract_from_resman(resref_lower + ext)
            if img:
                return img

        # Try PLT from base game
        raw = self._extract_raw_from_resman(resref_lower + ".plt")
        if raw:
            return self._render_plt_bytes(raw)

        return None

    def _render_plt_bytes(self, data: bytes) -> Optional[Image.Image]:
        """Render PLT data from raw bytes to an RGBA image."""
        try:
            if len(data) < 24:
                return None
            # Header: "PLT V1  " (8 bytes), then unknown (8 bytes), width (4), height (4)
            header = data[:8]
            if header != b"PLT V1  ":
                return None

            width = struct.unpack_from("<I", data, 16)[0]
            height = struct.unpack_from("<I", data, 20)[0]

            pixel_data_start = 24
            expected_size = pixel_data_start + width * height * 2
            if len(data) < expected_size:
                return None

            return self._render_plt_pixels(data[pixel_data_start:], width, height)
        except Exception:
            return None

    def _render_plt_file(self, path: Path) -> Optional[Image.Image]:
        """Render a PLT file to an RGBA image."""
        try:
            with open(path, "rb") as f:
                data = f.read()
            return self._render_plt_bytes(data)
        except Exception:
            return None

    def _render_plt_pixels(self, pixel_data: bytes, width: int, height: int) -> Optional[Image.Image]:
        """Render PLT pixel data using palettes.

        Each pixel is 2 bytes: intensity (0-255) and layer index (0-9).
        The layer index selects which palette to use, and the intensity
        selects the column in the palette. The palette row is determined
        by the item's color fields (we use defaults here).
        """
        # Get the primary palette (armor palette covers metal layers well)
        palette = self._palettes.get("pal_armor01")

        img = Image.new("RGBA", (width, height))
        pixels = img.load()

        for y in range(height):
            for x in range(width):
                offset = (y * width + x) * 2
                intensity = pixel_data[offset]
                layer_idx = pixel_data[offset + 1]

                if palette and layer_idx < 10:
                    # Use palette: x=intensity, y=palette_row for this layer
                    layer_name = self.PLT_LAYERS[layer_idx] if layer_idx < len(self.PLT_LAYERS) else "skin"
                    palette_row = self.DEFAULT_PALETTE_ROWS.get(layer_name, 0)

                    pw, ph = palette.size
                    px = min(intensity, pw - 1)
                    py = min(palette_row, ph - 1)
                    color = palette.getpixel((px, py))

                    # Apply intensity as alpha modulation
                    if len(color) == 4:
                        pixels[x, height - 1 - y] = color
                    else:
                        pixels[x, height - 1 - y] = (*color[:3], 255)
                else:
                    # No palette - grayscale fallback
                    if intensity == 0:
                        pixels[x, height - 1 - y] = (0, 0, 0, 0)
                    else:
                        pixels[x, height - 1 - y] = (intensity, intensity, intensity, 255)

        return img

    def _assemble_composite(self, bottom: Optional[Image.Image], middle: Optional[Image.Image], top: Optional[Image.Image]) -> Optional[Image.Image]:
        """Assemble a composite icon from bottom/middle/top layers."""
        parts = [p for p in [bottom, middle, top] if p is not None]
        if not parts:
            return None

        # Use the size of the first available part
        size = parts[0].size
        result = Image.new("RGBA", size, (0, 0, 0, 0))

        for part in parts:
            if part.size != size:
                part = part.resize(size, Image.LANCZOS)
            result = Image.alpha_composite(result, part)

        return result

    def _image_to_png_bytes(self, img: Image.Image) -> bytes:
        """Convert a PIL Image to PNG bytes."""
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    @lru_cache(maxsize=2000)
    def get_icon_png(self, base_item: int, part1: int, part2: int = 0, part3: int = 0) -> Optional[bytes]:
        """Get the icon PNG bytes for an item based on its base type and model parts.

        Returns PNG bytes or None if no icon could be found.
        """
        icon_info = self._get_icon_resref(base_item, part1, part2, part3)
        if not icon_info:
            # Try DefaultIcon fallback
            info = self._baseitems.get(base_item)
            if info and info.get("default_icon"):
                img = self._load_texture(info["default_icon"])
                if img:
                    return self._image_to_png_bytes(img)
            return None

        model_type = icon_info.get("model_type")

        if model_type == 2:
            # Composite: load and assemble three layers
            bottom = self._load_texture(icon_info["bottom"])
            middle = self._load_texture(icon_info["middle"])
            top = self._load_texture(icon_info["top"])
            result = self._assemble_composite(bottom, middle, top)
            if result:
                return self._image_to_png_bytes(result)
            # Fall back to bottom only
            if bottom:
                return self._image_to_png_bytes(bottom)
        else:
            # Simple, layered, or armor
            resref = icon_info.get("resref")
            if resref:
                img = self._load_texture(resref)
                if img:
                    return self._image_to_png_bytes(img)

        # Final fallback: DefaultIcon
        info = self._baseitems.get(base_item)
        if info and info.get("default_icon"):
            img = self._load_texture(info["default_icon"])
            if img:
                return self._image_to_png_bytes(img)

        return None

    def get_default_icon_png(self, base_item: int) -> Optional[bytes]:
        """Get the default icon for a base item type (part1=1)."""
        info = self._baseitems.get(base_item)
        if not info:
            return None

        # Try DefaultIcon field first
        if info.get("default_icon"):
            img = self._load_texture(info["default_icon"])
            if img:
                return self._image_to_png_bytes(img)

        # Try with part1=1
        return self.get_icon_png(base_item, 1, 1, 1)

    def list_available_parts(self, base_item: int) -> Optional[dict]:
        """List available icon part numbers for a base item type.

        Returns a dict with model_type and available parts information.
        """
        info = self._baseitems.get(base_item)
        if not info or info["model_type"] is None:
            return None

        model_type = info["model_type"]
        item_class = info.get("item_class")
        if not item_class:
            return None

        item_class_lower = item_class.lower()
        min_range = info["min_range"]
        max_range = info["max_range"]

        if model_type == 0:
            # Simple: scan for i<ItemClass>_NNN.tga/dds
            parts = self._scan_parts(f"i{item_class_lower}_", min_range, max_range)
            return {"model_type": 0, "parts": parts}

        elif model_type == 1:
            # Layered: scan for i<ItemClass>_NNN.plt
            parts = self._scan_parts(f"i{item_class_lower}_", min_range, max_range, extensions=[".plt"])
            return {"model_type": 1, "parts": parts}

        elif model_type == 2:
            # Composite: scan bottom/middle/top separately
            bottom_parts = self._scan_parts(f"i{item_class_lower}_b_", min_range, max_range)
            middle_parts = self._scan_parts(f"i{item_class_lower}_m_", min_range, max_range)
            top_parts = self._scan_parts(f"i{item_class_lower}_t_", min_range, max_range)
            return {
                "model_type": 2,
                "bottom_parts": bottom_parts,
                "middle_parts": middle_parts,
                "top_parts": top_parts,
            }

        elif model_type == 3:
            # Armor - just return the default icon info
            return {"model_type": 3, "default_icon": info.get("default_icon")}

        return None

    def _scan_parts(
        self,
        prefix: str,
        min_range: int,
        max_range: int,
        extensions: Optional[List[str]] = None,
    ) -> List[int]:
        """Scan the resource index for available part numbers matching a prefix pattern."""
        if extensions is None:
            extensions = [".tga", ".dds", ".plt"]

        found_parts = set()
        prefix_lower = prefix.lower()

        for key in self._resource_index:
            if not key.startswith(prefix_lower):
                continue
            # Extract the part number from the filename
            # Pattern: prefix + NNN + extension
            remainder = key[len(prefix_lower):]
            for ext in extensions:
                if remainder.endswith(ext):
                    num_str = remainder[:-len(ext)]
                    try:
                        num = int(num_str)
                        if min_range <= num <= max_range:
                            found_parts.add(num)
                    except ValueError:
                        continue

        # Also check base game via resman for a sample of part numbers
        # (only if we have few results from haks)
        if len(found_parts) < 5 and self.nwn_root_path and self._resman_path.exists():
            for num in range(min_range, min(max_range + 1, min_range + 30)):
                if num in found_parts:
                    continue
                for ext in extensions:
                    filename = f"{prefix_lower}{num:03d}{ext}"
                    raw = self._extract_raw_from_resman(filename)
                    if raw:
                        found_parts.add(num)
                        break

        return sorted(found_parts)

    def get_preview_png(self, base_item: int, part1: int, part2: int = 0, part3: int = 0) -> Optional[bytes]:
        """Get a preview icon for specific part numbers (bypasses the main cache key)."""
        return self.get_icon_png(base_item, part1, part2, part3)
