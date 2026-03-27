"""Creature API endpoints."""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List

from models.creature import (
    CreatureSummary, CreatureDetail, EquipmentSlot, InventoryItem,
    EquipmentSlots, EquipmentUpdate, InventoryAdd
)
from services.gff_service import GFFService

router = APIRouter(prefix="/api/creatures", tags=["creatures"])

# Injected by main.py
gff_service: GFFService = None
indexer = None
inventory_ops = None
tda_service = None


def init(gff: GFFService, idx, inv_ops, tda=None):
    global gff_service, indexer, inventory_ops, tda_service
    gff_service = gff
    indexer = idx
    inventory_ops = inv_ops
    tda_service = tda


@router.get("", response_model=dict)
async def list_creatures(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200)
):
    """List creatures with pagination."""
    creatures, total = indexer.list_creatures(offset=offset, limit=limit)

    # Add display_name to each creature
    for c in creatures:
        first = c.get("first_name", "")
        last = c.get("last_name", "")
        c["display_name"] = f"{first} {last}".strip() or c.get("resref", "")

    return {
        "creatures": creatures,
        "total": total,
        "offset": offset,
        "limit": limit
    }


@router.get("/search")
async def search_creatures(
    q: str = Query(..., min_length=1),
    limit: int = Query(50, ge=1, le=200)
):
    """Full-text search creatures."""
    query = q.replace('"', '""')
    results = indexer.search_creatures(f'"{query}"*', limit)

    for c in results:
        first = c.get("first_name", "")
        last = c.get("last_name", "")
        c["display_name"] = f"{first} {last}".strip() or c.get("resref", "")

    return {"creatures": results, "total": len(results)}


@router.get("/{resref}", response_model=CreatureDetail)
async def get_creature(resref: str):
    """Get a single creature with equipment and inventory."""
    data = gff_service.get_creature(resref)
    if not data:
        raise HTTPException(status_code=404, detail=f"Creature '{resref}' not found")

    # Get equipment
    equipment = inventory_ops.get_creature_equipment(resref)

    # Ensure all slots are represented (even empty ones)
    equipped_slots = {e.slot_id for e in equipment}
    for slot_id in EquipmentSlots.all_slots():
        if slot_id not in equipped_slots:
            equipment.append(EquipmentSlot(
                slot_id=slot_id,
                slot_name=EquipmentSlots.get_name(slot_id),
                item_resref=None,
                item_name=None
            ))

    # Sort by slot_id
    equipment.sort(key=lambda e: e.slot_id)

    # Get inventory
    inventory = inventory_ops.get_creature_inventory(resref)

    # Extract IDs for name resolution
    race = GFFService.extract_value(data, "Race", 0)
    appearance = GFFService.extract_value(data, "Appearance_Type", 0)
    faction_id = GFFService.extract_value(data, "FactionID", 0)

    # Resolve names if TDA service is available
    race_name = None
    appearance_name = None
    faction_name = None
    if tda_service:
        race_name = tda_service.get_race_name(race)
        appearance_name = tda_service.get_appearance_name(appearance)
        faction_name = tda_service.get_faction_name(faction_id)

    return CreatureDetail(
        resref=resref,
        first_name=GFFService.extract_locstring(data, "FirstName"),
        last_name=GFFService.extract_locstring(data, "LastName"),
        tag=GFFService.extract_value(data, "Tag", ""),
        race=race,
        race_name=race_name,
        subrace=GFFService.extract_value(data, "Subrace"),
        appearance=appearance,
        appearance_name=appearance_name,
        faction_id=faction_id,
        faction_name=faction_name,
        gender=GFFService.extract_value(data, "Gender", 0),
        portrait=GFFService.extract_value(data, "Portrait"),
        equipment=equipment,
        inventory=inventory,
        raw_data=data
    )


@router.put("/{resref}/equipment/{slot_id}")
async def set_equipment(resref: str, slot_id: int, body: EquipmentUpdate):
    """Set an item in a creature's equipment slot."""
    # Validate slot_id
    if slot_id not in EquipmentSlots.all_slots():
        raise HTTPException(status_code=400, detail=f"Invalid slot_id: {slot_id}")

    success = inventory_ops.set_creature_equipment(resref, slot_id, body.item_resref)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to set equipment")

    return {"success": True, "slot_id": slot_id, "item_resref": body.item_resref}


@router.delete("/{resref}/equipment/{slot_id}")
async def remove_equipment(resref: str, slot_id: int):
    """Remove an item from a creature's equipment slot."""
    if slot_id not in EquipmentSlots.all_slots():
        raise HTTPException(status_code=400, detail=f"Invalid slot_id: {slot_id}")

    success = inventory_ops.remove_creature_equipment(resref, slot_id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to remove equipment")

    return {"success": True, "slot_id": slot_id}


@router.post("/{resref}/inventory")
async def add_inventory_item(resref: str, body: InventoryAdd):
    """Add an item to a creature's inventory."""
    success = inventory_ops.add_creature_inventory(
        resref,
        body.item_resref,
        body.stack_size,
        body.repos_x,
        body.repos_y
    )
    if not success:
        raise HTTPException(status_code=400, detail="Failed to add inventory item")

    return {"success": True, "item_resref": body.item_resref}


@router.delete("/{resref}/inventory/{index}")
async def remove_inventory_item(resref: str, index: int):
    """Remove an item from a creature's inventory by index."""
    success = inventory_ops.remove_creature_inventory(resref, index)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to remove inventory item")

    return {"success": True, "index": index}
