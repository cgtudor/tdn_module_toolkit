from pydantic import BaseModel
from typing import Optional, List, Any
from models.store import StoreSettings, StoreCategory
from models.creature import EquipmentSlot, InventoryItem


class AreaSummary(BaseModel):
    """Summary info for area list views."""
    resref: str
    name: str
    store_count: int
    creature_count: int


class StoreInstance(BaseModel):
    """A store instance embedded in a GIT file."""
    index: int
    resref: str
    template_resref: Optional[str] = None
    tag: str
    name: str
    x: float
    y: float
    z: float
    settings: StoreSettings
    categories: List[StoreCategory] = []
    raw_data: Optional[dict] = None


class CreatureInstance(BaseModel):
    """A creature instance embedded in a GIT file."""
    index: int
    resref: str
    template_resref: Optional[str] = None
    tag: str
    first_name: str
    last_name: str
    x: float
    y: float
    z: float
    equipment: List[EquipmentSlot] = []
    inventory: List[InventoryItem] = []
    raw_data: Optional[dict] = None


class InstancePosition(BaseModel):
    """Position update for an instance."""
    x: float
    y: float
    z: float


class SyncResult(BaseModel):
    """Result of syncing instance from template."""
    success: bool
    message: str
    changes_made: List[str] = []
