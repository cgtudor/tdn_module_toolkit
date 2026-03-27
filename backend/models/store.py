from pydantic import BaseModel
from typing import Optional, List, Any


# Store category constants
# In NWN stores, the category is determined by the ARRAY INDEX in StoreList, not __struct_id
# StoreList[0] = Armor
# StoreList[1] = Weapons (melee, ranged, AND ammunition)
# StoreList[2] = Potions/Scrolls
# StoreList[3] = Magic Items (wands, staves, rods)
# StoreList[4] = Miscellaneous
class StoreCategories:
    ARMOR = 0           # Clothing and Armor
    WEAPONS = 1         # Weapons (melee, ranged, AND ammunition)
    POTIONS_SCROLLS = 2 # Scrolls and Potions
    MAGIC_ITEMS = 3     # Magic Items (wands, staves, rods)
    MISCELLANEOUS = 4   # Miscellaneous

    @classmethod
    def get_name(cls, cat_id: int) -> str:
        names = {
            0: "Armor",
            1: "Weapons",
            2: "Potions/Scrolls",
            3: "Magic Items",
            4: "Miscellaneous"
        }
        return names.get(cat_id, f"Unknown ({cat_id})")

    @classmethod
    def all_categories(cls) -> List[int]:
        return [0, 1, 2, 3, 4]


# StorePanel values from baseitems.2da directly correspond to store categories:
#   0 = Armor and Clothing
#   1 = Weapons
#   2 = Potions and Scrolls
#   3 = Wands and Magic Items
#   4 = Miscellaneous


def get_category_from_store_panel(store_panel: Optional[int]) -> int:
    """Get display category from StorePanel value.

    The StorePanel value from baseitems.2da directly corresponds to
    the store category index (0-4).

    Args:
        store_panel: StorePanel value from baseitems.2da

    Returns:
        Category ID (0-4), defaults to 4 (Miscellaneous) if unknown
    """
    if store_panel is None:
        return StoreCategories.MISCELLANEOUS
    # StorePanel value IS the category (0-4)
    if 0 <= store_panel <= 4:
        return store_panel
    return StoreCategories.MISCELLANEOUS


class StoreItem(BaseModel):
    """Represents an item in a store inventory."""
    index: int
    resref: str
    name: str
    infinite: bool = False
    stack_size: int = 1
    repos_x: int = 0
    repos_y: int = 0
    base_item: Optional[int] = None
    inv_slot_width: int = 1
    inv_slot_height: int = 1
    item_data: Optional[dict] = None


class StoreCategory(BaseModel):
    """Represents a store category with its items."""
    category_id: int
    category_name: str
    items: List[StoreItem] = []


class StoreSettings(BaseModel):
    """Store configuration settings."""
    markup: int = 100
    markdown: int = 100
    max_buy_price: int = -1
    store_gold: int = -1
    identify_price: int = 100
    black_market: bool = False
    bm_markdown: int = 25
    will_not_buy: List[int] = []
    will_only_buy: List[int] = []


class StoreSummary(BaseModel):
    """Summary info for store list views."""
    resref: str
    name: str
    markup: int
    markdown: int
    max_buy_price: int
    store_gold: int
    item_count: int


class StoreDetail(BaseModel):
    """Full store details including inventory and settings."""
    resref: str
    name: str
    tag: str
    settings: StoreSettings
    categories: List[StoreCategory] = []
    raw_data: Optional[dict] = None


class StoreSettingsUpdate(BaseModel):
    """Model for updating store settings."""
    markup: Optional[int] = None
    markdown: Optional[int] = None
    max_buy_price: Optional[int] = None
    store_gold: Optional[int] = None
    identify_price: Optional[int] = None
    black_market: Optional[bool] = None
    bm_markdown: Optional[int] = None
    will_not_buy: Optional[List[int]] = None
    will_only_buy: Optional[List[int]] = None


class StoreItemAdd(BaseModel):
    """Model for adding item to store."""
    item_resref: str
    infinite: bool = False
    stack_size: int = 1


class StoreItemUpdate(BaseModel):
    """Model for updating store item."""
    infinite: Optional[bool] = None
    stack_size: Optional[int] = None
    cost: Optional[int] = None
    identified: Optional[bool] = None
    repos_x: Optional[int] = None
    repos_y: Optional[int] = None


class StoreItemAddAuto(BaseModel):
    """Model for adding item to store with auto-categorization."""
    item_resref: str
    infinite: bool = False
    stack_size: int = 1


class StoreItemAddResult(BaseModel):
    """Result of adding item to store."""
    success: bool
    item_resref: str
    category_id: int
    category_name: str
    base_item: int
    store_panel: Optional[int] = None
