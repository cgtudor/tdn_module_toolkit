"""Global search API endpoint."""
from fastapi import APIRouter, Query
from typing import List

router = APIRouter(prefix="/api/search", tags=["search"])

# Injected by main.py
indexer = None


def init(idx):
    global indexer
    indexer = idx


@router.get("")
async def global_search(
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100)
):
    """Search across all indexed content."""
    query = q.replace('"', '""')
    fts_query = f'"{query}"*'

    # Search each type
    items = indexer.search_items(fts_query, limit)
    creatures = indexer.search_creatures(fts_query, limit)
    stores = indexer.search_stores(fts_query, limit)

    # Add display_name to creatures
    for c in creatures:
        first = c.get("first_name", "")
        last = c.get("last_name", "")
        c["display_name"] = f"{first} {last}".strip() or c.get("resref", "")

    return {
        "items": items,
        "creatures": creatures,
        "stores": stores,
        "total": len(items) + len(creatures) + len(stores)
    }
