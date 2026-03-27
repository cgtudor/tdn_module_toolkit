"""Item API endpoints."""
import re
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List

from models.item import ItemSummary, ItemDetail, ItemProperty, ItemTemplateUpdate, ScriptVariable
from models.store import StoreCategories, get_category_from_store_panel
from services.gff_service import GFFService
from services.palette_service import PaletteService

router = APIRouter(prefix="/api/items", tags=["items"])

# These will be injected by main.py
gff_service: GFFService = None
indexer = None
inventory_ops = None
tda_service = None
palette_service: PaletteService = None


def init(gff: GFFService, idx, inv_ops=None, tda=None, palette=None):
    global gff_service, indexer, inventory_ops, tda_service, palette_service
    gff_service = gff
    indexer = idx
    inventory_ops = inv_ops
    tda_service = tda
    palette_service = palette


@router.get("", response_model=dict)
async def list_items(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    base_item: Optional[int] = None,
    min_cost: Optional[int] = None,
    max_cost: Optional[int] = None
):
    """List items with pagination and optional filters."""
    items, total = indexer.list_items(
        offset=offset,
        limit=limit,
        base_item=base_item,
        min_cost=min_cost,
        max_cost=max_cost
    )

    return {
        "items": items,
        "total": total,
        "offset": offset,
        "limit": limit
    }


@router.get("/search")
async def search_items(
    q: str = Query(..., min_length=1),
    limit: int = Query(50, ge=1, le=200)
):
    """Full-text search items."""
    # Escape special FTS5 characters and add wildcard
    query = q.replace('"', '""')
    results = indexer.search_items(f'"{query}"*', limit)
    return {"items": results, "total": len(results)}


@router.get("/{resref}", response_model=ItemDetail)
async def get_item(resref: str):
    """Get a single item by resref."""
    data = gff_service.get_item(resref)
    if not data:
        raise HTTPException(status_code=404, detail=f"Item '{resref}' not found")

    # Extract properties
    props_list = GFFService.extract_list(data, "PropertiesList")
    properties = []
    for prop_data in props_list:
        prop_id = GFFService.extract_value(prop_data, "PropertyName", 0)
        subtype = GFFService.extract_value(prop_data, "Subtype")
        cost_value = GFFService.extract_value(prop_data, "CostValue")

        # Resolve names using TDA service
        prop_name_resolved = None
        subtype_resolved = None
        cost_value_resolved = None
        if tda_service:
            prop_name_resolved = tda_service.get_itemprop_name(prop_id)
            if subtype is not None:
                subtype_resolved = tda_service.resolve_property_subtype(prop_id, subtype)
            if cost_value is not None:
                cost_value_resolved = tda_service.resolve_property_value(prop_id, cost_value)

        prop = ItemProperty(
            property_name=prop_id,
            property_name_resolved=prop_name_resolved,
            subtype=subtype,
            subtype_resolved=subtype_resolved,
            cost_table=GFFService.extract_value(prop_data, "CostTable"),
            cost_value=cost_value,
            cost_value_resolved=cost_value_resolved,
            param1=GFFService.extract_value(prop_data, "Param1"),
            param1_value=GFFService.extract_value(prop_data, "Param1Value"),
            chance_appear=GFFService.extract_value(prop_data, "ChanceAppear")
        )
        properties.append(prop)

    # Extract variables from VarTable
    var_list = GFFService.extract_list(data, "VarTable")
    variables = []
    for var_data in var_list:
        var_name = GFFService.extract_value(var_data, "Name", "")
        var_type = GFFService.extract_value(var_data, "Type", 1)
        var_value = GFFService.extract_value(var_data, "Value", 0)
        if var_name:
            variables.append(ScriptVariable(
                name=var_name,
                var_type=var_type,
                value=var_value
            ))

    return ItemDetail(
        resref=resref,
        name=GFFService.extract_locstring(data, "LocalizedName"),
        localized_name=data.get("LocalizedName"),
        description=GFFService.extract_locstring(data, "Description"),
        localized_description=data.get("Description"),
        tag=GFFService.extract_value(data, "Tag", ""),
        base_item=GFFService.extract_value(data, "BaseItem", 0),
        cost=GFFService.extract_value(data, "Cost", 0),
        additional_cost=GFFService.extract_value(data, "AddCost", 0),
        stack_size=GFFService.extract_value(data, "StackSize", 1),
        charges=GFFService.extract_value(data, "Charges", 0),
        cursed=bool(GFFService.extract_value(data, "Cursed", 0)),
        identified=bool(GFFService.extract_value(data, "Identified", 1)),
        plot=bool(GFFService.extract_value(data, "Plot", 0)),
        stolen=bool(GFFService.extract_value(data, "Stolen", 0)),
        palette_id=GFFService.extract_value(data, "PaletteID"),
        comment=GFFService.extract_value(data, "Comment"),
        properties=properties,
        variables=variables,
        raw_data=data
    )


@router.get("/base-items/list")
async def list_base_items():
    """Get list of base item types with counts and names from baseitems.2da."""
    items, _ = indexer.list_items(offset=0, limit=10000)

    # Count items by base_item type
    counts = {}
    for item in items:
        bi = item.get("base_item", 0)
        counts[bi] = counts.get(bi, 0) + 1

    # Return sorted by count, include names from TDA service
    sorted_items = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    result = []
    for bi, count in sorted_items:
        name = f"Unknown ({bi})"
        if tda_service:
            name = tda_service.get_baseitem_name(bi)
        result.append({
            "base_item": bi,
            "name": name,
            "count": count
        })

    return {"base_items": result}


@router.get("/base-items/all")
async def get_all_base_items():
    """Get all base items from baseitems.2da with their names, store panels, and slot sizes.

    This endpoint provides the complete mapping from base item ID to name,
    which can be used by the frontend instead of a hardcoded list.
    """
    if not tda_service or not tda_service.is_loaded():
        return {"base_items": {}, "loaded": False}

    all_items = tda_service.get_all_baseitems()
    result = {}
    for item_id, data in all_items.items():
        name = data.get("label") or data.get("Name") or f"Unknown ({item_id})"
        store_panel = data.get("StorePanel")
        inv_slot_width = data.get("InvSlotWidth", 1) or 1
        inv_slot_height = data.get("InvSlotHeight", 1) or 1
        result[item_id] = {
            "name": str(name),
            "store_panel": store_panel,
            "inv_slot_width": inv_slot_width,
            "inv_slot_height": inv_slot_height
        }

    return {"base_items": result, "loaded": True}


@router.get("/{resref}/store-category")
async def get_item_store_category(resref: str):
    """Get the proper store category for an item based on its BaseItem type.

    This uses baseitems.2da StorePanel values to determine the correct
    category where an item should appear in a store.
    """
    data = gff_service.get_item(resref)
    if not data:
        raise HTTPException(status_code=404, detail=f"Item '{resref}' not found")

    base_item = GFFService.extract_value(data, "BaseItem", 0)
    store_panel = None
    base_item_name = f"Unknown ({base_item})"

    if tda_service:
        store_panel = tda_service.get_store_panel(base_item)
        base_item_name = tda_service.get_baseitem_name(base_item)

    category = get_category_from_store_panel(store_panel)

    return {
        "resref": resref,
        "base_item": base_item,
        "base_item_name": base_item_name,
        "store_panel": store_panel,
        "category_id": category,
        "category_name": StoreCategories.get_name(category)
    }


@router.get("/{resref}/references")
async def get_item_references(resref: str):
    """Find all references to an item across the module.

    Uses the pre-built reference index for fast lookups.
    The index is built during startup and updated on reindex.

    Returns counts and locations for each reference type:
    - Creature inventories (UTC ItemList)
    - Creature equipment (UTC Equip_ItemList)
    - Store templates (UTM StoreList -> ItemList)
    - Store instances in areas (GIT StoreList -> StoreList -> ItemList)
    """
    # Verify item exists
    item_data = gff_service.get_item(resref)
    if not item_data:
        raise HTTPException(status_code=404, detail=f"Item '{resref}' not found")

    # Use indexed references for fast lookup
    references = indexer.get_item_references(resref)
    return references


@router.post("/{resref}/update-instances")
async def update_item_instances(resref: str):
    """Sync all instances of an item with the template.

    Updates ALL properties from the template to all instances found in:
    - Creature inventories
    - Creature equipment
    - Store instances in areas (NOT store templates - those use references)

    Properties synced: Cost, LocalizedName, DescIdentified, Description,
    Identified, Plot, Cursed, Stolen, StackSize, PropertiesList, BaseItem,
    AddCost, Charges, ModelPart fields.
    """
    # Get the template
    template_data = gff_service.get_item(resref)
    if not template_data:
        raise HTTPException(status_code=404, detail=f"Item '{resref}' not found")

    # Fields to sync
    sync_fields = [
        "AddCost", "BaseItem", "Charges", "Cost", "Cursed",
        "DescIdentified", "Description", "Identified",
        "LocalizedName", "ModelPart1", "ModelPart2", "ModelPart3",
        "Plot", "PropertiesList", "StackSize", "Stolen", "Tag"
    ]

    updated_counts = {
        "creature_inventory": 0,
        "creature_equipment": 0,
        "area_stores": 0,
        "total": 0
    }

    # Update creature inventories and equipment
    for creature_resref in gff_service.list_creature_resrefs():
        creature_data = gff_service.get_creature(creature_resref)
        if not creature_data:
            continue

        modified = False

        # Update inventory items
        inv_list = GFFService.extract_list(creature_data, "ItemList")
        for inv_item in inv_list:
            item_resref = GFFService.extract_value(inv_item, "TemplateResRef", "")
            if item_resref == resref:
                # Sync fields from template
                for field in sync_fields:
                    if field in template_data:
                        inv_item[field] = template_data[field]
                modified = True
                updated_counts["creature_inventory"] += 1
                updated_counts["total"] += 1

        # Update inventory list if modified
        if modified and "ItemList" in creature_data:
            if isinstance(creature_data["ItemList"], dict):
                creature_data["ItemList"]["value"] = inv_list
            else:
                creature_data["ItemList"] = inv_list

        # Update equipment
        equip_list = GFFService.extract_list(creature_data, "Equip_ItemList")
        equip_modified = False
        for equip_item in equip_list:
            item_resref = GFFService.extract_value(equip_item, "EquippedRes", "")
            if not item_resref:
                item_resref = GFFService.extract_value(equip_item, "TemplateResRef", "")
            if item_resref == resref:
                # Sync fields from template (preserve __struct_id for slot)
                struct_id = equip_item.get("__struct_id")
                for field in sync_fields:
                    if field in template_data:
                        equip_item[field] = template_data[field]
                if struct_id is not None:
                    equip_item["__struct_id"] = struct_id
                equip_modified = True
                modified = True
                updated_counts["creature_equipment"] += 1
                updated_counts["total"] += 1

        # Update equipment list if modified
        if equip_modified and "Equip_ItemList" in creature_data:
            if isinstance(creature_data["Equip_ItemList"], dict):
                creature_data["Equip_ItemList"]["value"] = equip_list
            else:
                creature_data["Equip_ItemList"] = equip_list

        # Save creature if modified
        if modified:
            gff_service.save_creature(creature_resref, creature_data)

    # Update area store instances
    for area_resref in gff_service.list_area_git_resrefs():
        git_data = gff_service.get_area_git(area_resref)
        if not git_data:
            continue

        area_modified = False
        area_store_list = GFFService.extract_list(git_data, "StoreList")

        for store_instance in area_store_list:
            inner_store_list = GFFService.extract_list(store_instance, "StoreList")
            store_modified = False

            for cat_entry in inner_store_list:
                item_list = GFFService.extract_list(cat_entry, "ItemList")
                cat_modified = False

                for store_item in item_list:
                    item_resref = GFFService.extract_value(store_item, "TemplateResRef", "")
                    if not item_resref:
                        item_resref = GFFService.extract_value(store_item, "InventoryRes", "")
                    if item_resref == resref:
                        # Sync fields from template (preserve store-specific fields)
                        struct_id = store_item.get("__struct_id")
                        infinite = GFFService.extract_value(store_item, "Infinite", 0)
                        repos_x = store_item.get("Repos_PosX")
                        repos_y = store_item.get("Repos_Posy")

                        for field in sync_fields:
                            if field in template_data:
                                store_item[field] = template_data[field]

                        # Restore store-specific fields
                        if struct_id is not None:
                            store_item["__struct_id"] = struct_id
                        if infinite:
                            store_item["Infinite"] = {"type": "byte", "value": infinite}
                        if repos_x is not None:
                            store_item["Repos_PosX"] = repos_x
                        if repos_y is not None:
                            store_item["Repos_Posy"] = repos_y

                        cat_modified = True
                        store_modified = True
                        area_modified = True
                        updated_counts["area_stores"] += 1
                        updated_counts["total"] += 1

                # Update ItemList if modified
                if cat_modified:
                    if isinstance(cat_entry.get("ItemList"), dict):
                        cat_entry["ItemList"]["value"] = item_list
                    else:
                        cat_entry["ItemList"] = {"type": "list", "value": item_list}

            # Update inner StoreList if modified
            if store_modified:
                if isinstance(store_instance.get("StoreList"), dict):
                    store_instance["StoreList"]["value"] = inner_store_list
                else:
                    store_instance["StoreList"] = {"type": "list", "value": inner_store_list}

        # Save area if modified
        if area_modified:
            if isinstance(git_data.get("StoreList"), dict):
                git_data["StoreList"]["value"] = area_store_list
            else:
                git_data["StoreList"] = {"type": "list", "value": area_store_list}
            gff_service.save_area_git(area_resref, git_data)

    return {
        "success": True,
        "message": f"Updated {updated_counts['total']} instances",
        "updated_counts": updated_counts
    }


@router.put("/{resref}", response_model=ItemDetail)
async def update_item(resref: str, update: ItemTemplateUpdate):
    """Update an item template.

    This endpoint supports updating:
    - Basic fields: name, description, desc_identified, tag, cost, additional_cost, stack_size, charges
    - Flags: identified, plot, cursed, stolen
    - Properties: Full replacement of item properties list
    - Advanced: resref rename (new_resref), palette category change
    """
    # 1. Load existing item
    data = gff_service.get_item(resref)
    if not data:
        raise HTTPException(status_code=404, detail=f"Item '{resref}' not found")

    # 2. Validate new_resref if provided
    if update.new_resref:
        if len(update.new_resref) > 16:
            raise HTTPException(status_code=400, detail="Resref cannot exceed 16 characters")
        if not re.match(r'^[a-zA-Z0-9_]+$', update.new_resref):
            raise HTTPException(status_code=400, detail="Resref can only contain letters, numbers, underscores")
        if update.new_resref != resref and gff_service.item_exists(update.new_resref):
            raise HTTPException(status_code=400, detail=f"Item '{update.new_resref}' already exists")

    # 3. Apply simple field updates
    if update.cost is not None:
        GFFService.set_value(data, "Cost", update.cost, "dword")
    if update.additional_cost is not None:
        GFFService.set_value(data, "AddCost", update.additional_cost, "dword")
    if update.stack_size is not None:
        GFFService.set_value(data, "StackSize", update.stack_size, "word")
    if update.charges is not None:
        GFFService.set_value(data, "Charges", update.charges, "byte")
    if update.tag is not None:
        GFFService.set_value(data, "Tag", update.tag, "cexostring")

    # 4. Apply flag updates
    if update.identified is not None:
        GFFService.set_value(data, "Identified", 1 if update.identified else 0, "byte")
    if update.plot is not None:
        GFFService.set_value(data, "Plot", 1 if update.plot else 0, "byte")
    if update.cursed is not None:
        GFFService.set_value(data, "Cursed", 1 if update.cursed else 0, "byte")
    if update.stolen is not None:
        GFFService.set_value(data, "Stolen", 1 if update.stolen else 0, "byte")

    # 4b. Apply model part updates (both byte ModelPart and word xModelPart for NWN:EE)
    if update.model_part1 is not None:
        GFFService.set_value(data, "ModelPart1", update.model_part1, "byte")
        GFFService.set_value(data, "xModelPart1", update.model_part1, "word")
    if update.model_part2 is not None:
        GFFService.set_value(data, "ModelPart2", update.model_part2, "byte")
        GFFService.set_value(data, "xModelPart2", update.model_part2, "word")
    if update.model_part3 is not None:
        GFFService.set_value(data, "ModelPart3", update.model_part3, "byte")
        GFFService.set_value(data, "xModelPart3", update.model_part3, "word")

    # 5. Apply localized string updates
    if update.name:
        GFFService.set_locstring(data, "LocalizedName", update.name.text, update.name.string_ref)
    if update.description:
        GFFService.set_locstring(data, "Description", update.description.text, update.description.string_ref)
    if update.desc_identified:
        GFFService.set_locstring(data, "DescIdentified", update.desc_identified.text, update.desc_identified.string_ref)

    # 6. Apply properties update (full replacement)
    if update.properties is not None:
        props_list = []
        for prop in update.properties:
            props_list.append({
                "__struct_id": 0,
                "PropertyName": {"type": "word", "value": prop.property_name},
                "Subtype": {"type": "word", "value": prop.subtype},
                "CostTable": {"type": "byte", "value": prop.cost_table},
                "CostValue": {"type": "word", "value": prop.cost_value},
                "Param1": {"type": "byte", "value": prop.param1},
                "Param1Value": {"type": "byte", "value": prop.param1_value},
                "ChanceAppear": {"type": "byte", "value": prop.chance_appear},
            })
        if "PropertiesList" in data and isinstance(data["PropertiesList"], dict):
            data["PropertiesList"]["value"] = props_list
        else:
            data["PropertiesList"] = {"type": "list", "value": props_list}

    # 6b. Apply variables update (full replacement)
    if update.variables is not None:
        var_list = []
        for var in update.variables:
            # Determine value type based on var_type
            if var.var_type == 1:  # int
                value_entry = {"type": "int", "value": int(var.value) if var.value is not None else 0}
            elif var.var_type == 2:  # float
                value_entry = {"type": "float", "value": float(var.value) if var.value is not None else 0.0}
            elif var.var_type == 3:  # string
                value_entry = {"type": "cexostring", "value": str(var.value) if var.value is not None else ""}
            else:
                # Default to int
                value_entry = {"type": "int", "value": int(var.value) if var.value is not None else 0}

            var_list.append({
                "__struct_id": 0,
                "Name": {"type": "cexostring", "value": var.name},
                "Type": {"type": "dword", "value": var.var_type},
                "Value": value_entry,
            })

        if "VarTable" in data and isinstance(data["VarTable"], dict):
            data["VarTable"]["value"] = var_list
        else:
            data["VarTable"] = {"type": "list", "value": var_list}

    # 7. Handle resref rename
    final_resref = resref
    if update.new_resref and update.new_resref != resref:
        # Save current changes first
        gff_service.save_item(resref, data)
        # Rename file
        if not gff_service.rename_item(resref, update.new_resref):
            raise HTTPException(status_code=500, detail="Failed to rename item")
        final_resref = update.new_resref
        # Update palette
        if palette_service:
            palette_service.update_item_resref(resref, update.new_resref)
        # Delete old index entry and reindex new
        indexer.delete_item_index(resref)
    else:
        # Save changes
        gff_service.save_item(resref, data)

    # 8. Handle palette name update
    if update.name and update.name.text and palette_service:
        palette_service.update_item_name(final_resref, update.name.text)

    # 9. Handle palette category change
    if update.palette_category is not None and palette_service:
        palette_service.move_item_to_category(final_resref, update.palette_category)

    # 10. Trigger reindex
    indexer.update_item_index(final_resref)

    # Return updated item
    return await get_item(final_resref)


@router.get("/palette/categories")
async def get_palette_categories():
    """Get list of palette categories for items."""
    if not palette_service or not palette_service.palette_exists():
        return {"categories": [], "available": False}

    categories = palette_service.get_categories()
    return {"categories": categories, "available": True}


@router.get("/properties/types")
async def get_property_types():
    """Get all item property types with metadata for editor dropdowns.

    Returns list of property types with:
    - id: Property type ID (corresponds to itemprops.2da row)
    - label: Human-readable name (e.g., "Ability Bonus")
    - has_subtype: Whether this property has subtypes
    - has_cost_value: Whether this property has cost values
    - cost_table: The cost table ID
    """
    if not tda_service:
        raise HTTPException(status_code=503, detail="2DA service not available")

    properties = tda_service.get_all_item_properties()
    return {"properties": properties}


@router.get("/properties/{property_id}/subtypes")
async def get_property_subtypes(property_id: int):
    """Get valid subtypes for a property type.

    Args:
        property_id: The property type ID

    Returns:
        List of {id, label} options, or 404 if property has no subtypes
    """
    if not tda_service:
        raise HTTPException(status_code=503, detail="2DA service not available")

    subtypes = tda_service.get_property_subtypes(property_id)
    if subtypes is None:
        raise HTTPException(
            status_code=404,
            detail=f"Property {property_id} has no subtypes"
        )

    return {"subtypes": subtypes}


@router.get("/properties/{property_id}/cost-values")
async def get_property_cost_values(property_id: int):
    """Get valid cost values for a property type.

    Args:
        property_id: The property type ID

    Returns:
        List of {id, label} options, or 404 if property has no cost values
    """
    if not tda_service:
        raise HTTPException(status_code=503, detail="2DA service not available")

    cost_values = tda_service.get_property_cost_values(property_id)
    if cost_values is None:
        raise HTTPException(
            status_code=404,
            detail=f"Property {property_id} has no cost values"
        )

    return {"cost_values": cost_values}
