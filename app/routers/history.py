"""
StyleVision — Saved Looks / History Router
Saves, retrieves, updates, and deletes virtual try-on styling results for users via MongoDB.
JWT-protected and strictly user-scoped: users only ever see their own looks.
"""
from datetime import datetime, timezone
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.models.history import (
    SaveLookRequest,
    UpdateLookRequest,
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
        raw_cat = doc.get("category", "outfit")
        try:
            cat_enum = TryOnCategory(raw_cat)
        except ValueError:
            cat_enum = TryOnCategory.outfit

        results.append(
            SavedLookResponse(
                look_id=doc["look_id"],
                user_id=doc.get("user_id", user_id),
                title=doc.get("title", "Untitled Look"),
                category=cat_enum,
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


@router.get(
    "/{look_id}",
    response_model=SavedLookResponse,
    summary="Get details of a single saved styling look",
)
async def get_saved_look(look_id: str, current_user: dict = Depends(get_current_user)):
    """Retrieve a single saved look owned by the authenticated user."""
    user_id = current_user["sub"]
    db = get_database()
    col = db["saved_looks"]

    doc = await col.find_one({"look_id": look_id, "user_id": user_id})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Saved look '{look_id}' not found in your lookbook.",
        )

    raw_cat = doc.get("category", "outfit")
    try:
        cat_enum = TryOnCategory(raw_cat)
    except ValueError:
        cat_enum = TryOnCategory.outfit

    return SavedLookResponse(
        look_id=doc["look_id"],
        user_id=doc.get("user_id", user_id),
        title=doc.get("title", "Untitled Look"),
        category=cat_enum,
        original_image_url=doc.get("original_image_url", ""),
        result_image_url=doc.get("result_image_url", ""),
        style_item_name=doc.get("style_item_name", "Custom Style"),
        base_image_id=doc.get("base_image_id"),
        final_image_id=doc.get("final_image_id"),
        stages=doc.get("stages", []),
        created_at=doc.get("created_at", datetime.now(timezone.utc)),
    )


@router.put(
    "/{look_id}",
    response_model=SavedLookResponse,
    summary="Update title of a saved look",
)
async def update_saved_look(
    look_id: str,
    request: UpdateLookRequest,
    current_user: dict = Depends(get_current_user),
):
    """Update title or notes for a saved look in the user's lookbook."""
    user_id = current_user["sub"]
    db = get_database()
    col = db["saved_looks"]

    update_fields = {}
    if request.title:
        update_fields["title"] = request.title.strip()

    doc = await col.find_one_and_update(
        {"look_id": look_id, "user_id": user_id},
        {"$set": update_fields},
        return_document=True,
    )
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Saved look '{look_id}' not found in your lookbook.",
        )

    raw_cat = doc.get("category", "outfit")
    try:
        cat_enum = TryOnCategory(raw_cat)
    except ValueError:
        cat_enum = TryOnCategory.outfit

    return SavedLookResponse(
        look_id=doc["look_id"],
        user_id=doc.get("user_id", user_id),
        title=doc.get("title", "Untitled Look"),
        category=cat_enum,
        original_image_url=doc.get("original_image_url", ""),
        result_image_url=doc.get("result_image_url", ""),
        style_item_name=doc.get("style_item_name", "Custom Style"),
        base_image_id=doc.get("base_image_id"),
        final_image_id=doc.get("final_image_id"),
        stages=doc.get("stages", []),
        created_at=doc.get("created_at", datetime.now(timezone.utc)),
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

    # 1. Look up job from tryons collection
    job = await db["tryons"].find_one({"tryon_id": request.tryon_id, "user_id": user_id})

    # 2. If not in tryons collection, check images collection
    img_doc = None
    if not job:
        img_doc = await db["images"].find_one(
            {"user_id": user_id, "$or": [{"image_id": request.tryon_id}, {"tryon_id": request.tryon_id}]}
        )

    # Determine category
    cat_val = request.category
    if not cat_val and job:
        cat_val = job.get("category")
    if not cat_val and img_doc:
        cat_val = img_doc.get("stage")
    if not cat_val:
        if request.stages and len(request.stages) > 1:
            cat_val = "complete"
        elif "acc" in request.tryon_id:
            cat_val = "accessories"
        elif "mu" in request.tryon_id:
            cat_val = "makeup"
        elif "hair" in request.tryon_id:
            cat_val = "hairstyle"
        else:
            cat_val = "outfit"

    # Determine result image URL
    res_url = None
    if request.final_image_id:
        final_doc = await db["images"].find_one({"user_id": user_id, "image_id": request.final_image_id})
        if final_doc and final_doc.get("url"):
            res_url = final_doc["url"]

    if not res_url and job:
        res_url = job.get("result_image_url")
    if not res_url and img_doc:
        res_url = img_doc.get("url")
    if not res_url:
        res_url = f"/uploads/tryon/{request.tryon_id}.png"

    # Determine original base portrait URL
    orig_url = None
    if request.base_image_id:
        base_doc = await db["images"].find_one({"user_id": user_id, "image_id": request.base_image_id})
        if not base_doc:
            base_doc = await db["uploads"].find_one({"user_id": user_id, "image_id": request.base_image_id})
        if base_doc and base_doc.get("url"):
            orig_url = base_doc["url"]

    if not orig_url and job:
        orig_url = job.get("original_image_url")
    if not orig_url:
        latest_orig = await db["images"].find_one({"user_id": user_id, "kind": "original"}, sort=[("created_at", -1)])
        if latest_orig and latest_orig.get("url"):
            orig_url = latest_orig["url"]
        else:
            orig_url = ""

    # Style name
    style_name = None
    if job:
        style_name = job.get("subcategory") or job.get("garment_name") or job.get("style_name")
    if not style_name and img_doc:
        meta = img_doc.get("metadata", {})
        style_name = meta.get("subcategory") or meta.get("garment_name") or meta.get("style_name")
    if not style_name:
        style_name = "Complete Look" if cat_val == "complete" else title

    try:
        cat_enum = TryOnCategory(cat_val)
    except ValueError:
        cat_enum = TryOnCategory.outfit

    record = {
        "look_id": look_id,
        "user_id": user_id,
        "title": title,
        "category": cat_enum.value,
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
        category=cat_enum,
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
