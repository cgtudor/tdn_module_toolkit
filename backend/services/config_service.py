"""Configuration service for managing tool settings."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional
from pydantic import BaseModel


def _get_config_dir() -> Path:
    """Get the appropriate config directory based on execution mode."""
    if getattr(sys, 'frozen', False):
        # In bundled mode, use user's app data directory
        app_data = os.environ.get('APPDATA') or os.path.expanduser('~')
        config_dir = Path(app_data) / 'TDN Module Toolkit'
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir
    # In development, use backend directory
    return Path(__file__).parent.parent


class ConfigData(BaseModel):
    """Configuration data model."""
    source_mode: str = "json_directory"  # "json_directory" or "mod_file"
    module_path: str = ""
    mod_file_path: str = ""  # Path to .mod file (MOD mode only)
    custom_tlk_path: str = ""
    base_tlk_path: str = ""
    tda_folder_path: str = ""  # Folder containing all 2DA files
    # Individual paths (auto-populated from folder)
    baseitems_2da_path: str = ""
    itemprops_2da_path: str = ""
    racialtypes_2da_path: str = ""
    appearance_2da_path: str = ""
    hak_source_path: str = ""  # Path to TDN_Haks directory (for item icons)
    nwn_root_path: str = ""  # Path to NWN:EE installation (for base game icons)
    configured: bool = False


class ConfigService:
    """Service for managing application configuration."""

    _RAW_DEFAULT_PATHS = {
        "module_path": r"D:\tdn\workspace\tdn_gff\module",
        "mod_file_path": r"D:\Neverwinter Nights\modules\tdn_build.mod",
        "custom_tlk_path": r"D:\tdn\workspace\TDN_Haks\tlk\dragonsneck.tlk",
        "base_tlk_path": r"D:\tdn\workspace\TDN_Haks\tlk\dialog.tlk",
        "tda_folder_path": r"D:\tdn\workspace\TDN_Haks\tdn_2da",
        "baseitems_2da_path": r"D:\tdn\workspace\TDN_Haks\tdn_2da\baseitems.2da",
        "itemprops_2da_path": r"D:\tdn\workspace\TDN_Haks\tdn_2da\itemprops.2da",
        "racialtypes_2da_path": r"D:\tdn\workspace\TDN_Haks\tdn_2da\racialtypes.2da",
        "appearance_2da_path": r"D:\tdn\workspace\TDN_Haks\tdn_2da\appearance.2da",
        "hak_source_path": r"D:\tdn\workspace\TDN_Haks",
        "nwn_root_path": r"C:\Games\Steam\steamapps\common\Neverwinter Nights",
    }

    @classmethod
    def get_default_config(cls) -> ConfigData:
        """Build default config, clearing paths that don't exist on disk."""
        paths = {}
        for key, value in cls._RAW_DEFAULT_PATHS.items():
            if value and not Path(value).exists():
                paths[key] = ""
            else:
                paths[key] = value
        return ConfigData(**paths, configured=False)

    # Required 2DA files that should be in the folder
    REQUIRED_2DA_FILES = ["baseitems.2da", "itemprops.2da", "racialtypes.2da", "appearance.2da"]

    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize config service.

        Args:
            config_dir: Directory for config file. Defaults to app data in frozen mode,
                       or backend directory in development.
        """
        if config_dir is None:
            config_dir = _get_config_dir()
        self.config_dir = Path(config_dir)
        self.config_path = self.config_dir / "config.json"
        self.tlk_dir = self.config_dir / "tlk"
        self._config: Optional[ConfigData] = None
        print(f"ConfigService: config_path={self.config_path}", flush=True)

    def get_config(self) -> ConfigData:
        """Get current configuration, loading from file if needed."""
        if self._config is None:
            self._config = self._load_config()
        return self._config

    def reload_config(self):
        """Force re-read configuration from disk."""
        self._config = self._load_config()

    def _load_config(self) -> ConfigData:
        """Load configuration from file."""
        if not self.config_path.exists():
            return self.get_default_config()

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Migration: if we have baseitems_2da_path but no tda_folder_path,
            # derive the folder path from the file path
            if data.get('baseitems_2da_path') and not data.get('tda_folder_path'):
                baseitems_path = Path(data['baseitems_2da_path'])
                if baseitems_path.exists():
                    data['tda_folder_path'] = str(baseitems_path.parent)
                    print(f"Migrated tda_folder_path from baseitems_2da_path: {data['tda_folder_path']}")

            # Migration: fill in new icon-related paths from defaults if missing
            for key in ('hak_source_path', 'nwn_root_path'):
                if not data.get(key) and key in cls._RAW_DEFAULT_PATHS:
                    default_val = cls._RAW_DEFAULT_PATHS[key]
                    if default_val and Path(default_val).exists():
                        data[key] = default_val
                        print(f"Migrated {key} from default: {default_val}")

            return ConfigData(**data)
        except (json.JSONDecodeError, Exception) as e:
            print(f"Error loading config: {e}")
            return self.get_default_config()

    def save_config(self, config: ConfigData) -> bool:
        """Save configuration to file."""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config.model_dump(), f, indent=2)
            self._config = config
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False

    def is_configured(self) -> bool:
        """Check if tool has been configured."""
        config = self.get_config()
        return config.configured

    def validate_paths(self, config: ConfigData) -> dict:
        """Validate all paths in configuration.

        Returns:
            Dict with validation results for each path.
        """
        results = {
            "module_path": {
                "valid": False,
                "message": ""
            },
            "mod_file_path": {
                "valid": False,
                "message": ""
            },
            "custom_tlk_path": {
                "valid": False,
                "message": ""
            },
            "base_tlk_path": {
                "valid": False,
                "message": ""
            },
            "tda_folder_path": {
                "valid": False,
                "message": "",
                "found_files": []
            }
        }

        is_mod_mode = config.source_mode == "mod_file"

        # Validate module path (required in json_directory mode only)
        if is_mod_mode:
            results["module_path"]["valid"] = True
            results["module_path"]["message"] = "Not required in MOD file mode"
        elif config.module_path:
            module_path = Path(config.module_path)
            if module_path.exists() and module_path.is_dir():
                uti_path = module_path / "uti"
                if uti_path.exists():
                    results["module_path"]["valid"] = True
                    results["module_path"]["message"] = "Valid module directory"
                else:
                    results["module_path"]["message"] = "Module directory missing 'uti' folder"
            else:
                results["module_path"]["message"] = "Directory does not exist"
        else:
            results["module_path"]["message"] = "Path is required"

        # Validate mod file path (required in mod_file mode only)
        if not is_mod_mode:
            results["mod_file_path"]["valid"] = True
            results["mod_file_path"]["message"] = "Not required in JSON directory mode"
        elif config.mod_file_path:
            mod_path = Path(config.mod_file_path)
            if mod_path.exists() and mod_path.is_file():
                if mod_path.suffix.lower() == ".mod":
                    results["mod_file_path"]["valid"] = True
                    results["mod_file_path"]["message"] = "Valid .mod file"
                else:
                    results["mod_file_path"]["message"] = "File must have .mod extension"
            else:
                results["mod_file_path"]["message"] = "File does not exist"
        else:
            results["mod_file_path"]["message"] = "Path is required"

        # Validate custom TLK path
        if config.custom_tlk_path:
            tlk_path = Path(config.custom_tlk_path)
            if tlk_path.exists():
                if tlk_path.suffix == ".json":
                    results["custom_tlk_path"]["valid"] = True
                    results["custom_tlk_path"]["message"] = "Valid TLK JSON file"
                elif tlk_path.suffix == ".tlk":
                    results["custom_tlk_path"]["valid"] = True
                    results["custom_tlk_path"]["message"] = "TLK file (will be converted to JSON)"
                else:
                    results["custom_tlk_path"]["message"] = "Must be .tlk or .tlk.json file"
            else:
                results["custom_tlk_path"]["message"] = "File does not exist"
        else:
            # Custom TLK is optional
            results["custom_tlk_path"]["valid"] = True
            results["custom_tlk_path"]["message"] = "Optional (not set)"

        # Validate base TLK path
        if config.base_tlk_path:
            tlk_path = Path(config.base_tlk_path)
            if tlk_path.exists():
                if tlk_path.suffix == ".json":
                    results["base_tlk_path"]["valid"] = True
                    results["base_tlk_path"]["message"] = "Valid TLK JSON file"
                elif tlk_path.suffix == ".tlk":
                    results["base_tlk_path"]["valid"] = True
                    results["base_tlk_path"]["message"] = "TLK file (will be converted to JSON)"
                else:
                    results["base_tlk_path"]["message"] = "Must be .tlk or .tlk.json file"
            else:
                results["base_tlk_path"]["message"] = "File does not exist"
        else:
            # Check if we have a local copy
            local_tlk = self.tlk_dir / "dialog.tlk.json"
            if local_tlk.exists():
                results["base_tlk_path"]["valid"] = True
                results["base_tlk_path"]["message"] = "Using local copy"
            else:
                results["base_tlk_path"]["valid"] = True
                results["base_tlk_path"]["message"] = "Optional (not set)"

        # Validate 2DA folder path
        if config.tda_folder_path:
            tda_folder = Path(config.tda_folder_path)
            if tda_folder.exists() and tda_folder.is_dir():
                # Check for required 2DA files
                found_files = []
                missing_files = []
                for filename in self.REQUIRED_2DA_FILES:
                    file_path = tda_folder / filename
                    if file_path.exists():
                        found_files.append(filename)
                    else:
                        missing_files.append(filename)

                results["tda_folder_path"]["found_files"] = found_files

                if missing_files:
                    results["tda_folder_path"]["message"] = f"Missing: {', '.join(missing_files)}"
                else:
                    results["tda_folder_path"]["valid"] = True
                    results["tda_folder_path"]["message"] = f"Found all required 2DA files ({len(found_files)} files)"
            else:
                results["tda_folder_path"]["message"] = "Directory does not exist"
        else:
            results["tda_folder_path"]["message"] = "Path is required for item categorization"

        return results

    def populate_2da_paths_from_folder(self, config: ConfigData) -> ConfigData:
        """Populate individual 2DA paths from the folder path.

        Args:
            config: Configuration with tda_folder_path set

        Returns:
            Updated configuration with individual 2DA paths
        """
        updated = config.model_copy()

        if config.tda_folder_path:
            folder = Path(config.tda_folder_path)
            if folder.exists() and folder.is_dir():
                baseitems = folder / "baseitems.2da"
                itemprops = folder / "itemprops.2da"
                racialtypes = folder / "racialtypes.2da"
                appearance = folder / "appearance.2da"

                if baseitems.exists():
                    updated.baseitems_2da_path = str(baseitems)
                if itemprops.exists():
                    updated.itemprops_2da_path = str(itemprops)
                if racialtypes.exists():
                    updated.racialtypes_2da_path = str(racialtypes)
                if appearance.exists():
                    updated.appearance_2da_path = str(appearance)

        return updated

    def browse_directory(self, start_path: Optional[str] = None) -> dict:
        """Get directory contents for browsing.

        Args:
            start_path: Directory to list. Defaults to user's home directory.

        Returns:
            Dict with current path, parent path, and list of entries.
        """
        if start_path:
            current = Path(start_path)
            if not current.exists():
                current = Path.home()
        else:
            current = Path.home()

        # Ensure it's a directory
        if current.is_file():
            current = current.parent

        entries = []
        try:
            for entry in sorted(current.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                try:
                    entries.append({
                        "name": entry.name,
                        "path": str(entry),
                        "is_dir": entry.is_dir(),
                        "is_file": entry.is_file()
                    })
                except PermissionError:
                    continue
        except PermissionError:
            pass

        # Get drives on Windows
        drives = []
        if os.name == 'nt':
            import string
            for letter in string.ascii_uppercase:
                drive = f"{letter}:\\"
                if Path(drive).exists():
                    drives.append(drive)

        return {
            "current_path": str(current),
            "parent_path": str(current.parent) if current.parent != current else None,
            "entries": entries,
            "drives": drives
        }

    def setup_tlk_files(self, config: ConfigData) -> ConfigData:
        """Setup TLK files, converting and copying as needed.

        Args:
            config: Configuration with TLK paths

        Returns:
            Updated configuration with resolved TLK paths
        """
        # Ensure TLK directory exists
        self.tlk_dir.mkdir(exist_ok=True)

        updated_config = config.model_copy()

        # Handle base TLK
        if config.base_tlk_path:
            base_tlk = Path(config.base_tlk_path)
            if base_tlk.exists():
                dest_path = self.tlk_dir / "dialog.tlk.json"
                if base_tlk.suffix == ".tlk":
                    # Need to convert
                    if self._convert_tlk_to_json(base_tlk, dest_path):
                        updated_config.base_tlk_path = str(dest_path)
                elif base_tlk.resolve() != dest_path.resolve():
                    # Already JSON, copy to local (skip if already there)
                    shutil.copy2(base_tlk, dest_path)
                    updated_config.base_tlk_path = str(dest_path)
                else:
                    # Already in the right place
                    updated_config.base_tlk_path = str(dest_path)
        else:
            # Check for existing local copy
            local_tlk = self.tlk_dir / "dialog.tlk.json"
            if local_tlk.exists():
                updated_config.base_tlk_path = str(local_tlk)

        # Handle custom TLK (dragonsneck.tlk)
        if config.custom_tlk_path:
            custom_tlk = Path(config.custom_tlk_path)
            if custom_tlk.exists():
                dest_path = self.tlk_dir / "dragonsneck.tlk.json"
                if custom_tlk.suffix == ".tlk":
                    # Need to convert
                    if self._convert_tlk_to_json(custom_tlk, dest_path):
                        updated_config.custom_tlk_path = str(dest_path)
                elif custom_tlk.resolve() != dest_path.resolve():
                    # Already JSON, copy to local (skip if already there)
                    shutil.copy2(custom_tlk, dest_path)
                    updated_config.custom_tlk_path = str(dest_path)
                else:
                    # Already in the right place
                    updated_config.custom_tlk_path = str(dest_path)

        return updated_config

    def _convert_tlk_to_json(self, tlk_path: Path, json_path: Path) -> bool:
        """Convert binary TLK file to JSON using nwn_tlk tool.

        Args:
            tlk_path: Path to binary TLK file
            json_path: Path for output JSON file

        Returns:
            True if conversion successful
        """
        try:
            # Try nwn_tlk (neverwinter.nim tools)
            result = subprocess.run(
                ["nwn_tlk", "-i", str(tlk_path), "-o", str(json_path)],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return True
            print(f"nwn_tlk conversion failed: {result.stderr}")
        except FileNotFoundError:
            print("nwn_tlk not found, TLK conversion not available")
        except Exception as e:
            print(f"TLK conversion error: {e}")

        return False

    def apply_configuration(self, config: ConfigData) -> tuple[bool, str]:
        """Apply and save configuration.

        Args:
            config: Configuration to apply

        Returns:
            Tuple of (success, message)
        """
        # Validate paths first
        validation = self.validate_paths(config)

        # Check critical paths based on mode
        if config.source_mode == "mod_file":
            if not validation["mod_file_path"]["valid"]:
                return False, f"MOD file path invalid: {validation['mod_file_path']['message']}"
        else:
            if not validation["module_path"]["valid"]:
                return False, f"Module path invalid: {validation['module_path']['message']}"

        if not validation["tda_folder_path"]["valid"]:
            return False, f"2DA folder invalid: {validation['tda_folder_path']['message']}"

        # Populate individual 2DA paths from folder
        updated_config = self.populate_2da_paths_from_folder(config)

        # Setup TLK files (copy/convert as needed)
        try:
            updated_config = self.setup_tlk_files(updated_config)
        except Exception as e:
            return False, f"Failed to setup TLK files: {e}"

        # Mark as configured and save
        updated_config.configured = True
        if self.save_config(updated_config):
            return True, "Configuration saved successfully"
        else:
            return False, "Failed to save configuration"

    def get_base_tlk_json_path(self) -> Optional[Path]:
        """Get path to base TLK JSON file (dialog.tlk.json)."""
        config = self.get_config()
        if config.base_tlk_path:
            path = Path(config.base_tlk_path)
            if path.exists():
                return path

        # Check local copy
        local_path = self.tlk_dir / "dialog.tlk.json"
        if local_path.exists():
            return local_path

        return None

    def get_custom_tlk_json_path(self) -> Optional[Path]:
        """Get path to custom TLK JSON file (dragonsneck.tlk.json)."""
        config = self.get_config()
        if config.custom_tlk_path:
            path = Path(config.custom_tlk_path)
            if path.exists():
                return path

        # Check local copy
        local_path = self.tlk_dir / "dragonsneck.tlk.json"
        if local_path.exists():
            return local_path

        return None

    def get_baseitems_2da_path(self) -> Optional[Path]:
        """Get path to baseitems.2da file."""
        config = self.get_config()
        if config.baseitems_2da_path:
            path = Path(config.baseitems_2da_path)
            if path.exists():
                return path
        return None

    def get_itemprops_2da_path(self) -> Optional[Path]:
        """Get path to itemprops.2da file."""
        config = self.get_config()
        if config.itemprops_2da_path:
            path = Path(config.itemprops_2da_path)
            if path.exists():
                return path
        return None

    def get_racialtypes_2da_path(self) -> Optional[Path]:
        """Get path to racialtypes.2da file."""
        config = self.get_config()
        if config.racialtypes_2da_path:
            path = Path(config.racialtypes_2da_path)
            if path.exists():
                return path
        return None

    def get_appearance_2da_path(self) -> Optional[Path]:
        """Get path to appearance.2da file."""
        config = self.get_config()
        if config.appearance_2da_path:
            path = Path(config.appearance_2da_path)
            if path.exists():
                return path
        return None

    def get_tda_folder_path(self) -> Optional[Path]:
        """Get path to folder containing all 2DA files."""
        config = self.get_config()
        if config.tda_folder_path:
            path = Path(config.tda_folder_path)
            if path.exists() and path.is_dir():
                return path
        return None

    def get_hak_source_path(self) -> Optional[Path]:
        """Get path to TDN_Haks directory (for item icons)."""
        config = self.get_config()
        if config.hak_source_path:
            path = Path(config.hak_source_path)
            if path.exists() and path.is_dir():
                return path
        return None

    def get_nwn_root_path(self) -> Optional[Path]:
        """Get path to NWN:EE installation directory."""
        config = self.get_config()
        if config.nwn_root_path:
            path = Path(config.nwn_root_path)
            if path.exists() and path.is_dir():
                return path
        return None
