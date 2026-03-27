"""Configuration API endpoints."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from services.config_service import ConfigService, ConfigData

router = APIRouter(prefix="/api/config", tags=["config"])

# Injected by main.py
config_service: ConfigService = None


def init(cfg_service: ConfigService):
    global config_service
    config_service = cfg_service


class ConfigUpdateRequest(BaseModel):
    """Request model for updating configuration."""
    source_mode: str = "json_directory"
    module_path: str = ""
    mod_file_path: str = ""
    custom_tlk_path: Optional[str] = ""
    base_tlk_path: Optional[str] = ""
    tda_folder_path: str = ""
    hak_source_path: Optional[str] = ""
    nwn_root_path: Optional[str] = ""


class ValidationRequest(BaseModel):
    """Request model for validating paths."""
    source_mode: str = "json_directory"
    module_path: str = ""
    mod_file_path: str = ""
    custom_tlk_path: Optional[str] = ""
    base_tlk_path: Optional[str] = ""
    tda_folder_path: str = ""
    hak_source_path: Optional[str] = ""
    nwn_root_path: Optional[str] = ""


class BrowseRequest(BaseModel):
    """Request model for browsing directories."""
    path: Optional[str] = None


@router.get("")
async def get_config():
    """Get current configuration."""
    config = config_service.get_config()
    return {
        "source_mode": config.source_mode,
        "module_path": config.module_path,
        "mod_file_path": config.mod_file_path,
        "custom_tlk_path": config.custom_tlk_path,
        "base_tlk_path": config.base_tlk_path,
        "tda_folder_path": config.tda_folder_path,
        "hak_source_path": config.hak_source_path,
        "nwn_root_path": config.nwn_root_path,
        "configured": config.configured
    }


@router.get("/status")
async def get_config_status():
    """Get configuration status (is configured, validation results)."""
    config = config_service.get_config()
    validation = config_service.validate_paths(config)

    return {
        "configured": config.configured,
        "validation": validation
    }


@router.post("/validate")
async def validate_config(request: ValidationRequest):
    """Validate configuration paths without saving."""
    config = ConfigData(
        source_mode=request.source_mode,
        module_path=request.module_path,
        mod_file_path=request.mod_file_path,
        custom_tlk_path=request.custom_tlk_path or "",
        base_tlk_path=request.base_tlk_path or "",
        tda_folder_path=request.tda_folder_path,
        hak_source_path=request.hak_source_path or "",
        nwn_root_path=request.nwn_root_path or "",
        configured=False
    )

    validation = config_service.validate_paths(config)

    # Check if all required paths are valid
    all_valid = (
        validation["module_path"]["valid"] and
        validation["mod_file_path"]["valid"] and
        validation["tda_folder_path"]["valid"] and
        validation["custom_tlk_path"]["valid"]
        # base_tlk is optional
    )

    return {
        "valid": all_valid,
        "validation": validation
    }


@router.post("/save")
async def save_config(request: ConfigUpdateRequest):
    """Save configuration and apply settings."""
    config = ConfigData(
        source_mode=request.source_mode,
        module_path=request.module_path,
        mod_file_path=request.mod_file_path,
        custom_tlk_path=request.custom_tlk_path or "",
        base_tlk_path=request.base_tlk_path or "",
        tda_folder_path=request.tda_folder_path,
        hak_source_path=request.hak_source_path or "",
        nwn_root_path=request.nwn_root_path or "",
        configured=False
    )

    success, message = config_service.apply_configuration(config)

    if not success:
        raise HTTPException(status_code=400, detail=message)

    return {
        "success": True,
        "message": message,
        "config": config_service.get_config().model_dump()
    }


@router.get("/defaults")
async def get_default_config():
    """Get default configuration values."""
    defaults = ConfigService.get_default_config()
    return {
        "source_mode": defaults.source_mode,
        "module_path": defaults.module_path,
        "mod_file_path": defaults.mod_file_path,
        "custom_tlk_path": defaults.custom_tlk_path,
        "base_tlk_path": defaults.base_tlk_path,
        "tda_folder_path": defaults.tda_folder_path,
        "hak_source_path": defaults.hak_source_path,
        "nwn_root_path": defaults.nwn_root_path
    }


@router.post("/browse")
async def browse_directory(request: BrowseRequest):
    """Browse directory contents for file/folder selection."""
    return config_service.browse_directory(request.path)
