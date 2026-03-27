"""Store API endpoints."""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List

from models.store import (
    StoreSummary, StoreDetail, StoreSettings, StoreCategory,
    StoreCategories, StoreSettingsUpdate, StoreItemAdd, StoreItemUpdate,
    StoreItemAddAuto, StoreItemAddResult
)
from services.gff_service import GFFService

router = APIRouter(prefix="/api/stores", tags=["stores"])

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
async def list_stores(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200)
):
    """List stores with pagination."""
    stores, total = indexer.list_stores(offset=offset, limit=limit)

    return {
        "stores": stores,
        "total": total,
        "offset": offset,
        "limit": limit
    }


@router.get("/search")
async def search_stores(
    q: str = Query(..., min_length=1),
    limit: int = Query(50, ge=1, le=200)
):
    """Full-text search stores."""
    query = q.replace('"', '""')
    results = indexer.search_stores(f'"{query}"*', limit)
    return {"stores": results, "total": len(results)}


@router.get("/{resref}", response_model=StoreDetail)
async def get_store(resref: str):
    """Get a single store with inventory and settings."""
    data = gff_service.get_store(resref)
    if not data:
        raise HTTPException(status_code=404, detail=f"Store '{resref}' not found")

    # Get settings
    settings = inventory_ops.get_store_settings(resref)

    # Get all categories
    categories = []
    for cat_id in StoreCategories.all_categories():
        items = inventory_ops.get_store_category(resref, cat_id)
        categories.append(StoreCategory(
            category_id=cat_id,
            category_name=StoreCategories.get_name(cat_id),
            items=items
        ))

    return StoreDetail(
        resref=resref,
        name=GFFService.extract_locstring(data, "LocName"),
        tag=GFFService.extract_value(data, "Tag", ""),
        settings=settings,
        categories=categories,
        raw_data=data
    )


@router.put("/{resref}/settings")
async def update_store_settings(resref: str, body: StoreSettingsUpdate):
    """Update store settings."""
    # Convert model to dict, excluding None values
    settings_dict = {k: v for k, v in body.model_dump().items() if v is not None}

    if not settings_dict:
        raise HTTPException(status_code=400, detail="No settings to update")

    success = inventory_ops.update_store_settings(resref, settings_dict)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to update store settings")

    indexer.update_store_index(resref)

    return {"success": True}


@router.get("/{resref}/categories/{category_id}")
async def get_store_category(resref: str, category_id: int):
    """Get items in a store category."""
    if category_id not in StoreCategories.all_categories():
        raise HTTPException(status_code=400, detail=f"Invalid category_id: {category_id}")

    items = inventory_ops.get_store_category(resref, category_id)
    return {
        "category_id": category_id,
        "category_name": StoreCategories.get_name(category_id),
        "items": [item.model_dump() for item in items]
    }


@router.post("/{resref}/items", response_model=StoreItemAddResult)
async def add_store_item_auto(resref: str, body: StoreItemAddAuto):
    """Add an item to a store with automatic category detection.

    Uses the item's BaseItem type and baseitems.2da StorePanel to determine
    the correct category for the item.
    """
    result = inventory_ops.add_store_item_auto(
        resref,
        body.item_resref,
        body.infinite,
        body.stack_size
    )
    if not result:
        raise HTTPException(status_code=400, detail="Failed to add item to store")

    indexer.update_store_index(resref)

    return StoreItemAddResult(**result)


@router.post("/{resref}/categories/{category_id}/items")
async def add_store_item(resref: str, category_id: int, body: StoreItemAdd):
    """Add an item to a specific store category (manual override).

    Note: Prefer using POST /{resref}/items for automatic categorization.
    """
    if category_id not in StoreCategories.all_categories():
        raise HTTPException(status_code=400, detail=f"Invalid category_id: {category_id}")

    success = inventory_ops.add_store_item(
        resref, category_id,
        body.item_resref,
        body.infinite,
        body.stack_size
    )
    if not success:
        raise HTTPException(status_code=400, detail="Failed to add item to store")

    indexer.update_store_index(resref)

    return {"success": True, "item_resref": body.item_resref}


@router.put("/{resref}/categories/{category_id}/items/{index}")
async def update_store_item(resref: str, category_id: int, index: int, body: StoreItemUpdate):
    """Update a store item (infinite flag, stack size, cost, identified, position)."""
    if category_id not in StoreCategories.all_categories():
        raise HTTPException(status_code=400, detail=f"Invalid category_id: {category_id}")

    success = inventory_ops.update_store_item(
        resref, category_id, index,
        infinite=body.infinite,
        stack_size=body.stack_size,
        cost=body.cost,
        identified=body.identified,
        repos_x=body.repos_x,
        repos_y=body.repos_y
    )
    if not success:
        raise HTTPException(status_code=400, detail="Failed to update store item")

    indexer.update_store_index(resref)

    return {"success": True}


@router.delete("/{resref}/categories/{category_id}/items/{index}")
async def remove_store_item(resref: str, category_id: int, index: int):
    """Remove an item from a store category."""
    if category_id not in StoreCategories.all_categories():
        raise HTTPException(status_code=400, detail=f"Invalid category_id: {category_id}")

    success = inventory_ops.remove_store_item(resref, category_id, index)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to remove store item")

    # Update store search index so item counts and FTS stay in sync
    indexer.update_store_index(resref)

    return {"success": True, "index": index}
