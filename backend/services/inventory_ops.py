"""Inventory manipulation operations."""
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from services.gff_service import GFFService
from models.creature import EquipmentSlots, EquipmentSlot, InventoryItem
from models.store import (
    StoreCategories, StoreItem, StoreSettings, get_category_from_store_panel
)

if TYPE_CHECKING:
    from services.tda_service import TDAService


class InventoryOperations:
    """Operations for manipulating creature and store inventories."""

    def __init__(self, gff_service: GFFService, tda_service: Optional["TDAService"] = None):
        self.gff = gff_service
        self.tda = tda_service

    # ===== Creature Equipment Operations =====

    def get_creature_equipment(self, resref: str) -> List[EquipmentSlot]:
        """Get all equipment slots for a creature."""
        data = self.gff.get_creature(resref)
        if not data:
            return []

        equip_list = GFFService.extract_list(data, "Equip_ItemList")
        slots = []

        for item_data in equip_list:
            struct_id = item_data.get("__struct_id", 0)
            # Equipment can use either EquippedRes (reference only) or full item data with TemplateResRef
            item_resref = GFFService.extract_value(item_data, "EquippedRes", "")
            if not item_resref:
                item_resref = GFFService.extract_value(item_data, "TemplateResRef", "")
            slot = EquipmentSlot(
                slot_id=struct_id,
                slot_name=EquipmentSlots.get_name(struct_id),
                item_resref=item_resref,
                item_name=GFFService.extract_locstring(item_data, "LocalizedName"),
                item_data=item_data
            )
            slots.append(slot)

        return slots

    def set_creature_equipment(self, creature_resref: str, slot_id: int,
                                item_resref: str) -> bool:
        """Set an item in a creature's equipment slot."""
        creature_data = self.gff.get_creature(creature_resref)
        if not creature_data:
            return False

        # Get the item template
        item_data = self.gff.get_item(item_resref)
        if not item_data:
            return False

        # Create a copy for the equipment slot
        equip_item = dict(item_data)
        equip_item["__struct_id"] = slot_id

        # Get or create equipment list
        if "Equip_ItemList" not in creature_data:
            creature_data["Equip_ItemList"] = {"type": "list", "value": []}

        equip_list = GFFService.extract_list(creature_data, "Equip_ItemList")

        # Remove existing item in this slot
        equip_list = [e for e in equip_list if e.get("__struct_id") != slot_id]

        # Add new item
        equip_list.append(equip_item)

        # Update the data
        if isinstance(creature_data["Equip_ItemList"], dict):
            creature_data["Equip_ItemList"]["value"] = equip_list
        else:
            creature_data["Equip_ItemList"] = equip_list

        return self.gff.save_creature(creature_resref, creature_data)

    def remove_creature_equipment(self, creature_resref: str, slot_id: int) -> bool:
        """Remove an item from a creature's equipment slot."""
        creature_data = self.gff.get_creature(creature_resref)
        if not creature_data:
            return False

        equip_list = GFFService.extract_list(creature_data, "Equip_ItemList")
        equip_list = [e for e in equip_list if e.get("__struct_id") != slot_id]

        if isinstance(creature_data["Equip_ItemList"], dict):
            creature_data["Equip_ItemList"]["value"] = equip_list
        else:
            creature_data["Equip_ItemList"] = equip_list

        return self.gff.save_creature(creature_resref, creature_data)

    # ===== Creature Inventory Operations =====

    def get_creature_inventory(self, resref: str) -> List[InventoryItem]:
        """Get all inventory items for a creature."""
        data = self.gff.get_creature(resref)
        if not data:
            return []

        inv_list = GFFService.extract_list(data, "ItemList")
        items = []

        for idx, item_data in enumerate(inv_list):
            item = InventoryItem(
                index=idx,
                resref=GFFService.extract_value(item_data, "TemplateResRef", ""),
                name=GFFService.extract_locstring(item_data, "LocalizedName"),
                stack_size=GFFService.extract_value(item_data, "StackSize", 1),
                repos_x=GFFService.extract_value(item_data, "Repos_PosX", 0),
                repos_y=GFFService.extract_value(item_data, "Repos_PosY", 0),
                item_data=item_data
            )
            items.append(item)

        return items

    def add_creature_inventory(self, creature_resref: str, item_resref: str,
                                stack_size: int = 1,
                                repos_x: Optional[int] = None,
                                repos_y: Optional[int] = None) -> bool:
        """Add an item to a creature's inventory."""
        creature_data = self.gff.get_creature(creature_resref)
        if not creature_data:
            return False

        item_data = self.gff.get_item(item_resref)
        if not item_data:
            return False

        # Create a copy for inventory
        inv_item = dict(item_data)
        inv_item["__struct_id"] = 0

        # Set stack size
        GFFService.set_value(inv_item, "StackSize", stack_size, "word")

        # Set position if provided
        if repos_x is not None:
            GFFService.set_value(inv_item, "Repos_PosX", repos_x, "word")
        if repos_y is not None:
            GFFService.set_value(inv_item, "Repos_PosY", repos_y, "word")

        # Get or create inventory list
        if "ItemList" not in creature_data:
            creature_data["ItemList"] = {"type": "list", "value": []}

        inv_list = GFFService.extract_list(creature_data, "ItemList")
        inv_list.append(inv_item)

        if isinstance(creature_data["ItemList"], dict):
            creature_data["ItemList"]["value"] = inv_list
        else:
            creature_data["ItemList"] = inv_list

        return self.gff.save_creature(creature_resref, creature_data)

    def remove_creature_inventory(self, creature_resref: str, index: int) -> bool:
        """Remove an item from a creature's inventory by index."""
        creature_data = self.gff.get_creature(creature_resref)
        if not creature_data:
            return False

        inv_list = GFFService.extract_list(creature_data, "ItemList")
        if index < 0 or index >= len(inv_list):
            return False

        inv_list.pop(index)

        if isinstance(creature_data["ItemList"], dict):
            creature_data["ItemList"]["value"] = inv_list
        else:
            creature_data["ItemList"] = inv_list

        return self.gff.save_creature(creature_resref, creature_data)

    # ===== Store Operations =====

    def get_item_store_category(self, item_resref: str) -> int:
        """Get the proper store category for an item based on baseitems.2da.

        Args:
            item_resref: Item template resref

        Returns:
            Store category ID (0-4)
        """
        # Get item to find its BaseItem type
        item_data = self.gff.get_item(item_resref)
        if not item_data:
            return StoreCategories.MISCELLANEOUS

        base_item = GFFService.extract_value(item_data, "BaseItem", 0)

        # Look up StorePanel in baseitems.2da
        if self.tda:
            store_panel = self.tda.get_store_panel(base_item)
            return get_category_from_store_panel(store_panel)

        # Fallback: use basic heuristics without 2DA
        return StoreCategories.MISCELLANEOUS

    def get_item_store_category_by_baseitem(self, base_item: int) -> int:
        """Get the proper store category for a base item type.

        Args:
            base_item: Base item type ID

        Returns:
            Store category ID (0-4)
        """
        if self.tda:
            store_panel = self.tda.get_store_panel(base_item)
            return get_category_from_store_panel(store_panel)
        return StoreCategories.MISCELLANEOUS

    def get_store_settings(self, resref: str) -> Optional[StoreSettings]:
        """Get store settings."""
        data = self.gff.get_store(resref)
        if not data:
            return None

        # Extract will not buy list
        wnb_list = GFFService.extract_list(data, "WillNotBuy")
        will_not_buy = [
            GFFService.extract_value(item, "BaseItem", 0)
            for item in wnb_list
        ]

        # Extract will only buy list
        wob_list = GFFService.extract_list(data, "WillOnlyBuy")
        will_only_buy = [
            GFFService.extract_value(item, "BaseItem", 0)
            for item in wob_list
        ]

        return StoreSettings(
            markup=GFFService.extract_value(data, "MarkUp", 100),
            markdown=GFFService.extract_value(data, "MarkDown", 100),
            max_buy_price=GFFService.extract_value(data, "MaxBuyPrice", -1),
            store_gold=GFFService.extract_value(data, "StoreGold", -1),
            identify_price=GFFService.extract_value(data, "IdentifyPrice", 100),
            black_market=bool(GFFService.extract_value(data, "BlackMarket", 0)),
            bm_markdown=GFFService.extract_value(data, "BM_MarkDown", 25),
            will_not_buy=will_not_buy,
            will_only_buy=will_only_buy
        )

    def update_store_settings(self, resref: str, settings: dict) -> bool:
        """Update store settings."""
        data = self.gff.get_store(resref)
        if not data:
            return False

        # Update each provided setting
        field_map = {
            "markup": ("MarkUp", "int"),
            "markdown": ("MarkDown", "int"),
            "max_buy_price": ("MaxBuyPrice", "int"),
            "store_gold": ("StoreGold", "int"),
            "identify_price": ("IdentifyPrice", "int"),
            "black_market": ("BlackMarket", "byte"),
            "bm_markdown": ("BM_MarkDown", "int"),
        }

        for key, value in settings.items():
            if key in field_map and value is not None:
                gff_key, gff_type = field_map[key]
                if key == "black_market":
                    value = 1 if value else 0
                GFFService.set_value(data, gff_key, value, gff_type)

        # Handle will_not_buy list
        if "will_not_buy" in settings and settings["will_not_buy"] is not None:
            wnb_items = [
                {"__struct_id": 0, "BaseItem": {"type": "int", "value": bi}}
                for bi in settings["will_not_buy"]
            ]
            data["WillNotBuy"] = {"type": "list", "value": wnb_items}

        # Handle will_only_buy list
        if "will_only_buy" in settings and settings["will_only_buy"] is not None:
            wob_items = [
                {"__struct_id": 0, "BaseItem": {"type": "int", "value": bi}}
                for bi in settings["will_only_buy"]
            ]
            data["WillOnlyBuy"] = {"type": "list", "value": wob_items}

        return self.gff.save_store(resref, data)

    def get_store_category(self, resref: str, category_id: int) -> List[StoreItem]:
        """Get items in a store category.

        Args:
            resref: Store template resref
            category_id: Category index (0=Armor, 1=Weapons, 2=Potions/Scrolls, 3=Magic Items, 4=Misc)

        Returns:
            List of items in that category
        """
        data = self.gff.get_store(resref)
        if not data:
            return []

        store_list = GFFService.extract_list(data, "StoreList")

        # Category is determined by array index, not __struct_id
        if category_id < 0 or category_id >= len(store_list):
            return []

        category_entry = store_list[category_id]

        # Items are in ItemList within the category
        item_list = GFFService.extract_list(category_entry, "ItemList")

        items = []
        for idx, item_data in enumerate(item_list):
            # Check for infinite flag
            infinite = GFFService.extract_value(item_data, "Infinite", 0) == 1

            # Items use InventoryRes for the resref
            item_resref = GFFService.extract_value(item_data, "InventoryRes", "")

            # Look up item name and base item from the item template
            item_name = ""
            base_item = None
            inv_slot_width = 1
            inv_slot_height = 1
            if item_resref:
                item_template = self.gff.get_item(item_resref)
                if item_template:
                    item_name = GFFService.extract_locstring(item_template, "LocalizedName")
                    base_item = GFFService.extract_value(item_template, "BaseItem", 0)
                    # Get slot dimensions from baseitems.2da
                    if self.tda and base_item is not None:
                        base_item_data = self.tda.get_baseitem(base_item)
                        if base_item_data:
                            inv_slot_width = base_item_data.get("InvSlotWidth", 1) or 1
                            inv_slot_height = base_item_data.get("InvSlotHeight", 1) or 1

            # Get position (note: Repos_Posy has lowercase 'y' in NWN)
            repos_x = GFFService.extract_value(item_data, "Repos_PosX", 0)
            repos_y = GFFService.extract_value(item_data, "Repos_Posy", 0)

            item = StoreItem(
                index=idx,
                resref=item_resref,
                name=item_name or item_resref,
                infinite=infinite,
                stack_size=GFFService.extract_value(item_data, "StackSize", 1),
                repos_x=repos_x,
                repos_y=repos_y,
                base_item=base_item,
                inv_slot_width=inv_slot_width,
                inv_slot_height=inv_slot_height,
                item_data=item_data
            )
            items.append(item)

        return items

    def add_store_item(self, store_resref: str, category_id: int,
                       item_resref: str, infinite: bool = False,
                       stack_size: int = 1) -> bool:
        """Add an item to a store category.

        Args:
            store_resref: Store template resref
            category_id: Category index (0=Armor, 1=Weapons, 2=Potions/Scrolls, 3=Magic Items, 4=Misc)
            item_resref: Item template to add
            infinite: Whether item has infinite stock
            stack_size: Stack size

        Returns:
            True if successful
        """
        store_data = self.gff.get_store(store_resref)
        if not store_data:
            return False

        # Verify item exists
        item_template = self.gff.get_item(item_resref)
        if not item_template:
            return False

        # Create store item entry (reference only, not full item data)
        store_item = {
            "__struct_id": 0,
            "InventoryRes": {"type": "resref", "value": item_resref},
            "Repos_PosX": {"type": "word", "value": 0},
            "Repos_Posy": {"type": "word", "value": 0}
        }

        # Set infinite flag if requested
        if infinite:
            store_item["Infinite"] = {"type": "byte", "value": 1}

        # Category is determined by array index
        store_list = GFFService.extract_list(store_data, "StoreList")

        # Ensure store has enough category entries
        while len(store_list) <= category_id:
            store_list.append({
                "__struct_id": len(store_list),
                "ItemList": {"type": "list", "value": []}
            })

        category_entry = store_list[category_id]

        # Ensure ItemList exists
        if "ItemList" not in category_entry:
            category_entry["ItemList"] = {"type": "list", "value": []}

        # Add item to the category
        item_list = GFFService.extract_list(category_entry, "ItemList")
        # Update struct_id to be sequential
        store_item["__struct_id"] = len(item_list)
        item_list.append(store_item)

        # Update the category entry
        if isinstance(category_entry["ItemList"], dict):
            category_entry["ItemList"]["value"] = item_list
        else:
            category_entry["ItemList"] = item_list

        # Update store_list in store_data
        store_list[category_id] = category_entry
        if isinstance(store_data["StoreList"], dict):
            store_data["StoreList"]["value"] = store_list
        else:
            store_data["StoreList"] = store_list

        return self.gff.save_store(store_resref, store_data)

    def add_store_item_auto(self, store_resref: str, item_resref: str,
                            infinite: bool = False, stack_size: int = 1) -> Optional[dict]:
        """Add an item to a store with automatic category detection.

        Uses the item's BaseItem type and baseitems.2da StorePanel to determine
        the correct category.

        Args:
            store_resref: Store template resref
            item_resref: Item template to add
            infinite: Whether item has infinite stock
            stack_size: Stack size

        Returns:
            Dict with category info if successful, None on failure
        """
        # Get the correct category for this item
        category_id = self.get_item_store_category(item_resref)

        # Get additional info for the response
        item_data = self.gff.get_item(item_resref)
        if not item_data:
            return None

        base_item = GFFService.extract_value(item_data, "BaseItem", 0)
        store_panel = None
        if self.tda:
            store_panel = self.tda.get_store_panel(base_item)

        # Add the item to the determined category
        success = self.add_store_item(store_resref, category_id, item_resref, infinite, stack_size)
        if not success:
            return None

        return {
            "success": True,
            "item_resref": item_resref,
            "category_id": category_id,
            "category_name": StoreCategories.get_name(category_id),
            "base_item": base_item,
            "store_panel": store_panel
        }

    def update_store_item(self, store_resref: str, category_id: int, index: int,
                          infinite: Optional[bool] = None,
                          stack_size: Optional[int] = None,
                          cost: Optional[int] = None,
                          identified: Optional[bool] = None,
                          repos_x: Optional[int] = None,
                          repos_y: Optional[int] = None) -> bool:
        """Update a store item.

        Args:
            store_resref: Store template resref
            category_id: Category index (0=Armor, 1=Weapons, 2=Potions/Scrolls, 3=Magic Items, 4=Misc)
            index: Item index within category
            infinite: Whether item has infinite stock
            stack_size: Stack size
            cost: Item cost in gold
            identified: Whether item is identified

        Returns:
            True if update successful
        """
        store_data = self.gff.get_store(store_resref)
        if not store_data:
            return False

        # Category is determined by array index
        store_list = GFFService.extract_list(store_data, "StoreList")

        if category_id < 0 or category_id >= len(store_list):
            return False

        category_entry = store_list[category_id]
        item_list = GFFService.extract_list(category_entry, "ItemList")

        if index < 0 or index >= len(item_list):
            return False

        item_data = item_list[index]

        if infinite is not None:
            GFFService.set_value(item_data, "Infinite", 1 if infinite else 0, "byte")

        if stack_size is not None:
            GFFService.set_value(item_data, "StackSize", stack_size, "word")

        if cost is not None:
            GFFService.set_value(item_data, "Cost", cost, "dword")

        if identified is not None:
            GFFService.set_value(item_data, "Identified", 1 if identified else 0, "byte")

        if repos_x is not None:
            GFFService.set_value(item_data, "Repos_PosX", repos_x, "word")

        if repos_y is not None:
            # Note: NWN uses lowercase 'y' in Repos_Posy
            GFFService.set_value(item_data, "Repos_Posy", repos_y, "word")

        # Update the category entry
        if isinstance(category_entry["ItemList"], dict):
            category_entry["ItemList"]["value"] = item_list
        else:
            category_entry["ItemList"] = item_list

        store_list[category_id] = category_entry
        if isinstance(store_data["StoreList"], dict):
            store_data["StoreList"]["value"] = store_list
        else:
            store_data["StoreList"] = store_list

        return self.gff.save_store(store_resref, store_data)

    def remove_store_item(self, store_resref: str, category_id: int, index: int) -> bool:
        """Remove an item from a store category.

        Args:
            store_resref: Store template resref
            category_id: Category index (0=Armor, 1=Weapons, 2=Potions/Scrolls, 3=Magic Items, 4=Misc)
            index: Item index within category

        Returns:
            True if successful
        """
        store_data = self.gff.get_store(store_resref)
        if not store_data:
            return False

        # Category is determined by array index
        store_list = GFFService.extract_list(store_data, "StoreList")

        if category_id < 0 or category_id >= len(store_list):
            return False

        category_entry = store_list[category_id]
        item_list = GFFService.extract_list(category_entry, "ItemList")

        if index < 0 or index >= len(item_list):
            return False

        item_list.pop(index)

        # Update the category entry
        if isinstance(category_entry["ItemList"], dict):
            category_entry["ItemList"]["value"] = item_list
        else:
            category_entry["ItemList"] = item_list

        store_list[category_id] = category_entry
        if isinstance(store_data["StoreList"], dict):
            store_data["StoreList"]["value"] = store_list
        else:
            store_data["StoreList"] = store_list

        return self.gff.save_store(store_resref, store_data)
