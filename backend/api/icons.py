"""Icon API endpoints for serving NWN item icons as PNG images."""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from typing import Optional

from services.gff_service import GFFService
from services.icon_service import IconService

router = APIRouter(prefix="/api/icons", tags=["icons"])

# Injected by main.py
icon_service: IconService = None
gff_service: GFFService = None


def init(icons: IconService, gff: GFFService):
    global icon_service, gff_service
    icon_service = icons
    gff_service = gff


def _png_response(data: bytes) -> Response:
    """Return a PNG image response with caching headers."""
    return Response(
        content=data,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/item/{resref}")
async def get_item_icon(resref: str):
    """Get the icon PNG for a specific item by its resref."""
    if not icon_service or not gff_service:
        raise HTTPException(status_code=503, detail="Icon service not initialized")

    # Load item data to get BaseItem and ModelPart fields
    try:
        item_data = gff_service.get_item(resref)
    except Exception:
        raise HTTPException(status_code=404, detail=f"Item not found: {resref}")

    if not item_data:
        raise HTTPException(status_code=404, detail=f"Item not found: {resref}")

    base_item = GFFService.extract_value(item_data, "BaseItem", 0)
    part1 = GFFService.extract_value(item_data, "ModelPart1", 1)
    part2 = GFFService.extract_value(item_data, "ModelPart2", 1)
    part3 = GFFService.extract_value(item_data, "ModelPart3", 1)

    png_data = icon_service.get_icon_png(base_item, part1, part2, part3)
    if not png_data:
        raise HTTPException(status_code=404, detail="No icon found for this item")

    return _png_response(png_data)


@router.get("/base-item/{base_item_id}/default")
async def get_default_icon(base_item_id: int):
    """Get the default icon for a base item type."""
    if not icon_service:
        raise HTTPException(status_code=503, detail="Icon service not initialized")

    png_data = icon_service.get_default_icon_png(base_item_id)
    if not png_data:
        raise HTTPException(status_code=404, detail="No default icon for this base item type")

    return _png_response(png_data)


@router.get("/base-item/{base_item_id}/available")
async def get_available_icons(base_item_id: int):
    """Get available icon part numbers for a base item type."""
    if not icon_service:
        raise HTTPException(status_code=503, detail="Icon service not initialized")

    result = icon_service.list_available_parts(base_item_id)
    if not result:
        raise HTTPException(status_code=404, detail="Base item type not found or has no icon info")

    return result


@router.get("/preview")
async def get_preview_icon(
    base_item: int = Query(...),
    p1: int = Query(1),
    p2: int = Query(1),
    p3: int = Query(1),
):
    """Get a preview icon for specific part numbers."""
    if not icon_service:
        raise HTTPException(status_code=503, detail="Icon service not initialized")

    png_data = icon_service.get_preview_png(base_item, p1, p2, p3)
    if not png_data:
        raise HTTPException(status_code=404, detail="No icon found for these parameters")

    return _png_response(png_data)
