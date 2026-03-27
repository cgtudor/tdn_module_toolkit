"""Area instance API endpoints."""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List

from models.instance import (
    AreaSummary, StoreInstance, CreatureInstance, SyncResult
)
from models.creature import EquipmentSlot, InventoryItem, EquipmentSlots
from models.store import (
    StoreCategory, StoreCategories, StoreSettingsUpdate,
    StoreItemAddAuto, StoreItemAddResult, get_category_from_store_panel
)
from services.gff_service import GFFService

router = APIRouter(prefix="/api", tags=["instances"])

# Injected by main.py
gff_service: GFFService = None
indexer = None
inventory_ops = None
tda_service = None
tlk_service = None


def init(gff: GFFService, idx, inv_ops, tda=None, tlk=None):
    global gff_service, indexer, inventory_ops, tda_service, tlk_service
    gff_service = gff
    indexer = idx
    inventory_ops = inv_ops
    tda_service = tda
    tlk_service = tlk


def _get_item_file_location(store_data: dict, category_id: int, item_index: int):
    """Find the item data at a specific file location.

    For instances, category_id is the file category index (StoreList array index),
    and item_index is the item's index within that category's ItemList.

    Args:
        store_data: The store data from the GIT file
        category_id: The file category index (0-4)
        item_index: The item's index within the category's ItemList

    Returns:
        Tuple of (file_category_index, file_item_index, item_data) or raises HTTPException
    """
    inner_store_list = GFFService.extract_list(store_data, "StoreList")

    if category_id < 0 or category_id >= len(inner_store_list):
        raise HTTPException(status_code=404, detail=f"Category {category_id} not found")

    category_entry = inner_store_list[category_id]
    item_list = GFFService.extract_list(category_entry, "ItemList")

    if item_index < 0 or item_index >= len(item_list):
        raise HTTPException(status_code=404, detail=f"Item index {item_index} not found in category {category_id}")

    return category_id, item_index, item_list[item_index]


@router.get("/areas", response_model=dict)
async def list_areas(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200)
):
    """List all areas with instance counts."""
    areas, total = indexer.list_areas(offset=offset, limit=limit)

    return {
        "areas": areas,
        "total": total,
        "offset": offset,
        "limit": limit
    }


@router.get("/areas/search")
async def search_areas(
    q: str = Query(..., min_length=1),
    limit: int = Query(50, ge=1, le=200)
):
    """Full-text search areas by name or resref."""
    query = q.replace('"', '""')
    results = indexer.search_areas(f'"{query}"*', limit)

    return {"areas": results, "total": len(results)}


@router.get("/areas/{resref}")
async def get_area(resref: str):
    """Get area info with instance counts."""
    git_data = gff_service.get_area_git(resref)
    if not git_data:
        raise HTTPException(status_code=404, detail=f"Area '{resref}' not found")

    are_data = gff_service.get_area_are(resref)
    name = ""
    if are_data:
        name = GFFService.extract_locstring(are_data, "Name")

    store_list = GFFService.extract_list(git_data, "StoreList")
    creature_list = GFFService.extract_list(git_data, "Creature List")

    return {
        "resref": resref,
        "name": name,
        "store_count": len(store_list),
        "creature_count": len(creature_list)
    }


@router.get("/areas/{resref}/stores")
async def list_area_stores(resref: str):
    """List store instances in an area."""
    git_data = gff_service.get_area_git(resref)
    if not git_data:
        raise HTTPException(status_code=404, detail=f"Area '{resref}' not found")

    store_list = GFFService.extract_list(git_data, "StoreList")

    stores = []
    for idx, store_data in enumerate(store_list):
        stores.append({
            "index": idx,
            "resref": GFFService.extract_value(store_data, "ResRef", ""),
            "template_resref": GFFService.extract_value(store_data, "TemplateResRef"),
            "tag": GFFService.extract_value(store_data, "Tag", ""),
            "name": GFFService.extract_locstring(store_data, "LocName"),
            "x": GFFService.extract_value(store_data, "XPosition", 0.0),
            "y": GFFService.extract_value(store_data, "YPosition", 0.0),
            "z": GFFService.extract_value(store_data, "ZPosition", 0.0)
        })

    return {"stores": stores, "total": len(stores)}


@router.get("/areas/{resref}/stores/{index}", response_model=StoreInstance)
async def get_area_store(resref: str, index: int):
    """Get a specific store instance with full details."""
    git_data = gff_service.get_area_git(resref)
    if not git_data:
        raise HTTPException(status_code=404, detail=f"Area '{resref}' not found")

    store_list = GFFService.extract_list(git_data, "StoreList")
    if index < 0 or index >= len(store_list):
        raise HTTPException(status_code=404, detail=f"Store index {index} not found")

    store_data = store_list[index]

    # Extract settings
    from models.store import StoreSettings
    wnb_list = GFFService.extract_list(store_data, "WillNotBuy")
    will_not_buy = [GFFService.extract_value(item, "BaseItem", 0) for item in wnb_list]

    wob_list = GFFService.extract_list(store_data, "WillOnlyBuy")
    will_only_buy = [GFFService.extract_value(item, "BaseItem", 0) for item in wob_list]

    settings = StoreSettings(
        markup=GFFService.extract_value(store_data, "MarkUp", 100),
        markdown=GFFService.extract_value(store_data, "MarkDown", 100),
        max_buy_price=GFFService.extract_value(store_data, "MaxBuyPrice", -1),
        store_gold=GFFService.extract_value(store_data, "StoreGold", -1),
        identify_price=GFFService.extract_value(store_data, "IdentifyPrice", 100),
        black_market=bool(GFFService.extract_value(store_data, "BlackMarket", 0)),
        bm_markdown=GFFService.extract_value(store_data, "BM_MarkDown", 25),
        will_not_buy=will_not_buy,
        will_only_buy=will_only_buy
    )

    # Extract items by their FILE category (StoreList array index)
    # For instances, we use file category (not StorePanel) because:
    # 1. The game displays items by their file category
    # 2. Item positions (Repos_PosX/Y) are relative to the file category's grid
    from models.store import StoreItem
    inner_store_list = GFFService.extract_list(store_data, "StoreList")

    # Collect items by their file category (array index)
    category_items: dict[int, list] = {cat_id: [] for cat_id in StoreCategories.all_categories()}

    for file_cat_idx, category_entry in enumerate(inner_store_list):
        # Skip categories beyond the standard 5 (0-4)
        if file_cat_idx >= 5:
            continue

        item_list = GFFService.extract_list(category_entry, "ItemList")
        for file_item_idx, item_data in enumerate(item_list):
            # Store instances in areas have full item data with LocalizedName
            item_name = GFFService.extract_locstring(item_data, "LocalizedName")
            item_resref = GFFService.extract_value(item_data, "InventoryRes", "")

            # Also check TemplateResRef as fallback for resref
            if not item_resref:
                item_resref = GFFService.extract_value(item_data, "TemplateResRef", "")

            # Get BaseItem for slot dimensions lookup
            base_item = GFFService.extract_value(item_data, "BaseItem")

            # If BaseItem not found in embedded data, try loading item template
            if base_item is None and item_resref:
                item_template = gff_service.get_item(item_resref)
                if item_template:
                    base_item = GFFService.extract_value(item_template, "BaseItem", 0)

            # Get slot dimensions from baseitems.2da
            inv_slot_width = 1
            inv_slot_height = 1

            if tda_service and base_item is not None:
                base_item_data = tda_service.get_baseitem(base_item)
                if base_item_data:
                    # Ensure integer values with explicit conversion
                    width_val = base_item_data.get("InvSlotWidth", 1)
                    height_val = base_item_data.get("InvSlotHeight", 1)
                    inv_slot_width = int(width_val) if width_val else 1
                    inv_slot_height = int(height_val) if height_val else 1

            # Get position (note: Repos_Posy has lowercase 'y' in NWN)
            repos_x = GFFService.extract_value(item_data, "Repos_PosX", 0)
            repos_y = GFFService.extract_value(item_data, "Repos_Posy", 0)

            # Use file category index as the display category
            # This matches how the game displays items
            category_items[file_cat_idx].append(StoreItem(
                index=file_item_idx,
                resref=item_resref,
                name=item_name or item_resref,
                infinite=GFFService.extract_value(item_data, "Infinite", 0) == 1,
                stack_size=GFFService.extract_value(item_data, "StackSize", 1),
                repos_x=repos_x,
                repos_y=repos_y,
                base_item=base_item,
                inv_slot_width=inv_slot_width,
                inv_slot_height=inv_slot_height,
                item_data=item_data
            ))

    # Build categories list
    categories = []
    for cat_id in StoreCategories.all_categories():
        categories.append(StoreCategory(
            category_id=cat_id,
            category_name=StoreCategories.get_name(cat_id),
            items=category_items[cat_id]
        ))

    return StoreInstance(
        index=index,
        resref=GFFService.extract_value(store_data, "ResRef", ""),
        template_resref=GFFService.extract_value(store_data, "TemplateResRef"),
        tag=GFFService.extract_value(store_data, "Tag", ""),
        name=GFFService.extract_locstring(store_data, "LocName"),
        x=GFFService.extract_value(store_data, "XPosition", 0.0),
        y=GFFService.extract_value(store_data, "YPosition", 0.0),
        z=GFFService.extract_value(store_data, "ZPosition", 0.0),
        settings=settings,
        categories=categories,
        raw_data=store_data
    )


@router.put("/areas/{resref}/stores/{index}/settings")
async def update_area_store_settings(resref: str, index: int, body: StoreSettingsUpdate):
    """Update store instance settings (markup, markdown, gold, etc.) in area GIT file."""
    git_data = gff_service.get_area_git(resref)
    if not git_data:
        raise HTTPException(status_code=404, detail=f"Area '{resref}' not found")

    store_list = GFFService.extract_list(git_data, "StoreList")
    if index < 0 or index >= len(store_list):
        raise HTTPException(status_code=404, detail=f"Store index {index} not found")

    store_data = store_list[index]
    changes = []

    # Update settings that were provided
    if body.markup is not None:
        GFFService.set_value(store_data, "MarkUp", body.markup, "int")
        changes.append(f"MarkUp: {body.markup}")

    if body.markdown is not None:
        GFFService.set_value(store_data, "MarkDown", body.markdown, "int")
        changes.append(f"MarkDown: {body.markdown}")

    if body.max_buy_price is not None:
        GFFService.set_value(store_data, "MaxBuyPrice", body.max_buy_price, "int")
        changes.append(f"MaxBuyPrice: {body.max_buy_price}")

    if body.store_gold is not None:
        GFFService.set_value(store_data, "StoreGold", body.store_gold, "int")
        changes.append(f"StoreGold: {body.store_gold}")

    if body.identify_price is not None:
        GFFService.set_value(store_data, "IdentifyPrice", body.identify_price, "int")
        changes.append(f"IdentifyPrice: {body.identify_price}")

    if body.black_market is not None:
        GFFService.set_value(store_data, "BlackMarket", 1 if body.black_market else 0, "byte")
        changes.append(f"BlackMarket: {body.black_market}")

    if body.bm_markdown is not None:
        GFFService.set_value(store_data, "BM_MarkDown", body.bm_markdown, "int")
        changes.append(f"BM_MarkDown: {body.bm_markdown}")

    # Handle will_not_buy list
    if body.will_not_buy is not None:
        wnb_list = [{"__struct_id": i, "BaseItem": {"type": "int", "value": bi}}
                    for i, bi in enumerate(body.will_not_buy)]
        store_data["WillNotBuy"] = {"type": "list", "value": wnb_list}
        changes.append(f"WillNotBuy: {len(body.will_not_buy)} items")

    # Handle will_only_buy list
    if body.will_only_buy is not None:
        wob_list = [{"__struct_id": i, "BaseItem": {"type": "int", "value": bi}}
                    for i, bi in enumerate(body.will_only_buy)]
        store_data["WillOnlyBuy"] = {"type": "list", "value": wob_list}
        changes.append(f"WillOnlyBuy: {len(body.will_only_buy)} items")

    if changes:
        # Update the store list and save
        store_list[index] = store_data
        if isinstance(git_data["StoreList"], dict):
            git_data["StoreList"]["value"] = store_list
        else:
            git_data["StoreList"] = {"type": "list", "value": store_list}

        gff_service.save_area_git(resref, git_data)

    return {
        "success": True,
        "message": f"Updated {len(changes)} settings" if changes else "No changes made",
        "changes": changes
    }


@router.get("/areas/{resref}/creatures")
async def list_area_creatures(resref: str):
    """List creature instances in an area."""
    git_data = gff_service.get_area_git(resref)
    if not git_data:
        raise HTTPException(status_code=404, detail=f"Area '{resref}' not found")

    creature_list = GFFService.extract_list(git_data, "Creature List")

    creatures = []
    for idx, creature_data in enumerate(creature_list):
        first_name = GFFService.extract_locstring(creature_data, "FirstName")
        last_name = GFFService.extract_locstring(creature_data, "LastName")

        creatures.append({
            "index": idx,
            "resref": GFFService.extract_value(creature_data, "ResRef", ""),
            "template_resref": GFFService.extract_value(creature_data, "TemplateResRef"),
            "tag": GFFService.extract_value(creature_data, "Tag", ""),
            "first_name": first_name,
            "last_name": last_name,
            "display_name": f"{first_name} {last_name}".strip() or "Unknown",
            "x": GFFService.extract_value(creature_data, "XPosition", 0.0),
            "y": GFFService.extract_value(creature_data, "YPosition", 0.0),
            "z": GFFService.extract_value(creature_data, "ZPosition", 0.0)
        })

    return {"creatures": creatures, "total": len(creatures)}


@router.get("/areas/{resref}/creatures/{index}", response_model=CreatureInstance)
async def get_area_creature(resref: str, index: int):
    """Get a specific creature instance with full details."""
    git_data = gff_service.get_area_git(resref)
    if not git_data:
        raise HTTPException(status_code=404, detail=f"Area '{resref}' not found")

    creature_list = GFFService.extract_list(git_data, "Creature List")
    if index < 0 or index >= len(creature_list):
        raise HTTPException(status_code=404, detail=f"Creature index {index} not found")

    creature_data = creature_list[index]

    # Extract equipment
    equip_list = GFFService.extract_list(creature_data, "Equip_ItemList")
    equipment = []
    for item_data in equip_list:
        struct_id = item_data.get("__struct_id", 0)
        # Equipment can use either EquippedRes (reference only) or full item data with TemplateResRef
        item_resref = GFFService.extract_value(item_data, "EquippedRes", "")
        if not item_resref:
            item_resref = GFFService.extract_value(item_data, "TemplateResRef", "")
        equipment.append(EquipmentSlot(
            slot_id=struct_id,
            slot_name=EquipmentSlots.get_name(struct_id),
            item_resref=item_resref,
            item_name=GFFService.extract_locstring(item_data, "LocalizedName"),
            item_data=item_data
        ))

    # Extract inventory
    inv_list = GFFService.extract_list(creature_data, "ItemList")
    inventory = []
    for item_idx, item_data in enumerate(inv_list):
        inventory.append(InventoryItem(
            index=item_idx,
            resref=GFFService.extract_value(item_data, "TemplateResRef", ""),
            name=GFFService.extract_locstring(item_data, "LocalizedName"),
            stack_size=GFFService.extract_value(item_data, "StackSize", 1),
            repos_x=GFFService.extract_value(item_data, "Repos_PosX", 0),
            repos_y=GFFService.extract_value(item_data, "Repos_PosY", 0),
            item_data=item_data
        ))

    return CreatureInstance(
        index=index,
        resref=GFFService.extract_value(creature_data, "ResRef", ""),
        template_resref=GFFService.extract_value(creature_data, "TemplateResRef"),
        tag=GFFService.extract_value(creature_data, "Tag", ""),
        first_name=GFFService.extract_locstring(creature_data, "FirstName"),
        last_name=GFFService.extract_locstring(creature_data, "LastName"),
        x=GFFService.extract_value(creature_data, "XPosition", 0.0),
        y=GFFService.extract_value(creature_data, "YPosition", 0.0),
        z=GFFService.extract_value(creature_data, "ZPosition", 0.0),
        equipment=equipment,
        inventory=inventory,
        raw_data=creature_data
    )


@router.post("/areas/{resref}/stores/{index}/items", response_model=StoreItemAddResult)
async def add_area_store_item_auto(resref: str, index: int, body: StoreItemAddAuto):
    """Add an item to an area store instance with automatic category detection.

    Uses the item's BaseItem type and baseitems.2da StorePanel to determine
    the correct category for the item.
    """
    git_data = gff_service.get_area_git(resref)
    if not git_data:
        raise HTTPException(status_code=404, detail=f"Area '{resref}' not found")

    store_list = GFFService.extract_list(git_data, "StoreList")
    if index < 0 or index >= len(store_list):
        raise HTTPException(status_code=404, detail=f"Store index {index} not found")

    # Verify item exists and get its BaseItem
    item_template = gff_service.get_item(body.item_resref)
    if not item_template:
        raise HTTPException(status_code=400, detail=f"Item '{body.item_resref}' not found")

    base_item = GFFService.extract_value(item_template, "BaseItem", 0)

    # Get correct category from StorePanel
    store_panel = None
    if tda_service:
        store_panel = tda_service.get_store_panel(base_item)

    category_id = get_category_from_store_panel(store_panel)

    # Add the item using the internal function logic
    store_data = store_list[index]
    inner_store_list = GFFService.extract_list(store_data, "StoreList")

    # Ensure store has enough category entries (category is determined by array index)
    while len(inner_store_list) <= category_id:
        inner_store_list.append({
            "__struct_id": len(inner_store_list),
            "ItemList": {"type": "list", "value": []}
        })

    # Get category entry by array index
    category_entry = inner_store_list[category_id]
    category_index = category_id

    # Ensure ItemList exists in category
    if "ItemList" not in category_entry:
        category_entry["ItemList"] = {"type": "list", "value": []}

    item_list = GFFService.extract_list(category_entry, "ItemList")

    # Calculate __struct_id
    new_struct_id = len(item_list)

    # Calculate next available Repos position
    max_repos_y = -1
    for existing_item in item_list:
        repos_y = GFFService.extract_value(existing_item, "Repos_Posy", 0)
        if repos_y > max_repos_y:
            max_repos_y = repos_y
    new_repos_x = 0
    new_repos_y = max_repos_y + 2 if max_repos_y >= 0 else 0

    # Define the correct field order for store items
    store_item_fields = [
        'AddCost', 'BaseItem', 'Charges', 'Cost', 'Cursed',
        'DescIdentified', 'Description', 'Identified',
        'LocalizedName', 'ModelPart1', 'ModelPart2', 'ModelPart3',
        'Plot', 'PropertiesList', 'StackSize', 'Stolen', 'Tag',
        'VarTable', 'xModelPart1', 'xModelPart2', 'xModelPart3'
    ]

    # Build store item with correct fields
    store_item = {"__struct_id": new_struct_id}

    # Copy item template fields
    for field in store_item_fields:
        if field in item_template:
            store_item[field] = item_template[field]

    # Add store-specific fields
    store_item["Infinite"] = {"type": "byte", "value": 1 if body.infinite else 0}
    store_item["Repos_PosX"] = {"type": "word", "value": new_repos_x}
    store_item["Repos_Posy"] = {"type": "word", "value": new_repos_y}
    store_item["TemplateResRef"] = {"type": "resref", "value": body.item_resref}

    # Add position fields
    store_item["XOrientation"] = {"type": "float", "value": 0.0}
    store_item["XPosition"] = {"type": "float", "value": -1.0}
    store_item["YOrientation"] = {"type": "float", "value": 1.0}
    store_item["YPosition"] = {"type": "float", "value": -1.0}
    store_item["ZPosition"] = {"type": "float", "value": -1.0}

    # Add the new item to the list
    item_list.append(store_item)

    # Update category entry
    if isinstance(category_entry["ItemList"], dict):
        category_entry["ItemList"]["value"] = item_list
    else:
        category_entry["ItemList"] = {"type": "list", "value": item_list}

    inner_store_list[category_index] = category_entry

    # Update store_data with inner_store_list
    if "StoreList" not in store_data:
        store_data["StoreList"] = {"type": "list", "value": []}
    if isinstance(store_data["StoreList"], dict):
        store_data["StoreList"]["value"] = inner_store_list
    else:
        store_data["StoreList"] = {"type": "list", "value": inner_store_list}

    # Update git_data's StoreList
    store_list[index] = store_data
    if isinstance(git_data["StoreList"], dict):
        git_data["StoreList"]["value"] = store_list
    else:
        git_data["StoreList"] = {"type": "list", "value": store_list}

    gff_service.save_area_git(resref, git_data)

    return StoreItemAddResult(
        success=True,
        item_resref=body.item_resref,
        category_id=category_id,
        category_name=StoreCategories.get_name(category_id),
        base_item=base_item,
        store_panel=store_panel
    )


@router.post("/areas/{resref}/stores/{index}/categories/{category_id}/items")
async def add_area_store_item(resref: str, index: int, category_id: int, body: dict):
    """Add an item to a specific area store category (manual override)."""
    git_data = gff_service.get_area_git(resref)
    if not git_data:
        raise HTTPException(status_code=404, detail=f"Area '{resref}' not found")

    store_list = GFFService.extract_list(git_data, "StoreList")
    if index < 0 or index >= len(store_list):
        raise HTTPException(status_code=404, detail=f"Store index {index} not found")

    if category_id not in StoreCategories.all_categories():
        raise HTTPException(status_code=400, detail=f"Invalid category_id: {category_id}")

    item_resref = body.get("item_resref")
    if not item_resref:
        raise HTTPException(status_code=400, detail="item_resref is required")

    # Verify item exists
    item_template = gff_service.get_item(item_resref)
    if not item_template:
        raise HTTPException(status_code=400, detail=f"Item '{item_resref}' not found")

    store_data = store_list[index]
    inner_store_list = GFFService.extract_list(store_data, "StoreList")

    # Ensure store has enough category entries (category is determined by array index)
    while len(inner_store_list) <= category_id:
        inner_store_list.append({
            "__struct_id": len(inner_store_list),
            "ItemList": {"type": "list", "value": []}
        })

    # Get category entry by array index
    category_entry = inner_store_list[category_id]

    # Ensure ItemList exists in category
    if "ItemList" not in category_entry:
        category_entry["ItemList"] = {"type": "list", "value": []}

    item_list = GFFService.extract_list(category_entry, "ItemList")

    # Calculate __struct_id (should be the item's index in the list)
    new_struct_id = len(item_list)

    # Calculate next available Repos position
    # Find max Y position used, then place new item at next row
    max_repos_y = -1
    for existing_item in item_list:
        repos_y = GFFService.extract_value(existing_item, "Repos_Posy", 0)
        if repos_y > max_repos_y:
            max_repos_y = repos_y
    # Place new item at next row (Y increments by 2 per row typically)
    new_repos_x = 0
    new_repos_y = max_repos_y + 2 if max_repos_y >= 0 else 0

    # Create store item - build with only the needed fields
    # GIT store instances need full item data but NOT template-only fields
    # Fields to exclude from template: __data_type, Comment, PaletteID

    # Define the correct field order for store items
    store_item_fields = [
        'AddCost', 'BaseItem', 'Charges', 'Cost', 'Cursed',
        'DescIdentified', 'Description', 'Identified',
        'LocalizedName', 'ModelPart1', 'ModelPart2', 'ModelPart3',
        'Plot', 'PropertiesList', 'StackSize', 'Stolen', 'Tag',
        'VarTable', 'xModelPart1', 'xModelPart2', 'xModelPart3'
    ]

    # Build store item with correct fields
    store_item = {"__struct_id": new_struct_id}

    # Copy item template fields (excluding template-only fields)
    for field in store_item_fields:
        if field in item_template:
            store_item[field] = item_template[field]

    # Add store-specific fields
    store_item["Infinite"] = {"type": "byte", "value": 1 if body.get("infinite", False) else 0}
    store_item["Repos_PosX"] = {"type": "word", "value": new_repos_x}
    store_item["Repos_Posy"] = {"type": "word", "value": new_repos_y}
    store_item["TemplateResRef"] = {"type": "resref", "value": item_resref}

    # Add position fields (standard values for store items)
    store_item["XOrientation"] = {"type": "float", "value": 0.0}
    store_item["XPosition"] = {"type": "float", "value": -1.0}
    store_item["YOrientation"] = {"type": "float", "value": 1.0}
    store_item["YPosition"] = {"type": "float", "value": -1.0}
    store_item["ZPosition"] = {"type": "float", "value": -1.0}

    # Add the new item to the list
    item_list.append(store_item)

    # Update category entry
    if isinstance(category_entry["ItemList"], dict):
        category_entry["ItemList"]["value"] = item_list
    else:
        category_entry["ItemList"] = {"type": "list", "value": item_list}

    inner_store_list[category_id] = category_entry

    # Update store_data with inner_store_list
    if "StoreList" not in store_data:
        store_data["StoreList"] = {"type": "list", "value": []}
    if isinstance(store_data["StoreList"], dict):
        store_data["StoreList"]["value"] = inner_store_list
    else:
        store_data["StoreList"] = {"type": "list", "value": inner_store_list}

    # Update git_data's StoreList
    store_list[index] = store_data
    if isinstance(git_data["StoreList"], dict):
        git_data["StoreList"]["value"] = store_list
    else:
        git_data["StoreList"] = {"type": "list", "value": store_list}

    gff_service.save_area_git(resref, git_data)

    return {"success": True, "item_resref": item_resref}


@router.put("/areas/{resref}/stores/{index}/categories/{category_id}/items/{item_index}")
async def update_area_store_item(resref: str, index: int, category_id: int, item_index: int, body: dict):
    """Update an item in an area store instance's category.

    Items are displayed categorized by StorePanel, but may be stored in different
    file category entries. This function maps the display location to file location.

    Supports updating: infinite, stack_size, cost, identified, repos_x, repos_y
    """
    git_data = gff_service.get_area_git(resref)
    if not git_data:
        raise HTTPException(status_code=404, detail=f"Area '{resref}' not found")

    store_list = GFFService.extract_list(git_data, "StoreList")
    if index < 0 or index >= len(store_list):
        raise HTTPException(status_code=404, detail=f"Store index {index} not found")

    if category_id not in StoreCategories.all_categories():
        raise HTTPException(status_code=400, detail=f"Invalid category_id: {category_id}")

    store_data = store_list[index]
    inner_store_list = GFFService.extract_list(store_data, "StoreList")

    # Map display category/index to file location
    file_cat_idx, file_item_idx, item_data = _get_item_file_location(store_data, category_id, item_index)

    # Get the actual category entry and item list from the file
    category_entry = inner_store_list[file_cat_idx]
    item_list = GFFService.extract_list(category_entry, "ItemList")

    # Update the item in place (item_data is a reference to the actual item)
    # Update infinite flag if provided
    if "infinite" in body:
        GFFService.set_value(item_data, "Infinite", 1 if body["infinite"] else 0, "byte")

    # Update stack size if provided
    if "stack_size" in body:
        GFFService.set_value(item_data, "StackSize", body["stack_size"], "word")

    # Update cost if provided
    if "cost" in body:
        GFFService.set_value(item_data, "Cost", body["cost"], "dword")

    # Update identified flag if provided
    if "identified" in body:
        GFFService.set_value(item_data, "Identified", 1 if body["identified"] else 0, "byte")

    # Update position if provided
    if "repos_x" in body:
        GFFService.set_value(item_data, "Repos_PosX", body["repos_x"], "word")

    if "repos_y" in body:
        # Note: NWN uses lowercase 'y' in Repos_Posy
        GFFService.set_value(item_data, "Repos_Posy", body["repos_y"], "word")

    # Update category entry
    if isinstance(category_entry["ItemList"], dict):
        category_entry["ItemList"]["value"] = item_list
    else:
        category_entry["ItemList"] = {"type": "list", "value": item_list}

    inner_store_list[file_cat_idx] = category_entry

    # Update store_data
    if isinstance(store_data["StoreList"], dict):
        store_data["StoreList"]["value"] = inner_store_list
    else:
        store_data["StoreList"] = {"type": "list", "value": inner_store_list}

    # Update git_data
    store_list[index] = store_data
    if isinstance(git_data["StoreList"], dict):
        git_data["StoreList"]["value"] = store_list
    else:
        git_data["StoreList"] = {"type": "list", "value": store_list}

    gff_service.save_area_git(resref, git_data)

    return {"success": True}


@router.delete("/areas/{resref}/stores/{index}/categories/{category_id}/items/{item_index}")
async def remove_area_store_item(resref: str, index: int, category_id: int, item_index: int):
    """Remove an item from an area store instance's category.

    Items are displayed categorized by StorePanel, but may be stored in different
    file category entries. This function maps the display location to file location.
    """
    git_data = gff_service.get_area_git(resref)
    if not git_data:
        raise HTTPException(status_code=404, detail=f"Area '{resref}' not found")

    store_list = GFFService.extract_list(git_data, "StoreList")
    if index < 0 or index >= len(store_list):
        raise HTTPException(status_code=404, detail=f"Store index {index} not found")

    if category_id not in StoreCategories.all_categories():
        raise HTTPException(status_code=400, detail=f"Invalid category_id: {category_id}")

    store_data = store_list[index]
    inner_store_list = GFFService.extract_list(store_data, "StoreList")

    # Map display category/index to file location
    file_cat_idx, file_item_idx, _ = _get_item_file_location(store_data, category_id, item_index)

    # Get the actual category entry from the file
    category_entry = inner_store_list[file_cat_idx]
    item_list = GFFService.extract_list(category_entry, "ItemList")

    # Remove the item at the file index
    item_list.pop(file_item_idx)

    # Update category entry
    if isinstance(category_entry["ItemList"], dict):
        category_entry["ItemList"]["value"] = item_list
    else:
        category_entry["ItemList"] = {"type": "list", "value": item_list}

    inner_store_list[file_cat_idx] = category_entry

    # Update store_data
    if isinstance(store_data["StoreList"], dict):
        store_data["StoreList"]["value"] = inner_store_list
    else:
        store_data["StoreList"] = {"type": "list", "value": inner_store_list}

    # Update git_data
    store_list[index] = store_data
    if isinstance(git_data["StoreList"], dict):
        git_data["StoreList"]["value"] = store_list
    else:
        git_data["StoreList"] = {"type": "list", "value": store_list}

    gff_service.save_area_git(resref, git_data)

    return {"success": True, "index": item_index}


@router.post("/areas/{resref}/stores/{index}/sync", response_model=SyncResult)
async def sync_store_from_template(resref: str, index: int):
    """Sync a store instance from its template.

    Copies category contents from the template to the instance. Categories are
    identified by their array index position in the StoreList.
    """
    git_data = gff_service.get_area_git(resref)
    if not git_data:
        raise HTTPException(status_code=404, detail=f"Area '{resref}' not found")

    store_list = GFFService.extract_list(git_data, "StoreList")
    if index < 0 or index >= len(store_list):
        raise HTTPException(status_code=404, detail=f"Store index {index} not found")

    store_data = store_list[index]
    template_resref = GFFService.extract_value(store_data, "TemplateResRef")

    if not template_resref:
        return SyncResult(
            success=False,
            message="No template resref found on store instance"
        )

    # Get template
    template_data = gff_service.get_store(template_resref)
    if not template_data:
        return SyncResult(
            success=False,
            message=f"Template '{template_resref}' not found"
        )

    changes = []

    # Category is determined by array index, not __struct_id
    template_store_list = GFFService.extract_list(template_data, "StoreList")
    instance_store_list = GFFService.extract_list(store_data, "StoreList")

    # Ensure instance has at least as many category entries as template
    while len(instance_store_list) < len(template_store_list):
        instance_store_list.append({
            "__struct_id": len(instance_store_list),
            "ItemList": {"type": "list", "value": []}
        })

    # Sync each category by array index
    for cat_id in range(len(template_store_list)):
        template_entry = template_store_list[cat_id]
        template_items = GFFService.extract_list(template_entry, "ItemList")

        instance_entry = instance_store_list[cat_id]
        instance_items = GFFService.extract_list(instance_entry, "ItemList")

        # Compare item counts (simple sync - replace if different)
        if len(template_items) != len(instance_items):
            # Copy the entire category from template
            new_entry = dict(template_entry)
            instance_store_list[cat_id] = new_entry
            changes.append(f"Updated {StoreCategories.get_name(cat_id)} category ({len(template_items)} items)")

    # Update the instance's StoreList
    if changes:
        if "StoreList" not in store_data:
            store_data["StoreList"] = {"type": "list", "value": []}

        if isinstance(store_data["StoreList"], dict):
            store_data["StoreList"]["value"] = instance_store_list
        else:
            store_data["StoreList"] = {"type": "list", "value": instance_store_list}

    # Sync settings
    settings_keys = ["MarkUp", "MarkDown", "MaxBuyPrice", "StoreGold",
                     "IdentifyPrice", "BlackMarket", "BM_MarkDown"]
    for key in settings_keys:
        if key in template_data:
            template_val = GFFService.extract_value(template_data, key)
            instance_val = GFFService.extract_value(store_data, key)
            if template_val != instance_val:
                store_data[key] = template_data[key]
                changes.append(f"Updated {key}")

    if changes:
        # Update the store list and save
        store_list[index] = store_data
        if isinstance(git_data["StoreList"], dict):
            git_data["StoreList"]["value"] = store_list
        else:
            git_data["StoreList"] = {"type": "list", "value": store_list}

        gff_service.save_area_git(resref, git_data)

    return SyncResult(
        success=True,
        message=f"Synced {len(changes)} changes from template" if changes else "Already in sync",
        changes_made=changes
    )
