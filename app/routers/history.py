"""
StyleVision — Saved Looks / History Router
Saves, retrieves, and deletes virtual try-on styling results for users via MongoDB.
JWT-protected and strictly user-scoped: users only ever see their own looks.
"""
from datetime import datetime, timezone
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.models.history import (
    SaveLookRequest,
    SavedLookResponse,
    HistoryListResponse,
    DeleteResponse,
)
from app.models.catalogue import TryOnCategory
from app.utils.security import get_current_user
from app.database import get_database

router = APIRouter(prefix="/api/v1/history", tags=["Saved Looks & History"])


@router.get(
    "",
    response_model=HistoryListResponse,
    summary="List saved styling looks",
)
async def list_saved_looks(
    category: Optional[TryOnCategory] = Query(None, description="Filter by category"),
    current_user: dict = Depends(get_current_user),
):
    """Retrieve the authenticated user's saved looks with optional category filtering."""
    user_id = current_user["sub"]
    db = get_database()
    col = db["saved_looks"]

    query = {"user_id": user_id}
    if category:
        query["category"] = category.value

    cursor = col.find(query).sort("created_at", -1)
    results = []
    async for doc in cursor:
        results.append(
            SavedLookResponse(
                look_id=doc["look_id"],
                user_id=doc.get("user_id", user_id),
                title=doc.get("title", "Untitled Look"),
                category=TryOnCategory(doc["category"]),
                original_image_url=doc.get("original_image_url", ""),
                result_image_url=doc.get("result_image_url", ""),
                style_item_name=doc.get("style_item_name", "Custom Style"),
                base_image_id=doc.get("base_image_id"),
                final_image_id=doc.get("final_image_id"),
                stages=doc.get("stages", []),
                created_at=doc.get("created_at", datetime.now(timezone.utc)),
            )
        )

    return HistoryListResponse(
        looks=results,
        total=len(results),
    )


@router.post(
    "/save",
    response_model=SavedLookResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Save a try-on result to history",
)
async def save_look(request: SaveLookRequest, current_user: dict = Depends(get_current_user)):
    """Save a generated virtual styling try-on to the authenticated user's lookbook."""
    user_id = current_user["sub"]
    db = get_database()
    col = db["saved_looks"]

    look_id = f"look-{uuid.uuid4().hex[:10]}"
    title = request.title or "My Virtual Style"
    now = datetime.now(timezone.utc)

    job = await db["tryons"].find_one({"tryon_id": request.tryon_id, "user_id": user_id})

    cat_val = job.get("category") if job else None
    if not cat_val:
        if "acc" in request.tryon_id:
            cat_val = "accessories"
        elif "mu" in request.tryon_id:
            cat_val = "makeup"
        elif "hair" in request.tryon_id:
            cat_val = "hairstyle"
        else:
            cat_val = "outfit"

    orig_url = (job or {}).get("original_image_url") or ""
    res_url = (job or {}).get("result_image_url") or f"/uploads/tryon/{request.tryon_id}.png"
    style_name = (job or {}).get("subcategory") or (job or {}).get("garment_name") or title

    record = {
        "look_id": look_id,
        "user_id": user_id,
        "title": title,
        "category": cat_val,
        "original_image_url": orig_url,
        "result_image_url": res_url,
        "style_item_name": str(style_name).title(),
        "base_image_id": request.base_image_id,
        "final_image_id": request.final_image_id,
        "stages": request.stages or [],
        "created_at": now,
    }
    await col.insert_one(record)

    return SavedLookResponse(
        look_id=look_id,
        user_id=record["user_id"],
        title=record["title"],
        category=TryOnCategory(record["category"]),
        original_image_url=record["original_image_url"],
        result_image_url=record["result_image_url"],
        style_item_name=record["style_item_name"],
        base_image_id=record["base_image_id"],
        final_image_id=record["final_image_id"],
        stages=record["stages"],
        created_at=now,
    )


@router.delete(
    "/{look_id}",
    response_model=DeleteResponse,
    summary="Delete a saved look",
)
async def delete_look(look_id: str, current_user: dict = Depends(get_current_user)):
    """Remove a styling result document from the authenticated user's lookbook."""
    user_id = current_user["sub"]
    db = get_database()
    col = db["saved_looks"]

    result = await col.delete_one({"look_id": look_id, "user_id": user_id})
    if result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Saved look '{look_id}' not found.",
        )

    return DeleteResponse(
        message="Look successfully removed from history.",
        deleted_id=look_id,
    )
