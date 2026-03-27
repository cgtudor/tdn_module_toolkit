from pydantic import BaseModel
from typing import Optional, List, Any


# Equipment slot constants matching NWN __struct_id values (bitmasks)
# Reference: nwscript.nss lines 61-64
class EquipmentSlots:
    HEAD = 1
    CHEST = 2
    BOOTS = 4
    ARMS = 8
    RIGHT_HAND = 16
    LEFT_HAND = 32
    CLOAK = 64
    LEFT_RING = 128
    RIGHT_RING = 256
    NECK = 512
    BELT = 1024
    ARROWS = 2048
    BULLETS = 4096
    BOLTS = 8192
    # Creature-specific slots (slot indices 14-17)
    CREATURE_WEAPON_L = 16384   # Slot 14: Creature Left Weapon
    CREATURE_WEAPON_R = 32768   # Slot 15: Creature Right Weapon
    CREATURE_WEAPON_B = 65536   # Slot 16: Creature Bite Weapon
    CREATURE_ARMOUR = 131072    # Slot 17: Creature Armour

    @classmethod
    def get_name(cls, slot_id: int) -> str:
        names = {
            1: "Head",
            2: "Chest",
            4: "Boots",
            8: "Arms",
            16: "Right Hand",
            32: "Left Hand",
            64: "Cloak",
            128: "Left Ring",
            256: "Right Ring",
            512: "Neck",
            1024: "Belt",
            2048: "Arrows",
            4096: "Bullets",
            8192: "Bolts",
            16384: "Creature Left Weapon",
            32768: "Creature Right Weapon",
            65536: "Creature Bite Weapon",
            131072: "Creature Armour"
        }
        return names.get(slot_id, f"Unknown ({slot_id})")

    @classmethod
    def all_slots(cls) -> List[int]:
        return [1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384, 32768, 65536, 131072]


class EquipmentSlot(BaseModel):
    """Represents an equipment slot on a creature."""
    slot_id: int
    slot_name: str
    item_resref: Optional[str] = None
    item_name: Optional[str] = None
    item_data: Optional[dict] = None


class InventoryItem(BaseModel):
    """Represents an item in creature inventory."""
    index: int
    resref: str
    name: str
    stack_size: int = 1
    repos_x: int = 0
    repos_y: int = 0
    item_data: Optional[dict] = None


class CreatureSummary(BaseModel):
    """Summary info for creature list views."""
    resref: str
    first_name: str
    last_name: str
    display_name: str
    race: int
    appearance: int
    equipment_count: int
    inventory_count: int


class CreatureDetail(BaseModel):
    """Full creature details including equipment and inventory."""
    resref: str
    first_name: str
    last_name: str
    tag: str
    race: int
    race_name: Optional[str] = None
    subrace: Optional[str] = None
    appearance: int
    appearance_name: Optional[str] = None
    faction_id: int = 0
    faction_name: Optional[str] = None
    gender: int = 0
    portrait: Optional[str] = None
    equipment: List[EquipmentSlot] = []
    inventory: List[InventoryItem] = []
    raw_data: Optional[dict] = None


class EquipmentUpdate(BaseModel):
    """Model for setting equipment slot."""
    item_resref: str


class InventoryAdd(BaseModel):
    """Model for adding item to inventory."""
    item_resref: str
    stack_size: int = 1
    repos_x: Optional[int] = None
    repos_y: Optional[int] = None
